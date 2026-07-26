# MVP Benchmark Synthetic Framework

## Status

This is a framework bootstrap under DR-007. It has no real benchmark text or
human labels and does not validate S7, S3, or any public score.

## Implemented controls

- Benchmark groups are the transitive union of logical-document, duplicate,
  revision, template-family, and pair-family identifiers.
- Whole groups receive deterministic development, validation, or final splits.
- A zero-overlap audit blocks any group present in more than one split.
- Annotation rows are append-only. Adjudication requires two distinct
  annotators and cannot overwrite a prior decision.
- Final labels are exposed only to the evaluator role and every read is
  recorded.
- The protected evaluator accepts predictions rather than candidate code.
- Candidate, benchmark manifest, prediction, artifact, and freeze-record
  checksums or identifiers must match before labels are read.
- Exact item coverage is required.
- A candidate lineage and its declared ancestors may consume one benchmark
  major version once.
- Gate definitions are immutable values supplied to the evaluator.
- Public packets expose aggregate metrics and gate results through an
  allowlist. Private object IDs, raw text, labels, annotation notes, identities,
  credentials, and filesystem paths are rejected.

## Synthetic evidence

Automated tests cover deterministic transitive splits, overlap rejection,
double annotation, append-only adjudication, label-role isolation, a reference
passing candidate, a reference failing candidate, malformed submissions,
lineage reuse, and public item hygiene.

The reference candidate results are fixture assertions only. They are not
benchmark scores.

## Remaining gates

Human execution requires approved source rights, source composition, annotator
qualification, protected production storage, final task design, final
thresholds, independence review, and frozen non-overlapping manifests. Those
requirements remain open in IS-006 and ES-009.
