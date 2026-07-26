# S3 Synthetic Bootstrap Method

## Status

This method is synthetic implementation evidence. It makes no claim about
observed professional writing, LLM influence, document authorship, or language
quality.

## Corpus controls

Synthetic records supply explicit structural block roles. Only authored blocks
enter features. Personal contacts are removed without paraphrasing. Genre,
topic, event, entity, publisher, owner, duplicate, syndication, and revision
controls remain separate versioned fields.

## Feature families

- Lexical: baseline-fitted token distribution with an immutable vocabulary,
  other bucket, smoothing, type-token, hapax, baseline-frequency, repetition,
  and out-of-vocabulary diagnostics.
- Syntactic: transparent sentence-length and surface grammatical proxies. This
  is a bootstrap fallback, not an approved parser representation.
- Rhetorical: authored transition, hedge, booster, reference, uncertainty, and
  structural counts from a fixed registry.
- Semantic: deterministic local hashed TF-IDF fallback with immutable baseline
  inverse-document frequencies and L2 normalization.

Current-period documents cannot change baseline artifacts. Source, publisher,
entity, period, URL, and AI-likeness fields are unavailable to feature
extraction.

## Dispersion and score

Lexical and syntactic dispersion use base-2 Jensen-Shannon divergence from the
weighted centroid. Rhetorical and semantic dispersion use cosine distance from
the normalized centroid. Lower dispersion means more convergence.

Each component uses a robust baseline center and scale. Positive convergence
z-scores map above 50, negative scores below 50, and values clip to 0-100. The
bootstrap top level is the equal mean of the four component scores.

Logical duplicates contribute once. Deterministic entity and publisher caps
run before dispersion.

## Release behavior

All reportable score, baseline, change, confidence, interval, and component
values are null in the shared score contract. Candidate values remain private,
and registered experimental, benchmark, and suppression warnings are required.
