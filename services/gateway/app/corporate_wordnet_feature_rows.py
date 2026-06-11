from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from nltk.corpus import wordnet as _WORDNET_CORPUS
    from nltk.stem import WordNetLemmatizer
except Exception as exc:  # pragma: no cover - surfaced when WordNet is used.
    _WORDNET_CORPUS = None
    WordNetLemmatizer = None
    _WORDNET_IMPORT_ERROR = exc
else:
    _WORDNET_IMPORT_ERROR = None

MODEL_FEATURE_SCHEMA = "corporate.sumo_feature_row.v1"

TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?%?")

_WORDNET_DATA_INSTRUCTIONS = (
    "The NLTK WordNet corpus is not available. "
    "Install it with `python -m nltk.downloader wordnet` "
    "(or `python -m nltk.downloader -d /tmp/nltk_data wordnet` and set NLTK_DATA=/tmp/nltk_data)."
)
_WORDNET_POS_ORDER = ("n", "v", "a", "r", "s")

_ABSTRACT_THRESHOLD = 6
_CONCRETE_THRESHOLD = 9
_NO_WORDNET_MATCH = "other"
_NO_WORDNET_RELATION = "no_match"

_VAGUE_QUANTIFIERS = {
    "some",
    "many",
    "few",
    "several",
    "various",
    "multiple",
    "almost",
    "about",
    "around",
    "roughly",
}

_VAGUE_ADJECTIVES = {
    "rough",
    "possible",
    "approximate",
    "generic",
    "basic",
    "simple",
    "similar",
    "certain",
}

_MODAL_VERBS = {"can", "could", "may", "might", "must", "should", "shall", "will", "would", "might", "ought"}

_GENERIC_VERBS = {
    "be",
    "is",
    "are",
    "have",
    "do",
    "does",
    "did",
    "use",
    "utilize",
    "provide",
    "deliver",
    "enable",
    "improve",
    "increase",
    "decrease",
    "drive",
    "support",
    "offer",
    "create",
    "build",
    "make",
}

_NUMERIC_RE = re.compile(r"^\d+(?:\.\d+)?%?$")
_ENTITY_SUFFIXES = {"inc", "inc.", "llc", "ltd", "corp", "co", "corporation", "company", "group", "bank"}
_CAPITALIZED_NE_STOPWORDS = {
    "can",
    "will",
    "would",
    "should",
    "could",
    "may",
    "must",
    "mustn",
    "we",
    "i",
    "you",
    "he",
    "she",
    "they",
    "them",
    "it",
    "there",
    "this",
    "that",
    "these",
    "those",
    "the",
    "a",
    "an",
    "and",
    "or",
    "if",
    "when",
    "while",
    "for",
    "from",
    "to",
    "in",
    "on",
    "with",
    "without",
    "into",
}

_WORDNET_READY = False
_WORDNET_LEMMATIZER = WordNetLemmatizer() if WordNetLemmatizer is not None else None
_SUMO_MAPPING_FILES = {
    "n": "WordNetMappings30-noun.txt",
    "v": "WordNetMappings30-verb.txt",
    "a": "WordNetMappings30-adj.txt",
    "r": "WordNetMappings30-adv.txt",
}
_SUMO_MAPPING_RE = re.compile(r"&%([^\s|]+)\s*$")
_SUMO_TERM_RELATION_RE = re.compile(r"^(.+?)([=:+@\[\]])$")
_NO_SUMO_MAPPING = "no_sumo_mapping"


@dataclass(frozen=True)
class SumoMapping:
    term: str
    relation: str


def _wordnet() -> Any:
    if _WORDNET_IMPORT_ERROR is not None:
        raise RuntimeError(
            "NLTK is required for WordNet features but could not be imported. "
            "Install `nltk` in the gateway runtime dependencies."
        ) from _WORDNET_IMPORT_ERROR
    if _WORDNET_CORPUS is None:
        raise RuntimeError("NLTK WordNet corpus is unavailable.")

    global _WORDNET_READY
    if not _WORDNET_READY:
        try:
            _WORDNET_CORPUS.ensure_loaded()
        except LookupError as exc:
            raise RuntimeError(_WORDNET_DATA_INSTRUCTIONS) from exc
        _WORDNET_READY = True
    return _WORDNET_CORPUS


