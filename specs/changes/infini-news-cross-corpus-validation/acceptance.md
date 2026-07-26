# Acceptance criteria

## V1 immutability

- [ ] Selected model ID is unchanged.
- [ ] Artifact SHA-256 is unchanged.
- [ ] Threshold is unchanged.
- [ ] No INFINI frozen test row becomes training/tuning data.

## January 2024 diagnostic

- [ ] Recomputes the 951-row January 2024 accuracy of approximately 60.99% from frozen predictions.
- [ ] Reports source/topic/length/missing-author/error concentration without article text.
- [ ] Compares December 2023, January 2024, February 2024, remainder of 2024, and overall test.
- [ ] Clearly distinguishes diagnosis from model selection or tuning.

## External source

- [ ] Independent of INFINI and OpenAlex.
- [ ] Source revision/snapshot and schema are pinned.
- [ ] Temporal label comes from actual article publication date.
- [ ] Crawl/WARC/archive/partition dates are not substituted.
- [ ] Raw text remains local/private.

## External evaluation

- [ ] Uses unchanged v1 artifact and threshold.
- [ ] Deterministic sample and global dedupe are documented.
- [ ] Reports full metrics, confidence intervals, time groups, and confound slices.
- [ ] Public outputs contain no raw/normalized article text.
- [ ] PASS/HOLD/REJECT follows predeclared gates without post-hoc threshold changes.

## Repository and release

- [ ] Focused tests pass.
- [ ] Checksum manifests pass.
- [ ] Worktree is clean after commits.
- [ ] GitHub PR exists and is verified with `gh pr view`.
- [ ] No deployment or production integration occurred.

Mandatory wording: “This score does not establish AI authorship.”
