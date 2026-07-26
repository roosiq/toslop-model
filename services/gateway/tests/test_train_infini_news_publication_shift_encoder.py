import json

import pytest
import torch

from train_infini_news_publication_shift_encoder import (
    CANDIDATE_NAME,
    DISCLAIMER,
    TextOnlyCollator,
    accelerator_probe,
    build_examples,
    recency_pair_accuracy,
    regression_metrics,
    write_failed_candidate,
    year_to_target,
)
from train_infini_news_publication_shift_candidates import assert_public_safe


class _Tokenizer:
    def __call__(self, texts, padding, truncation, max_length, return_tensors):
        assert padding is True
        assert truncation is True
        assert max_length == 16
        assert return_tensors == "pt"
        # The collator must pass only raw text strings into the tokenizer.
        assert texts == ["old article text", "new article text"]
        return {
            "input_ids": torch.tensor([[1, 2, 0], [1, 3, 4]], dtype=torch.long),
            "attention_mask": torch.tensor([[1, 1, 0], [1, 1, 1]], dtype=torch.long),
        }


def _row(document_id: str, role: str, text: str, year: int):
    return {
        "document_id": document_id,
        "corpus_role": role,
        "normalized_text": text,
        "publication_year": year,
        "publication_month": 1,
        "publication_year_month": f"{year}-01",
        "url_hostname": "example.com",
        "sitename": "Example News",
        "topic": "technology",
        "author_hash": "a1",
        "identity_hash": f"identity-{document_id}",
        "normalized_text_sha256": f"text-{document_id}",
        "near_duplicate_cluster_id": f"cluster-{document_id}",
        "word_count": len(text.split()),
    }


def test_text_only_collator_uses_text_not_metadata_and_builds_multitask_targets():
    rows = [
        _row("old", "pre_llm_core", "old article text", 2019),
        _row("new", "current_core", "new article text", 2025),
        _row("eval", "forward_2026", "eval only text", 2026),
    ]

    examples = build_examples(rows)
    batch = TextOnlyCollator(_Tokenizer(), max_length=16)(examples)

    assert [example.document_id for example in examples] == ["old", "new"]
    assert batch["era_labels"].tolist() == [0, 1]
    assert batch["year_targets"].tolist() == pytest.approx([year_to_target(2019), year_to_target(2025)])
    assert batch["pair_indices"].tolist() == [[0.0, 1.0, -1.0]]
    assert batch["document_ids"] == ["old", "new"]
    assert "url_hostname" not in batch
    assert "sitename" not in batch


def test_encoder_metrics_cover_year_regression_and_pairwise_recency():
    years = torch.tensor([2018, 2020, 2025], dtype=torch.float32).numpy()
    good_predictions = torch.tensor([2018.5, 2020.5, 2024.0], dtype=torch.float32).numpy()
    bad_predictions = torch.tensor([2025.0, 2020.0, 2018.0], dtype=torch.float32).numpy()

    regression = regression_metrics(years, good_predictions)
    good_rank = recency_pair_accuracy(years, good_predictions)
    bad_rank = recency_pair_accuracy(years, bad_predictions)

    assert regression["count"] == 3
    assert regression["mae_years"] == pytest.approx(2.0 / 3.0)
    assert good_rank == {"pair_count": 3, "accuracy": 1.0}
    assert bad_rank == {"pair_count": 3, "accuracy": 0.0}


def test_accelerator_probe_is_explicit_and_does_not_claim_unverified_gpu():
    probe = accelerator_probe()

    assert "cuda_available" in probe
    assert "torch_hip_version" in probe
    assert probe["selected_device"] in {"cpu", "cuda"}
    if not probe["verified"]:
        assert probe["selected_device"] == "cpu"


def test_failed_candidate_record_is_public_safe_and_preserves_hold(tmp_path):
    out = tmp_path / CANDIDATE_NAME

    write_failed_candidate(out, {"reason": "accelerator_required_but_not_verified", "decision": "HOLD", "accelerator_probe": {"selected_device": "cpu"}})

    payload = json.loads((out / "FAILED_CANDIDATE.json").read_text())
    assert payload["decision"] == "HOLD"
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["reason"] == "accelerator_required_but_not_verified"
    assert_public_safe(payload)
    assert "Decision: `HOLD`" in (out / "MODEL_CARD.md").read_text()