def _wordnet_lemma(token: str) -> str:
    if _WORDNET_LEMMATIZER is None:
        raise RuntimeError("NLTK WordNet lemmatizer is unavailable.")

    lowered = token.lower()
    if _NUMERIC_RE.fullmatch(lowered):
        return lowered

    for pos in _WORDNET_POS_ORDER:
        lemma = _WORDNET_LEMMATIZER.lemmatize(lowered, pos=pos)
        if lemma:
            return lemma
    return lowered


def _wordnet_depths(synset: Any) -> tuple[float, float]:
    try:
        shallow = float(synset.min_depth())
    except Exception:
        shallow = 0.0
    try:
        deep = float(synset.max_depth())
    except Exception:
        deep = shallow
    return shallow, deep


def _wordnet_category(synset: Any) -> str:
    lexname = synset.lexname()
    if lexname.startswith("noun.Tops") or lexname.startswith("verb.Tops"):
        return "abstract"
    if lexname.startswith("adj.") or lexname.startswith("sat."):
        return "generic"

    shallow, _ = _wordnet_depths(synset)
    if shallow <= _ABSTRACT_THRESHOLD:
        return "abstract"
    if shallow >= _CONCRETE_THRESHOLD:
        return "concrete"
    return "generic"


def _normalize_wordnet_lemma(name: str) -> str:
    return name.replace("_", " ").lower().strip()


def _wordnet_stats(lemma: str) -> tuple[str, float, float, str, Any]:
    wn = _wordnet()
    for pos in _WORDNET_POS_ORDER:
        for synset in wn.synsets(lemma, pos=pos):
            shallow, deep = _wordnet_depths(synset)
            return _wordnet_category(synset), shallow, deep, pos, synset
    return "other", 0.0, 0.0, _NO_WORDNET_MATCH, None


def load_wordnet_sumo_mappings(mapping_dir: Path) -> dict[tuple[str, str], SumoMapping]:
    mappings: dict[tuple[str, str], SumoMapping] = {}
    for pos, filename in _SUMO_MAPPING_FILES.items():
        path = Path(mapping_dir) / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith(";;"):
                    continue
                parts = stripped.split(maxsplit=1)
                if not parts:
                    continue
                offset = parts[0]
                if not re.fullmatch(r"\d{8}", offset):
                    continue
                marker = _SUMO_MAPPING_RE.search(stripped)
                if not marker:
                    continue
                relation = _SUMO_TERM_RELATION_RE.match(marker.group(1))
                if not relation:
                    continue
                term, relation_symbol = relation.groups()
                if term:
                    mappings[(offset, pos)] = SumoMapping(term=term, relation=relation_symbol)
    return mappings


@lru_cache(maxsize=8)
def _cached_wordnet_sumo_mappings(mapping_dir: str) -> dict[tuple[str, str], SumoMapping]:
    return load_wordnet_sumo_mappings(Path(mapping_dir))


def lookup_wordnet_sumo_mapping(
    synset: Any,
    mappings: dict[tuple[str, str], SumoMapping],
) -> SumoMapping | None:
    try:
        offset = f"{int(synset.offset()):08d}"
        pos = str(synset.pos())
    except Exception:
        return None
    return mappings.get((offset, pos))


def _wordnet_synonym_lemmas(synset: Any, lemma: str) -> list[str]:
    if synset is None:
        return []
    target = _normalize_wordnet_lemma(lemma)
    synonyms: set[str] = set()
    for synonym in synset.lemmas():
        text = _normalize_wordnet_lemma(synonym.name())
        if text and text != target:
            synonyms.add(text)
    return sorted(synonyms)


