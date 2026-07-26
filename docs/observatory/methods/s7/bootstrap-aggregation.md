# S7 Synthetic Aggregation Method

## Status

This document describes the bootstrap formula implementation authorized by
DR-005. It does not define a released score or an observed empirical result.

## Formula

Each unique logical document receives its bootstrap primary-level severity
divided by five. Documents are averaged within resolved employer and analytical
cell. Employer means are then combined using approved synthetic baseline-cell
weights and scaled to 0-100.

Duplicate logical IDs are idempotent only when their observations are
identical. Conflicting duplicates fail closed.

## Coverage

The production defaults suppress below 500 logical documents, 50 resolved
employers, five occupation groups, two source families, 0.80 employer
resolution, 0.80 matched baseline weight, or the effective-sample threshold.
Synthetic tests may use lower explicit thresholds to exercise formula
properties; those thresholds cannot enter a release.

## Components

Private diagnostics include:

- all six primary-level shares;
- primary pressure, required-or-stronger prevalence, and monitored or enforced
  prevalence;
- every observed mechanism prevalence;
- ambiguity, unresolved-employer, and matched-baseline rates.

The public score contract currently treats primary pressure as the headline
component with weight one and the two required prevalence components as
zero-weight diagnostics.

## Uncertainty and sensitivities

The bootstrap resamples resolved employers within eligible cells using a seed
derived from immutable run material. Bootstrap diagnostics use 2,000
replicates by default. Sensitivities include current-composition
employer-balanced, document-weighted, equal-source-family,
leave-one-source-family-out, and leave-one-occupation-group-out values.
Fixed-employer panel output remains unavailable until a real baseline panel
exists.

## Release behavior

The bootstrap projection validates against the shared score contract but nulls
all reportable values and emits registered suppression warnings. Candidate
values remain private and cannot be interpreted as employer-language evidence.
