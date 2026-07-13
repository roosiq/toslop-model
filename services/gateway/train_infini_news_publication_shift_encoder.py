#!/usr/bin/env python3
"""Train a text-only multi-task INFINI-NEWS publication-shift encoder.

The score estimates similarity to matched current-era publication language.
This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import torch
from build_publication_shift_splits import build_infini_news_protocols, protocol_summary, stable_json_sha256
from sklearn.metrics import mean_absolute_error, mean_squared_error
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset
from train_infini_news_publication_shift_candidates import (
    CORE_ROLES,
    DISCLAIMER,
    SCORE_NAME,
    TEXT_FIELD,
    assert_public_safe,
    binary_metrics,
    choose_threshold,
    no_text_prediction,
    read_jsonl_balanced_by_role,
    rows_for_split,
    score_distribution,
    sha256_file,
    write_json,
    write_jsonl,
)
from transformers import AutoConfig, AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

try:
    import safetensors.torch as safe_torch
except Exception:  # pragma: no cover - optional dependency guard
    safe_torch = None

SEED = 20260712
YEAR_CENTER = 2023.0
YEAR_SCALE = 4.0
DEFAULT_BASE_MODEL = "microsoft/deberta-v3-small"
DEFAULT_PINNED_REVISION = "a36c739020e01763fe789b4b85e2df55d6180012"
MODEL_FAMILY = "infini_news_deberta_multitask_encoder"
CANDIDATE_NAME = "deberta_multitask_encoder"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def set_deterministic_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def accelerator_probe() -> dict[str, Any]:
    probe: dict[str, Any] = {
        "torch": torch.__version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()),
        "torch_cuda_version": getattr(torch.version, "cuda", None),
        "torch_hip_version": getattr(torch.version, "hip", None),
        "selected_device": "cpu",
        "verified": False,
    }
    if torch.cuda.is_available():
        try:
            tensor = torch.ones(2, 2, device="cuda")
            probe["cuda_tensor_sum"] = float((tensor @ tensor).sum().item())
            probe["selected_device"] = "cuda"
            probe["device_name"] = torch.cuda.get_device_name(0)
            probe["verified"] = True
        except Exception as exc:  # pragma: no cover - hardware-specific
            probe["cuda_error"] = repr(exc)
    return probe


def select_device(probe: dict[str, Any], requested: str) -> torch.device:
    if requested == "auto":
        return torch.device(probe["selected_device"] if probe.get("verified") else "cpu")
    if requested == "cuda" and not probe.get("verified"):
        raise RuntimeError("CUDA was requested but accelerator_probe did not verify a usable CUDA device")
    return torch.device(requested)


@dataclass(frozen=True)
class EncoderExample:
    document_id: str
    text: str
    era_label: int
    year: int
    row: dict[str, Any]


def year_to_target(year: int | float) -> float:
    return (float(year) - YEAR_CENTER) / YEAR_SCALE


def target_to_year(target: float) -> float:
    return float(target) * YEAR_SCALE + YEAR_CENTER


def build_examples(rows: Sequence[dict[str, Any]], labels_by_role: dict[str, int] = CORE_ROLES) -> list[EncoderExample]:
    examples: list[EncoderExample] = []
    for row in rows:
        role = row.get("corpus_role")
        if role not in labels_by_role:
            continue
        text = str(row.get(TEXT_FIELD) or "")
        examples.append(
            EncoderExample(
                document_id=str(row["document_id"]),
                text=text,
                era_label=int(labels_by_role[str(role)]),
                year=int(row["publication_year"]),
                row=row,
            )
        )
    return examples


class EncoderDataset(Dataset[EncoderExample]):
    def __init__(self, examples: Sequence[EncoderExample]) -> None:
        self.examples = list(examples)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> EncoderExample:
        return self.examples[index]


class TextOnlyCollator:
    """Tokenize article text only; metadata stays outside model inputs."""

    def __init__(self, tokenizer: Any, max_length: int) -> None:
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, batch: Sequence[EncoderExample]) -> dict[str, Any]:
        texts = [item.text for item in batch]
        tokens = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        years = torch.tensor([item.year for item in batch], dtype=torch.float32)
        pair_indices: list[tuple[int, int, float]] = []
        for left in range(len(batch)):
            for right in range(left + 1, len(batch)):
                if batch[left].year == batch[right].year:
                    continue
                target = 1.0 if batch[left].year > batch[right].year else -1.0
                pair_indices.append((left, right, target))
        return {
            "input_ids": tokens["input_ids"],
            "attention_mask": tokens.get("attention_mask"),
            "era_labels": torch.tensor([item.era_label for item in batch], dtype=torch.long),
            "year_targets": torch.tensor([year_to_target(item.year) for item in batch], dtype=torch.float32),
            "years": years,
            "pair_indices": torch.tensor(pair_indices, dtype=torch.float32) if pair_indices else torch.empty((0, 3), dtype=torch.float32),
            "rows": [item.row for item in batch],
            "document_ids": [item.document_id for item in batch],
        }


class MultiTaskPublicationEncoder(nn.Module):
    def __init__(self, base_model_name_or_path: str, *, revision: str | None = None, local_files_only: bool = False, dropout: float = 0.1) -> None:
        super().__init__()
        config = AutoConfig.from_pretrained(base_model_name_or_path, revision=revision, local_files_only=local_files_only)
        self.encoder = AutoModel.from_pretrained(base_model_name_or_path, config=config, revision=revision, local_files_only=local_files_only)
        hidden = int(getattr(config, "hidden_size"))
        self.dropout = nn.Dropout(dropout)
        self.era_classifier = nn.Linear(hidden, 2)
        self.year_regressor = nn.Linear(hidden, 1)

    def pooled(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            return outputs.pooler_output
        hidden = outputs.last_hidden_state
        if attention_mask is None:
            return hidden[:, 0]
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        return (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        era_labels: torch.Tensor | None = None,
        year_targets: torch.Tensor | None = None,
        pair_indices: torch.Tensor | None = None,
        rank_margin: float = 0.1,
        loss_weights: dict[str, float] | None = None,
    ) -> dict[str, torch.Tensor]:
        weights = {"era": 1.0, "year": 0.25, "rank": 0.25, **(loss_weights or {})}
        pooled = self.dropout(self.pooled(input_ids=input_ids, attention_mask=attention_mask))
        pooled = pooled.to(self.era_classifier.weight.dtype)
        era_logits = self.era_classifier(pooled)
        year_pred = self.year_regressor(pooled).squeeze(-1)
        losses: dict[str, torch.Tensor] = {}
        if era_labels is not None:
            losses["era_loss"] = F.cross_entropy(era_logits, era_labels)
        if year_targets is not None:
            losses["year_loss"] = F.mse_loss(year_pred, year_targets)
        if pair_indices is not None and pair_indices.numel() > 0:
            idx = pair_indices.to(year_pred.device)
            left = idx[:, 0].long()
            right = idx[:, 1].long()
            target = idx[:, 2]
            losses["rank_loss"] = F.margin_ranking_loss(year_pred[left], year_pred[right], target, margin=rank_margin)
        total = sum(weights[name.replace("_loss", "")] * value for name, value in losses.items()) if losses else year_pred.sum() * 0.0
        return {"loss": total, "era_logits": era_logits, "year_pred": year_pred, **losses}


def move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    moved = dict(batch)
    for key in ["input_ids", "attention_mask", "era_labels", "year_targets", "pair_indices"]:
        value = moved.get(key)
        if isinstance(value, torch.Tensor):
            moved[key] = value.to(device)
    return moved


def prediction_from_outputs(rows: Sequence[dict[str, Any]], era_scores: np.ndarray, year_pred: np.ndarray, lane: str, split: str | None) -> list[dict[str, Any]]:
    preds = []
    for row, score, year_value in zip(rows, era_scores, year_pred):
        label = CORE_ROLES.get(str(row.get("corpus_role")))
        payload = no_text_prediction(row, float(score), label, MODEL_FAMILY, lane, split)
        payload["predicted_publication_year"] = float(year_value)
        preds.append(payload)
    return preds


@torch.no_grad()
def score_examples(model: MultiTaskPublicationEncoder, loader: DataLoader, device: torch.device) -> dict[str, Any]:
    model.eval()
    rows: list[dict[str, Any]] = []
    labels: list[int] = []
    years: list[float] = []
    era_scores: list[float] = []
    year_preds: list[float] = []
    for batch in loader:
        moved = move_batch(batch, device)
        out = model(input_ids=moved["input_ids"], attention_mask=moved.get("attention_mask"))
        probs = torch.softmax(out["era_logits"], dim=-1)[:, 1].detach().cpu().numpy()
        denorm_years = [target_to_year(value) for value in out["year_pred"].detach().cpu().numpy()]
        era_scores.extend(float(v) for v in probs)
        year_preds.extend(denorm_years)
        labels.extend(int(v) for v in batch["era_labels"].numpy())
        years.extend(float(v) for v in batch["years"].numpy())
        rows.extend(batch["rows"])
    return {"rows": rows, "labels": np.asarray(labels, dtype=np.int8), "years": np.asarray(years, dtype=float), "era_scores": np.asarray(era_scores, dtype=float), "year_predictions": np.asarray(year_preds, dtype=float)}


def regression_metrics(years: np.ndarray, preds: np.ndarray) -> dict[str, Any]:
    if len(years) == 0:
        return {"count": 0, "mae_years": None, "rmse_years": None}
    return {"count": int(len(years)), "mae_years": float(mean_absolute_error(years, preds)), "rmse_years": float(math.sqrt(mean_squared_error(years, preds)))}


def recency_pair_accuracy(years: np.ndarray, preds: np.ndarray, max_pairs: int = 20000) -> dict[str, Any]:
    pairs = []
    for left in range(len(years)):
        for right in range(left + 1, len(years)):
            if years[left] != years[right]:
                pairs.append((left, right))
                if len(pairs) >= max_pairs:
                    break
        if len(pairs) >= max_pairs:
            break
    if not pairs:
        return {"pair_count": 0, "accuracy": None}
    correct = 0
    for left, right in pairs:
        correct += int((years[left] > years[right]) == (preds[left] > preds[right]))
    return {"pair_count": len(pairs), "accuracy": float(correct / len(pairs))}


def build_loader(examples: Sequence[EncoderExample], tokenizer: Any, args: argparse.Namespace, *, shuffle: bool) -> DataLoader:
    generator = torch.Generator().manual_seed(args.numeric_seed)
    return DataLoader(
        EncoderDataset(examples),
        batch_size=args.batch_size,
        shuffle=shuffle,
        generator=generator if shuffle else None,
        collate_fn=TextOnlyCollator(tokenizer, args.max_length),
        num_workers=0,
    )


def train_model(model: MultiTaskPublicationEncoder, train_loader: DataLoader, validation_loader: DataLoader, device: torch.device, args: argparse.Namespace) -> dict[str, Any]:
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = max(1, len(train_loader) * args.epochs)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=min(args.warmup_steps, total_steps // 2), num_training_steps=total_steps)
    start_epoch = 0
    checkpoint_dir = args.checkpoint_dir
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    latest = checkpoint_dir / "latest.pt"
    if args.resume and latest.exists():
        state = torch.load(latest, map_location=device)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        start_epoch = int(state["epoch"]) + 1
    history: list[dict[str, Any]] = []
    for epoch in range(start_epoch, args.epochs):
        model.train()
        losses = []
        for batch in train_loader:
            moved = move_batch(batch, device)
            optimizer.zero_grad(set_to_none=True)
            out = model(
                input_ids=moved["input_ids"],
                attention_mask=moved.get("attention_mask"),
                era_labels=moved["era_labels"],
                year_targets=moved["year_targets"],
                pair_indices=moved["pair_indices"],
                rank_margin=args.rank_margin,
            )
            out["loss"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            scheduler.step()
            losses.append(float(out["loss"].detach().cpu().item()))
            if args.max_train_steps and len(losses) >= args.max_train_steps:
                break
        val = score_examples(model, validation_loader, device)
        threshold = choose_threshold(val["labels"], val["era_scores"])
        epoch_record = {
            "epoch": epoch,
            "train_loss_mean": float(np.mean(losses)) if losses else None,
            "validation_era": binary_metrics(val["labels"], val["era_scores"], threshold),
            "validation_year": regression_metrics(val["years"], val["year_predictions"]),
            "validation_recency_rank": recency_pair_accuracy(val["years"], val["year_predictions"]),
            "threshold": threshold,
        }
        history.append(epoch_record)
        torch.save({"epoch": epoch, "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(), "history": history}, latest)
    return {"history": history, "checkpoint": str(latest)}


def evaluate_lane(model: MultiTaskPublicationEncoder, examples: Sequence[EncoderExample], tokenizer: Any, args: argparse.Namespace, device: torch.device, threshold: float, lane: str, split: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    loader = build_loader(examples, tokenizer, args, shuffle=False)
    scored = score_examples(model, loader, device)
    metrics = {
        "era": binary_metrics(scored["labels"], scored["era_scores"], threshold),
        "publication_year": regression_metrics(scored["years"], scored["year_predictions"]),
        "recency_rank": recency_pair_accuracy(scored["years"], scored["year_predictions"]),
    }
    predictions = prediction_from_outputs(scored["rows"], scored["era_scores"], scored["year_predictions"], lane, split)
    return metrics, predictions


def write_failed_candidate(output_dir: Path, failure: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "publication_shift.infini_news_encoder_failure.v1", "created_at": utc_now(), "candidate_name": CANDIDATE_NAME, "disclaimer": DISCLAIMER, **failure}
    write_json(output_dir / "FAILED_CANDIDATE.json", payload)
    (output_dir / "MODEL_CARD.md").write_text("\n".join([f"# INFINI-NEWS {CANDIDATE_NAME} candidate", "", DISCLAIMER, "", "- Decision: `HOLD`", f"- Failure reason: `{failure.get('reason')}`", "- Production wiring: none", ""]), encoding="utf-8")


def save_pretrained_artifact(model: MultiTaskPublicationEncoder, tokenizer: Any, artifact_path: Path, metadata: dict[str, Any]) -> None:
    artifact_path.mkdir(parents=True, exist_ok=True)
    (artifact_path / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tokenizer.save_pretrained(artifact_path / "tokenizer")
    (artifact_path / "encoder_config.json").write_text(model.encoder.config.to_json_string(), encoding="utf-8")
    head_state = {f"era_classifier.{key}": value.detach().cpu() for key, value in model.era_classifier.state_dict().items()}
    head_state.update({f"year_regressor.{key}": value.detach().cpu() for key, value in model.year_regressor.state_dict().items()})
    if safe_torch is not None:
        safe_torch.save_file(head_state, artifact_path / "multitask_heads.safetensors")
    else:  # pragma: no cover - safetensors is present in the training env
        torch.save({"heads": head_state, "metadata": metadata}, artifact_path / "multitask_heads.pt")


def render_model_card(metadata: dict[str, Any], metrics: dict[str, Any]) -> str:
    primary_auc = metrics["lanes"].get("publisher_domain_heldout_primary", {}).get("era", {}).get("roc_auc")
    return "\n".join([
        f"# INFINI-NEWS {CANDIDATE_NAME} candidate",
        "",
        DISCLAIMER,
        "",
        f"- Model ID: `{metadata['model_id']}`",
        f"- Model family: `{MODEL_FAMILY}`",
        "- Runtime inputs: article text tokens only; metadata is not accepted by the model forward path.",
        "- Tasks: era classification, publication-year regression, pairwise recency ranking.",
        "- Training protocol: `publisher_domain_heldout_primary` train/validation rows only.",
        "- Evaluation-only roles excluded from fitting/calibration/thresholds: `historical_placebo`, `transition_2022`, `forward_2026`.",
        "- Production wiring: none",
        f"- Decision: `{metrics['decision']}`",
        f"- Primary held-out ROC-AUC: `{primary_auc}`",
        f"- Artifact SHA256: `{metadata.get('artifact_sha256')}`",
        "",
        "Public artifacts contain IDs, hashes, metrics, and feature audits only; article text, titles, descriptions, URLs, and previews are excluded.",
        "",
    ])


def directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> dict[str, Any]:
    set_deterministic_seed(args.numeric_seed)
    probe = accelerator_probe()
    device = select_device(probe, args.device)
    candidate_dir = args.output / CANDIDATE_NAME
    candidate_dir.mkdir(parents=True, exist_ok=True)
    args.checkpoint_dir = args.checkpoint_dir or (candidate_dir / "checkpoints")

    if args.require_accelerator and device.type == "cpu":
        failure = {"reason": "accelerator_required_but_not_verified", "accelerator_probe": probe, "decision": "HOLD"}
        write_failed_candidate(candidate_dir, failure)
        return {"candidate_name": CANDIDATE_NAME, "decision": "HOLD", "failure": failure}

    rows = read_jsonl_balanced_by_role(args.corpus / "normalized_rows.jsonl", limit_per_role=args.limit_per_role)
    rows_by_id = {row["document_id"]: row for row in rows}
    package = build_infini_news_protocols(rows, seed=args.seed)
    summary = protocol_summary(package)
    primary_manifest = package["protocols"]["publisher_domain_heldout_primary"]
    primary_train_rows = rows_for_split(rows_by_id, primary_manifest, "train", CORE_ROLES)
    primary_validation_rows = rows_for_split(rows_by_id, primary_manifest, "validation", CORE_ROLES)
    primary_test_rows = rows_for_split(rows_by_id, primary_manifest, "test", CORE_ROLES)

    train_examples = build_examples(primary_train_rows)
    validation_examples = build_examples(primary_validation_rows)
    test_examples = build_examples(primary_test_rows)
    if not train_examples or not validation_examples:
        failure = {"reason": "empty_train_or_validation_split", "counts": {"train": len(train_examples), "validation": len(validation_examples)}, "decision": "HOLD", "accelerator_probe": probe}
        write_failed_candidate(candidate_dir, failure)
        return {"candidate_name": CANDIDATE_NAME, "decision": "HOLD", "failure": failure}

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name_or_path or args.base_model, revision=args.tokenizer_revision, local_files_only=args.local_files_only)
    model = MultiTaskPublicationEncoder(args.base_model, revision=args.model_revision, local_files_only=args.local_files_only, dropout=args.dropout)
    if device.type == "cpu":
        model = model.float()
    train_loader = build_loader(train_examples, tokenizer, args, shuffle=True)
    validation_loader = build_loader(validation_examples, tokenizer, args, shuffle=False)
    training = train_model(model, train_loader, validation_loader, device, args)
    best = training["history"][-1] if training["history"] else {"threshold": 0.5}
    threshold = float(best["threshold"])

    lanes: dict[str, Any] = {"primary_validation": best}
    prediction_files: dict[str, str] = {}
    checksum_paths: list[Path] = []
    metrics, predictions = evaluate_lane(model, test_examples, tokenizer, args, device, threshold, "publisher_domain_heldout_primary", "test")
    lanes["publisher_domain_heldout_primary"] = metrics
    pred_path = candidate_dir / "publisher_domain_heldout_primary_predictions.jsonl"
    write_jsonl(pred_path, predictions)
    prediction_files["publisher_domain_heldout_primary"] = str(pred_path)
    checksum_paths.append(pred_path)

    for lane_name in ["source_sitename_heldout", "topic_heldout", "author_heldout", "random_diagnostic"]:
        manifest = package["protocols"][lane_name]
        lane_examples = build_examples(rows_for_split(rows_by_id, manifest, "test", CORE_ROLES))
        metrics, predictions = evaluate_lane(model, lane_examples, tokenizer, args, device, threshold, lane_name, "test")
        lanes[lane_name] = metrics
        pred_path = candidate_dir / f"{lane_name}_predictions.jsonl"
        write_jsonl(pred_path, predictions)
        prediction_files[lane_name] = str(pred_path)
        checksum_paths.append(pred_path)

    for role, lane_name in [("transition_2022", "transition_2022"), ("forward_2026", "forward_2026_jan_apr")]:
        eval_examples = [EncoderExample(str(row["document_id"]), str(row.get(TEXT_FIELD) or ""), 0, int(row["publication_year"]), row) for row in rows if row.get("corpus_role") == role]
        loader = build_loader(eval_examples, tokenizer, args, shuffle=False)
        scored = score_examples(model, loader, device)
        lanes[lane_name] = {"era_score_distribution": score_distribution(scored["era_scores"]), "predicted_year_distribution": score_distribution(scored["year_predictions"])}
        pred_path = candidate_dir / f"{lane_name}_predictions.jsonl"
        write_jsonl(pred_path, prediction_from_outputs(scored["rows"], scored["era_scores"], scored["year_predictions"], lane_name, "evaluation_only"))
        prediction_files[lane_name] = str(pred_path)
        checksum_paths.append(pred_path)

    placebo_rows = [row for row in rows if row.get("corpus_role") == "historical_placebo"]
    matched_placebo_lanes = {}
    for early, late in [((2016, 2017), (2020, 2021)), ((2016, 2017, 2018), (2019, 2020, 2021))]:
        lane_rows = []
        labels_by_doc = {}
        for row in placebo_rows:
            if row.get("publication_year") in early:
                lane_rows.append(row); labels_by_doc[row["document_id"]] = 0
            elif row.get("publication_year") in late:
                lane_rows.append(row); labels_by_doc[row["document_id"]] = 1
        lane_examples = [EncoderExample(str(row["document_id"]), str(row.get(TEXT_FIELD) or ""), labels_by_doc[row["document_id"]], int(row["publication_year"]), row) for row in lane_rows]
        name = f"placebo_{min(early)}_{max(early)}_vs_{min(late)}_{max(late)}"
        metrics, predictions = evaluate_lane(model, lane_examples, tokenizer, args, device, threshold, name, "evaluation_only")
        matched_placebo_lanes[name] = metrics
        pred_path = candidate_dir / f"{name}_predictions.jsonl"
        write_jsonl(pred_path, predictions)
        prediction_files[name] = str(pred_path)
        checksum_paths.append(pred_path)
    lanes["matched_2016_2021_placebos"] = matched_placebo_lanes

    train_identity = stable_json_sha256({
        "primary_assignment_sha256": summary["protocols"]["publisher_domain_heldout_primary"]["assignment_sha256"],
        "fit_roles": CORE_ROLES,
        "train_document_ids": sorted(row["document_id"] for row in primary_train_rows),
        "seed": args.seed,
        "numeric_seed": args.numeric_seed,
        "candidate": CANDIDATE_NAME,
        "base_model": args.base_model,
        "model_revision": args.model_revision,
        "tokenizer_revision": args.tokenizer_revision,
        "max_length": args.max_length,
    })
    model_id = f"infini-news-{CANDIDATE_NAME}-v1-{train_identity[:12]}"
    artifact_path = args.artifact_dir / CANDIDATE_NAME
    metadata = {
        "schema": "publication_shift.infini_news_encoder_metadata.v1",
        "created_at": utc_now(),
        "model_id": model_id,
        "candidate_name": CANDIDATE_NAME,
        "model_family": MODEL_FAMILY,
        "score_name": SCORE_NAME,
        "disclaimer": DISCLAIMER,
        "base_model": args.base_model,
        "model_revision": args.model_revision,
        "tokenizer_revision": args.tokenizer_revision,
        "runtime_inputs": ["input_ids", "attention_mask"],
        "metadata_runtime_inputs": [],
        "tasks": ["era_classification", "publication_year_regression", "pairwise_recency_ranking"],
        "artifact_path": str(artifact_path),
        "training_identity_sha256": train_identity,
        "threshold": threshold,
        "training_roles": CORE_ROLES,
        "excluded_from_training": ["historical_placebo", "transition_2022", "forward_2026"],
        "split_summary_sha256": stable_json_sha256(summary),
        "accelerator_probe": probe,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "torch": torch.__version__},
    }
    save_pretrained_artifact(model, tokenizer, artifact_path, metadata)
    metadata["artifact_sha256"] = directory_sha256(artifact_path)
    metadata["artifact_size_bytes"] = sum(p.stat().st_size for p in artifact_path.rglob("*") if p.is_file())

    decision = "PASS-HOLD" if not args.limit_per_role else "SMOKE-HOLD"
    decision_reason = (
        "Encoder candidate artifacts and frozen-lane diagnostics produced; held for downstream review/no production wiring and this score does not establish AI authorship."
        if not args.limit_per_role
        else "CPU smoke candidate only because --limit-per-role was set; held from production and serious claims until a full frozen-row run completes on feasible verified hardware."
    )
    metrics_payload = {
        "schema": "publication_shift.infini_news_encoder_metrics.v1",
        "created_at": utc_now(),
        "model_id": model_id,
        "candidate_name": CANDIDATE_NAME,
        "model_family": MODEL_FAMILY,
        "score_name": SCORE_NAME,
        "disclaimer": DISCLAIMER,
        "decision": decision,
        "decision_reason": decision_reason,
        "training_protocol": "publisher_domain_heldout_primary",
        "counts": {"train": len(train_examples), "validation": len(validation_examples), "test": len(test_examples), "corpus_rows": len(rows)},
        "training_history": training,
        "lanes": lanes,
        "prediction_files": prediction_files,
    }
    write_json(candidate_dir / "metrics.json", metrics_payload)
    write_json(candidate_dir / "model_metadata.json", metadata)
    card = render_model_card(metadata, metrics_payload)
    (candidate_dir / "MODEL_CARD.md").write_text(card, encoding="utf-8")
    checksum_paths.extend([candidate_dir / "metrics.json", candidate_dir / "model_metadata.json", candidate_dir / "MODEL_CARD.md"])
    checksums = {str(path): sha256_file(path) for path in sorted(set(checksum_paths), key=str)}
    write_json(args.output / "encoder_checksums.json", {"schema": "publication_shift.infini_news_encoder_checksums.v1", "files": checksums})
    (args.output / "encoder_checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(checksums.items())), encoding="utf-8")
    return {"candidate_name": CANDIDATE_NAME, "decision": decision, "metadata": metadata, "metrics": metrics_payload}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("services/data/publication_shift/infini_news_v1"))
    parser.add_argument("--output", type=Path, default=Path("services/evals/publication_shift_model/infini_news_v1/candidates"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("services/gateway/model_artifacts/publication_shift/infini_news_v1"))
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--model-revision", default=DEFAULT_PINNED_REVISION)
    parser.add_argument("--tokenizer-name-or-path", default=None)
    parser.add_argument("--tokenizer-revision", default=DEFAULT_PINNED_REVISION)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--seed", default="infini_news_v1_protocols")
    parser.add_argument("--numeric-seed", type=int, default=SEED)
    parser.add_argument("--limit-per-role", type=int, default=None, help="Smoke-test per-role row cap; omit for frozen artifacts.")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-steps", type=int, default=10)
    parser.add_argument("--rank-margin", type=float, default=0.1)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--max-train-steps", type=int, default=None, help="Smoke-test cap inside each epoch.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--require-accelerator", action="store_true", help="Write a measured HOLD candidate instead of training on CPU.")
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as exc:
        failure_dir = args.output / CANDIDATE_NAME
        write_failed_candidate(failure_dir, {"reason": "exception", "error_type": type(exc).__name__, "error": str(exc), "traceback_tail": traceback.format_exc().splitlines()[-12:], "decision": "HOLD", "accelerator_probe": accelerator_probe()})
        raise
    print(json.dumps({"candidate_name": result["candidate_name"], "decision": result["decision"], "model_id": result.get("metadata", {}).get("model_id"), "artifact_sha256": result.get("metadata", {}).get("artifact_sha256")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