def _wordnet_antonym_lemmas(synset: Any, lemma: str) -> list[str]:
    if synset is None:
        return []
    target = _normalize_wordnet_lemma(lemma)
    antonyms: set[str] = set()
    for synonym in synset.lemmas():
        for antonym in synonym.antonyms():
            text = _normalize_wordnet_lemma(antonym.name())
            if text and text != target:
                antonyms.add(text)
    return sorted(antonyms)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not (stripped := line.strip()):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _text_fields(row: dict[str, Any]) -> str:
    for field in ("text", "normalized_text", "document_text", "content", "title"):
        value = _coerce_text(row.get(field))
        if value:
            if field == "title":
                maybe = _coerce_text(row.get("text"))
                if maybe and maybe != value:
                    return f"{value}\n{maybe}"
                return value
            return value
    return ""


def build_text_lookup(text_input: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in _read_jsonl(text_input):
        doc_id = _coerce_text(row.get("doc_id"))
        if not doc_id:
            continue
        if doc_id in lookup:
            continue
        text = _text_fields(row)
        if text:
            lookup[doc_id] = text
    return lookup


def _tokenize(text: str) -> list[str]:
    return [value.lower() for value in TOKEN_RE.findall(str(text))]


def _lemma(token: str) -> str:
    token = token.lower()
    if _NUMERIC_RE.fullmatch(token):
        return token
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _is_numeric(token: str) -> bool:
    return bool(_NUMERIC_RE.fullmatch(token))


def _is_numeric_specific(token: str) -> bool:
    if "%" in token:
        return True
    if "." in token:
        return True
    digits = token.replace(".", "").replace("%", "")
    return len(digits) >= 4 and digits.isdigit()


def _is_named_entityish(token: str, tokens: list[str], index: int) -> bool:
    if not token:
        return False
    lowered = token.lower()
    raw_tokens = [tok for tok in tokens if tok]
    if lowered in _CAPITALIZED_NE_STOPWORDS:
        return False
    if len(token) <= 1:
        return False
    if token.isupper():
        return len(token) > 1 and token.isalpha()
    if token[0].isupper():
        if lowered in _ENTITY_SUFFIXES:
            return True
        if index > 0 and tokens[index - 1] and tokens[index - 1][0].isupper():
            return True
        if index + 1 < len(raw_tokens) and raw_tokens[index + 1] and raw_tokens[index + 1][0].isupper():
            return True
        return token.isalpha() and lowered not in _CAPITALIZED_NE_STOPWORDS
    return False


def _analyze_text(
    text: str,
    sumo_mappings: dict[tuple[str, str], SumoMapping] | None = None,
) -> tuple[dict[str, float | int], dict[str, list[Any]]]:
    tokens = _tokenize(text)
    if not tokens:
        return (
            {
                "wordnet_text_present": 0,
                "wordnet_token_count": 0,
                "wordnet_lemma_count": 0,
                "wordnet_distinct_lemma_count": 0,
                "wordnet_abstract_lexicon_count": 0,
                "wordnet_generic_lexicon_count": 0,
                "wordnet_concrete_lexicon_count": 0,
                "wordnet_abstract_lexicon_ratio": 0.0,
                "wordnet_generic_lexicon_ratio": 0.0,
                "wordnet_concrete_lexicon_ratio": 0.0,
                "wordnet_vague_quantifier_count": 0,
                "wordnet_vague_quantifier_ratio": 0.0,
                "wordnet_vague_adjective_count": 0,
                "wordnet_vague_adjective_ratio": 0.0,
                "wordnet_modal_verb_count": 0,
                "wordnet_modal_verb_ratio": 0.0,
                "wordnet_generic_verb_count": 0,
                "wordnet_generic_verb_ratio": 0.0,
                "wordnet_named_entityish_count": 0,
                "wordnet_named_entityish_ratio": 0.0,
                "wordnet_numeric_count": 0,
                "wordnet_numeric_specificity_count": 0,
                "wordnet_numeric_specificity_ratio": 0.0,
                "wordnet_ontology_match_ratio": 0.0,
                "wordnet_pseudo_depth_shallow_mean": 0.0,
                "wordnet_pseudo_depth_deep_mean": 0.0,
                "wordnet_synonym_match_count": 0,
                "wordnet_synonym_match_ratio": 0.0,
                "wordnet_antonym_match_count": 0,
                "wordnet_antonym_match_ratio": 0.0,
                "wordnet_sumo_mapping_count": 0,
                "wordnet_sumo_mapping_ratio": 0.0,
                "wordnet_sumo_equivalence_count": 0,
                "wordnet_sumo_subsumed_count": 0,
                "wordnet_sumo_instance_count": 0,
                "wordnet_sumo_complement_count": 0,
            },
            {
                "wordnet_token_sequence": [],
                "wordnet_lemma_sequence": [],
                "wordnet_category_sequence": [],
                "wordnet_pos_sequence": [],
                "wordnet_lexname_sequence": [],
                "wordnet_synset_sequence": [],
                "wordnet_sumo_term_sequence": [],
                "wordnet_sumo_relation_sequence": [],
                "wordnet_synonym_match_sequence": [],
                "wordnet_antonym_match_sequence": [],
            },
        )

    lemmas = []
    categories: list[str] = []
    pos_sequence: list[str] = []
    lexname_sequence: list[str] = []
    synset_sequence: list[str] = []
    sumo_term_sequence: list[str] = []
    sumo_relation_sequence: list[str] = []
    synonym_match_sequence: list[str] = []
    antonym_match_sequence: list[str] = []
    abstract_count = 0
    generic_count = 0
    concrete_count = 0
    synonym_match_count = 0
    antonym_match_count = 0
    sumo_mapping_count = 0
    sumo_equivalence_count = 0
    sumo_subsumed_count = 0
    sumo_instance_count = 0
    sumo_complement_count = 0
    vague_quantifier_count = 0
    vague_adjective_count = 0
    modal_count = 0
    generic_verb_count = 0
    named_entityish_count = 0
    numeric_count = 0
    numeric_specificity_count = 0
    pseudo_shallow_sum = 0.0
    pseudo_deep_sum = 0.0
    ontology_token_count = 0

    # Keep original casing for a small NE heuristic; the simple token stream is
    # lowercased for robust deterministic lexical matching.
    raw_tokens = [m.group(0) for m in TOKEN_RE.finditer(text)]

    for index, raw_token in enumerate(raw_tokens):
        lemma_token = _wordnet_lemma(raw_token)
        lemmas.append(lemma_token)
        category, shallow, deep, pos, synset = _wordnet_stats(lemma_token)
        categories.append(category)
        pos_sequence.append(pos)
        if synset is not None:
            lexname_sequence.append(synset.lexname())
            synset_sequence.append(synset.name())
            synonyms = _wordnet_synonym_lemmas(synset, lemma_token)
            sumo_mapping = lookup_wordnet_sumo_mapping(synset, sumo_mappings) if sumo_mappings else None
            if sumo_mapping is not None:
                sumo_mapping_count += 1
                sumo_term_sequence.append(sumo_mapping.term)
                sumo_relation_sequence.append(sumo_mapping.relation)
                if sumo_mapping.relation == "=":
                    sumo_equivalence_count += 1
                elif sumo_mapping.relation == "+":
                    sumo_subsumed_count += 1
                elif sumo_mapping.relation == "@":
                    sumo_instance_count += 1
                elif sumo_mapping.relation in {":", "[", "]"}:
                    sumo_complement_count += 1
            else:
                sumo_term_sequence.append(_NO_SUMO_MAPPING)
                sumo_relation_sequence.append(_NO_SUMO_MAPPING)
            antonyms = _wordnet_antonym_lemmas(synset, lemma_token)
            if synonyms:
                synonym_match_count += 1
                synonym_match_sequence.append(synonyms[0])
            else:
                synonym_match_sequence.append(_NO_WORDNET_RELATION)

            if antonyms:
                antonym_match_count += 1
                antonym_match_sequence.append(antonyms[0])
            else:
                antonym_match_sequence.append(_NO_WORDNET_RELATION)
        else:
            lexname_sequence.append(_NO_WORDNET_MATCH)
            synset_sequence.append(_NO_WORDNET_MATCH)
            sumo_term_sequence.append(_NO_SUMO_MAPPING)
            sumo_relation_sequence.append(_NO_SUMO_MAPPING)
            synonym_match_sequence.append(_NO_WORDNET_RELATION)
            antonym_match_sequence.append(_NO_WORDNET_RELATION)

        if category == "abstract":
            abstract_count += 1
            ontology_token_count += 1
            pseudo_shallow_sum += shallow
            pseudo_deep_sum += deep
        elif category == "generic":
            generic_count += 1
            ontology_token_count += 1
            pseudo_shallow_sum += shallow
            pseudo_deep_sum += deep
        elif category == "concrete":
            concrete_count += 1
            ontology_token_count += 1
            pseudo_shallow_sum += shallow
            pseudo_deep_sum += deep

        if lemma_token in _VAGUE_QUANTIFIERS:
            vague_quantifier_count += 1

        if lemma_token in _VAGUE_ADJECTIVES:
            vague_adjective_count += 1

        if lemma_token in _MODAL_VERBS:
            modal_count += 1

        if lemma_token in _GENERIC_VERBS:
            generic_verb_count += 1

        if _is_named_entityish(raw_token, raw_tokens, index):
            named_entityish_count += 1

        if _is_numeric(lemma_token):
            numeric_count += 1
            if _is_numeric_specific(lemma_token):
                numeric_specificity_count += 1

    token_count = len(tokens)
    features = {
        "wordnet_text_present": 1,
        "wordnet_token_count": token_count,
        "wordnet_lemma_count": len(lemmas),
        "wordnet_distinct_lemma_count": len(set(lemmas)),
        "wordnet_abstract_lexicon_count": abstract_count,
        "wordnet_generic_lexicon_count": generic_count,
        "wordnet_concrete_lexicon_count": concrete_count,
        "wordnet_abstract_lexicon_ratio": _ratio(abstract_count, token_count),
        "wordnet_generic_lexicon_ratio": _ratio(generic_count, token_count),
        "wordnet_concrete_lexicon_ratio": _ratio(concrete_count, token_count),
        "wordnet_vague_quantifier_count": vague_quantifier_count,
        "wordnet_vague_quantifier_ratio": _ratio(vague_quantifier_count, token_count),
        "wordnet_vague_adjective_count": vague_adjective_count,
        "wordnet_vague_adjective_ratio": _ratio(vague_adjective_count, token_count),
        "wordnet_modal_verb_count": modal_count,
        "wordnet_modal_verb_ratio": _ratio(modal_count, token_count),
        "wordnet_generic_verb_count": generic_verb_count,
        "wordnet_generic_verb_ratio": _ratio(generic_verb_count, token_count),
        "wordnet_named_entityish_count": named_entityish_count,
        "wordnet_named_entityish_ratio": _ratio(named_entityish_count, token_count),
        "wordnet_numeric_count": numeric_count,
        "wordnet_numeric_specificity_count": numeric_specificity_count,
        "wordnet_numeric_specificity_ratio": _ratio(numeric_specificity_count, numeric_count),
        "wordnet_ontology_match_ratio": _ratio(ontology_token_count, token_count),
        "wordnet_pseudo_depth_shallow_mean": _ratio(pseudo_shallow_sum, ontology_token_count),
        "wordnet_pseudo_depth_deep_mean": _ratio(pseudo_deep_sum, ontology_token_count),
        "wordnet_synonym_match_count": synonym_match_count,
        "wordnet_synonym_match_ratio": _ratio(synonym_match_count, token_count),
        "wordnet_antonym_match_count": antonym_match_count,
        "wordnet_antonym_match_ratio": _ratio(antonym_match_count, token_count),
        "wordnet_sumo_mapping_count": sumo_mapping_count,
        "wordnet_sumo_mapping_ratio": _ratio(sumo_mapping_count, token_count),
        "wordnet_sumo_equivalence_count": sumo_equivalence_count,
        "wordnet_sumo_subsumed_count": sumo_subsumed_count,
        "wordnet_sumo_instance_count": sumo_instance_count,
        "wordnet_sumo_complement_count": sumo_complement_count,
    }

    return features, {
        "wordnet_token_sequence": tokens,
        "wordnet_lemma_sequence": lemmas,
        "wordnet_category_sequence": categories,
        "wordnet_pos_sequence": pos_sequence,
        "wordnet_lexname_sequence": lexname_sequence,
        "wordnet_synset_sequence": synset_sequence,
        "wordnet_sumo_term_sequence": sumo_term_sequence,
        "wordnet_sumo_relation_sequence": sumo_relation_sequence,
        "wordnet_synonym_match_sequence": synonym_match_sequence,
        "wordnet_antonym_match_sequence": antonym_match_sequence,
    }


def transform_wordnet_feature_row(
    record: dict[str, Any],
    text_lookup: dict[str, str],
    *,
    sumo_mapping_dir: Path | None = None,
) -> dict[str, Any]:
    doc_id = _coerce_text(record.get("doc_id"))
    text = _coerce_text(record.get("text"))
    if not text and doc_id:
        text = _coerce_text(text_lookup.get(doc_id))

    features = record.get("features")
    if not isinstance(features, dict):
        features = {}

    sumo_mappings = _cached_wordnet_sumo_mappings(str(sumo_mapping_dir)) if sumo_mapping_dir is not None else None
    lexical_features, sequences = _analyze_text(text, sumo_mappings=sumo_mappings)
    output = dict(record)
    merged_features = dict(features)
    merged_features.update(lexical_features)
    output["features"] = merged_features
    output.update(sequences)
    return output


def transform_wordnet_jsonl(
    features_input: Path,
    text_input: Path,
    output: Path,
    *,
    limit: int | None = None,
    sumo_mapping_dir: Path | None = None,
) -> int:
    feature_rows = _read_jsonl(features_input)
    if limit is not None:
        feature_rows = feature_rows[:limit]

    text_lookup = build_text_lookup(text_input)
    out_rows: list[dict[str, Any]] = []
    for row in feature_rows:
        if isinstance(row, dict):
            out_rows.append(transform_wordnet_feature_row(row, text_lookup, sumo_mapping_dir=sumo_mapping_dir))
    _write_jsonl(out_rows, output)
    return len(out_rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add lightweight ontology-style lexical features to SUMO feature rows.")
    parser.add_argument("--features-input", type=Path, required=True, help="SUMO feature-row JSONL file.")
    parser.add_argument("--text-input", type=Path, required=True, help="Normalized corpus JSONL containing doc_id + text.")
    parser.add_argument("--output", type=Path, required=True, help="Output enriched feature-row JSONL path.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to process.")
    parser.add_argument(
        "--sumo-mapping-dir",
        type=Path,
        default=None,
        help="Optional directory containing WordNetMappings30-*.txt files for WordNet→SUMO enrichment.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rows = transform_wordnet_jsonl(
        args.features_input,
        args.text_input,
        args.output,
        limit=args.limit,
        sumo_mapping_dir=args.sumo_mapping_dir,
    )
    print(
        json.dumps(
            {
                "features_input": str(args.features_input),
                "text_input": str(args.text_input),
                "output": str(args.output),
                "sumo_mapping_dir": str(args.sumo_mapping_dir) if args.sumo_mapping_dir else None,
                "rows": rows,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
