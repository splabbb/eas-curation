# Rubric Schema v1 Design Review

Status: DRAFT FOR RATIFICATION

## Document Purpose

This document defines the authoritative Phase 1 rubric architecture for the
eas-curation repository.

It governs:

- Rubric structure
- Criterion structure
- Validation behavior
- Versioning requirements
- Disclaimer requirements
- Approval and ratification

Once ratified, this document becomes the source of truth for Phase 1
implementation.

No implementation may diverge from this schema without a new pull request or
Architecture Decision Record review cycle.

## 1. Scope

This document applies to the Phase 1 Rubric, Critique, and Integrity
foundations.

Phase 1 is additive. It must preserve the current working system.

Included:

- Rubric schema
- Criterion schema
- Validation rules
- Versioning policy
- Critique provenance requirements
- Review and ratification governance

Excluded:

- PortfolioReviewPipeline
- PortfolioReviewPipeline placeholders
- Runtime rubric integration
- CLI changes
- Cache-key or cache-format changes
- Embedding changes
- VisionAnalyzer refactoring
- TechnicalAnalyzer implementation
- ImageResult replacement
- Legacy scoring changes

## 2. Architectural Requirements

The rubric architecture shall:

1. Preserve existing repository behavior.
2. Support future portfolio-review workflows.
3. Remain independent of VisionAnalyzer.
4. Remain independent of the current hardcoded scoring calculation.
5. Support image-level and portfolio-level criteria.
6. Provide deterministic validation behavior.
7. Record schema and rubric versions in future critiques.
8. Treat the reference rubric as source-only documentation.
9. Never load the reference rubric as an automatic runtime default.

The rubric architecture shall not:

1. Alter ImageCurationPipeline.
2. Alter ImageResult.
3. Alter VisionAnalyzer scoring.
4. Alter duplicate clustering behavior.
5. Alter embedding-cache keys or formats.
6. Alter CLI behavior.

# 3. Rubric Schema

A Rubric is a versioned review framework consisting of ordered, weighted
evaluation criteria.

## 3.1 Required Rubric Fields

### schema_version

Purpose:

Identifies the structural schema understood by the parser.

Type:

Integer.

Phase 1 value:

```yaml
schema_version: 1
```

Rules:

- Required.
- Must be an integer.
- Schema Version 1 is the only supported Phase 1 version.
- Unknown schema versions must be rejected.
- Schema version is separate from rubric content version.

### rubric_id

Purpose:

Provides the permanent machine-readable identity of the rubric.

Example:

```yaml
rubric_id: magnum_informed_portfolio_review
```

Rules:

- Required.
- Must be non-empty.
- Must be unique within the repository.
- Must remain stable across rubric revisions.
- Must not be derived from the display title.

### rubric_version

Purpose:

Identifies the editorial content version of the rubric.

Example:

```yaml
rubric_version: 1.0.0
```

Rules:

- Required.
- Must use Semantic Versioning.
- Must be independent from schema_version.

### title

Purpose:

Provides a human-readable rubric title.

Rules:

- Required.
- Must be non-empty.

### description

Purpose:

Explains the rubric's editorial intent and intended use.

Rules:

- Required.
- Must be non-empty.

### scope

Purpose:

Defines the evaluation levels represented by the rubric.

Allowed values:

- image
- portfolio
- hybrid

Rules:

- Required.
- Must use exactly one supported value.
- The reference rubric shall use hybrid scope because it contains image-level
  and portfolio-level criteria.

### metadata

Purpose:

Records authorship, provenance, and scope information.

Required metadata fields:

- author
- disclaimer

Optional metadata fields:

- created_at
- updated_at
- reference_documents
- tags

Rules:

- The metadata disclaimer must contain the Magnum disclaimer defined in this
  document.
- Metadata must not contain runtime model configuration.
- Metadata must not change existing pipeline behavior.

### score_scale

Purpose:

Defines the global numeric range for criterion assessments.

Required fields:

- minimum
- maximum

Phase 1 value:

```yaml
score_scale:
  minimum: 0
  maximum: 5
```

Rules:

- Values must be finite numbers.
- Minimum must be lower than maximum.
- Criterion scores must remain inside this range.
- Score bands must remain inside this range.
- The rubric scale is separate from the legacy ImageResult score.

### aggregation

Purpose:

Defines how applicable criterion scores may be aggregated.

Phase 1 structure:

```yaml
aggregation:
  method: weighted_mean
  normalize_weights: true
```

Supported Phase 1 method:

- weighted_mean

Rules:

- Active criterion weights are normalized during aggregation.
- Criterion weights do not need to total 1.0 in the source document.
- The total weight of applicable criteria must be greater than zero.
- No additional aggregation method is supported in Schema Version 1.
- Aggregation must not mutate the original rubric or assessments.

### criteria

Purpose:

Contains the ordered list of criterion definitions.

Rules:

- Required.
- Must be a list.
- Must contain at least one criterion.
- Source order must be preserved.
- Criterion identifiers must be unique.

# 4. Criterion Schema

A Criterion represents one independently addressable evaluation dimension.

## 4.1 Required Criterion Fields

### criterion_id

Purpose:

Provides the permanent machine-readable identity of the criterion.

Example:

```yaml
criterion_id: narrative_contribution
```

Rules:

- Required.
- Must be non-empty.
- Must be unique within the rubric.
- Must remain immutable once published.
- Must not be derived dynamically from the display name.

Changing a criterion_id after publication requires a new criterion identity
and a major rubric-version change.

### name

Purpose:

Provides the human-readable display name.

Rules:

- Required.
- Must be non-empty.
- May be clarified without changing criterion identity, provided its scoring
  meaning does not change.

### level

Purpose:

Defines the level at which the criterion is assessed.

Allowed values:

- image
- portfolio

Rules:

- Required.
- Must use exactly one supported value.

### weight

Purpose:

Defines the criterion's relative importance during aggregation.

Rules:

- Required.
- Must be numeric.
- Must be finite.
- Must be non-negative.
- The total weight of applicable criteria must be greater than zero.
- Weights are normalized during aggregation.
- Source weights do not need to total 1.0.

### required

Purpose:

Indicates whether an assessment for the criterion is mandatory whenever the
criterion is applicable.

Allowed values:

- true
- false

Rules:

- Required.
- Must be Boolean.

### description

Purpose:

Defines the criterion's evaluation intent.

Rules:

- Required.
- Must be non-empty.
- Must explain what is being evaluated.
- Must not contain model configuration.
- Must not contain executable prompt instructions.

### score_bands

Purpose:

Defines human-readable interpretations of score ranges.

Each score band must include:

- minimum
- maximum
- label
- guidance

Example:

```yaml
score_bands:
  - minimum: 0
    maximum: 1
    label: weak
    guidance: The criterion is not meaningfully satisfied.

  - minimum: 2
    maximum: 3
    label: developing
    guidance: The criterion is partially satisfied.

  - minimum: 4
    maximum: 5
    label: strong
    guidance: The criterion is clearly and consistently satisfied.
```

Rules:

- Score bands must be deterministically ordered.
- Score bands must remain within the global score scale.
- Score bands must not overlap.
- Score bands must provide complete coverage when the rubric declares
  complete-band coverage.
- A band minimum must not exceed its maximum.
- Boundary ownership must be unambiguous.
- A numeric score must not match more than one score band.

## 4.2 Optional Criterion Fields

### projectbrief_fields

Purpose:

Documents which ProjectBrief fields provide context for the criterion.

Allowed Phase 1 references:

- title
- synopsis
- themes
- subjects
- locations
- visual_intent
- desired_sequence_roles
- avoid
- semantic_prompts

Rules:

- Unknown field references must fail validation.
- This field documents applicability and context.
- It does not integrate ProjectBrief into runtime scoring during Phase 1.
- The current ProjectBrief model remains authoritative for project intent.

### tags

Purpose:

Provides non-executable classification labels.

Rules:

- Optional.
- Must be a list of non-empty strings when present.

### evidence_guidance

Purpose:

Explains the evidence expected for a future assessment.

Rules:

- Optional.
- Must contain human-review guidance only.
- Must not contain executable prompts.
- Must not contain model configuration.

### gating

Purpose:

Identifies criteria that may become critical gates in a future integration
phase.

Phase 1 structure:

```yaml
gating:
  enabled: false
```

Rules:

- Optional.
- If present, enabled must be Boolean.
- Phase 1 defines the structure only.
- Phase 1 does not implement gating behavior.
- Thresholds, severities, and execution policies are deferred.

# 5. Reference Evaluation Dimensions

The reference rubric should contain the following evaluation dimensions.

These dimensions define the initial reference content. They do not alter the
current legacy scoring path.

## 5.1 Image-Level Dimensions

### technical_quality

Evaluates technical image characteristics such as focus, exposure, contrast,
dynamic range, resolution suitability, and clipping.

This criterion must not replace or modify VisionAnalyzer scoring during
Phase 1.

### composition

Evaluates framing, balance, visual hierarchy, spatial relationships, and
visual clarity.

### narrative_contribution

Evaluates whether an image contributes meaningfully to the project's story,
tension, development, or context.

### project_relevance

Evaluates alignment with the ProjectBrief, including themes, subjects,
locations, synopsis, and visual intent.

### distinctiveness

Evaluates whether an image contributes a distinct moment, perspective, visual
treatment, or narrative function.

## 5.2 Portfolio-Level Dimensions

### cohesion

Evaluates thematic and visual coherence across the selected portfolio.

### sequence_support

Evaluates how images support progression, pacing, transitions, and desired
sequence roles.

### subject_coverage

Evaluates whether the portfolio represents the intended themes, subjects,
locations, and narrative requirements.

### portfolio_integrity

Evaluates duplicate findings, provenance warnings, missing assets, and other
portfolio-level integrity signals.

Portfolio-level execution is deferred. Schema Version 1 defines these
dimensions so future integration does not require a breaking schema change.

# 6. Validation Rules

Rubric validation must be deterministic.

Invalid documents must fail validation.

No silent correction or best-effort repair is permitted.

## 6.1 Validation Result Requirements

Validation failures must:

1. Identify the affected field.
2. Include a stable machine-readable issue code.
3. Include a human-readable explanation.
4. Preserve deterministic issue ordering.
5. Avoid modifying the source document.

## 6.2 Version Validation

A rubric must fail validation when:

- schema_version is missing.
- schema_version is not an integer.
- schema_version is unsupported.
- rubric_version is missing.
- rubric_version is not valid Semantic Versioning.

## 6.3 Rubric Validation

A rubric must fail validation when:

- rubric_id is missing or empty.
- title is missing or empty.
- description is missing or empty.
- scope is unsupported.
- metadata is missing.
- the required disclaimer is missing.
- score_scale is invalid.
- aggregation method is unsupported.
- criteria is missing.
- criteria is empty.

## 6.4 Criterion Validation

A criterion must fail validation when:

- criterion_id is missing or empty.
- criterion_id duplicates another criterion.
- name is missing or empty.
- description is missing or empty.
- level is unsupported.
- weight is missing.
- weight is negative.
- weight is infinite.
- weight is NaN.
- required is not Boolean.
- score_bands is missing or empty.
- projectbrief_fields contains an unknown field.
- gating.enabled is present but is not Boolean.

## 6.5 Weight Validation

Phase 1 weight rules:

- Individual weights must be finite and non-negative.
- Source weights do not need to total 1.0.
- Applicable weights are normalized during weighted aggregation.
- The total applicable weight must be greater than zero.
- A zero applicable-weight total is a validation or aggregation error.
- Normalization must not mutate the original rubric.

The explicit absolute floating-point tolerance is:

```text
ABSOLUTE_WEIGHT_TOLERANCE = 1e-6
```

This tolerance applies to aggregate floating-point comparisons.

Relative tolerance must not silently replace this explicit absolute
tolerance.

## 6.6 Score-Band Validation

Score bands must fail validation when:

- A band minimum exceeds its maximum.
- A band falls outside the rubric score scale.
- Bands overlap.
- Bands are not deterministically ordered.
- Required scale coverage contains a gap.
- A band label is missing or empty.
- Required guidance is missing or empty.

Boundary ownership must be unambiguous. A numeric score must not match more
than one score band.

## 6.7 Applicability and Missing Context

Phase 1 defines the following future-facing rules:

- Missing optional ProjectBrief context must not crash validation.
- Unknown ProjectBrief field names must fail rubric validation.
- Applicability evaluation is deferred from the current production pipeline.
- A required criterion is mandatory only when it is applicable.
- A non-applicable criterion must not contribute to aggregate weight.
- Applicable weights must be renormalized after exclusions.

These rules define the contract but do not alter runtime scoring in Phase 1.

## 6.8 Pass, Fail, and Review Status

Future criterion assessments may use:

- PASS
- FAIL
- REVIEW
- NOT_APPLICABLE

Schema Version 1 does not impose one universal numeric pass threshold across
all criteria.

Threshold or gating behavior must be declared explicitly by a future approved
rubric revision before it affects runtime decisions.

Phase 1 must not infer pass or fail behavior from the current VisionAnalyzer
threshold.

## 6.9 Edge-Case Handling

The following conditions must produce explicit validation or assessment
outcomes:

- Empty criteria list: validation failure.
- Duplicate criterion ID: validation failure.
- Unsupported schema version: validation failure.
- Unknown ProjectBrief field: validation failure.
- Negative weight: validation failure.
- Non-finite weight: validation failure.
- Zero total applicable weight: aggregation failure.
- Missing optional context: criterion may become NOT_APPLICABLE.
- Score outside the global scale: validation failure.
- Overlapping score bands: validation failure.
- Unsupported aggregation method: validation failure.
- Unknown gating structure: validation failure.

# 7. Critique Provenance Requirements

Every future ImageCritique must record:

- schema_version
- rubric_id
- rubric_version

A critique without rubric-version provenance is invalid.

A legacy ImageResult score must not be presented as a complete rubric
critique.

Any future ImageResult-to-ImageCritique conversion must use an explicit
adapter and document information that cannot be reconstructed.

No such adapter is implemented in Phase 1.

# 8. Versioning Policy

Schema structure and rubric content use separate version systems.

## 8.1 Schema Version

schema_version controls parser and structural compatibility.

Schema Version 1 uses integer value:

```yaml
schema_version: 1
```

A new schema major version is required for:

- Removing a required field.
- Adding a required field that older parsers cannot handle.
- Changing the meaning or type of a field.
- Changing criterion identity rules.
- Changing score-band structure incompatibly.
- Changing aggregation structure incompatibly.

Unsupported schema versions must be rejected explicitly.

No implicit schema migration is permitted in Phase 1.

## 8.2 Rubric Version

rubric_version controls editorial content and uses Semantic Versioning.

### Patch Version

Example:

```text
1.0.0 to 1.0.1
```

Permitted changes:

- Spelling corrections.
- Formatting corrections.
- Non-semantic documentation clarifications.
- Metadata corrections that do not alter scoring meaning.

### Minor Version

Example:

```text
1.0.0 to 1.1.0
```

Permitted changes:

- Backward-compatible optional metadata.
- Optional guidance additions.
- New optional criteria that do not change existing results.
- Additional non-breaking tags or evidence guidance.

### Major Version

Example:

```text
1.0.0 to 2.0.0
```

Required for:

- Weight changes.
- Criterion removal.
- Criterion semantic redefinition.
- Existing criterion ID replacement.
- Score-scale changes.
- Required-criterion changes.
- Aggregation changes.
- Pass or fail threshold changes.
- Gating behavior changes that affect outcomes.

## 8.3 Architecture Decision Records

Major schema or rubric changes require an Architecture Decision Record.

Recommended path:

```text
docs/adr/XXXX-rubric-change.md
```

The ADR must record:

- Context
- Problem
- Decision
- Alternatives considered
- Compatibility impact
- Migration impact
- Reviewer
- Maintainer approval
- Approval date

## 8.4 Freeze Policy

After ratification, Schema Version 1 is frozen for Phase 1.

Changes to the following require a new pull request or ADR cycle:

- Required rubric fields
- Criterion structure
- Criterion identity rules
- Weight semantics
- Score scale
- Aggregation semantics
- Validation behavior
- Versioning policy
- Disclaimer requirements

Implementation commits must reference the ratified schema pull request,
commit, or tag.

# 9. Magnum Disclaimer

The reference rubric is independently authored.

The following disclaimer must appear in the metadata of
docs/magnum_informed_rubric.yaml:

```text
This rubric is independently authored for the eas-curation project.

It is informed by general, publicly discussed editorial portfolio-review
concepts and photographic evaluation practices.

It is not an official Magnum Photos rubric, policy, review framework,
endorsement, certification, recommendation, or publication standard.

Use of the term "Magnum-informed" indicates general editorial inspiration
only. It does not indicate affiliation, authorization, sponsorship, approval,
representation, or endorsement by Magnum Photos or any of its members.

The rubric provides configurable review guidance and does not guarantee
editorial acceptance, publication, professional recognition, legal
compliance, factual authenticity, or any particular selection outcome.

Users remain responsible for editorial decisions, rights clearance,
provenance verification, privacy obligations, and lawful use of all images
and associated metadata.
```

The disclaimer establishes scope boundaries. It must not be interpreted as a
substitute for repository licensing, legal review, rights clearance, or
provenance verification.

# 10. Source-Only Reference Rubric Policy

The reference file will be located at:

```text
docs/magnum_informed_rubric.yaml
```

It is a source-only reference artifact.

Phase 1 requirements:

- It must not be loaded automatically.
- It must not become a package-global default.
- CLI behavior must not depend on it.
- Editable installation must not depend on its runtime presence.
- Existing scoring must not depend on it.
- Tests may load it explicitly from a source checkout.
- A future packaged default requires a separate architecture decision and
  package-resource design.

# 11. Approval Block

Document:

```text
docs/rubric_schema.md
```

Schema version:

```text
1
```

Status:

```text
DRAFT FOR RATIFICATION
```

Author:

```text
Name: Nicolas Malaisé
Date: 2026-07-31
```

Reviewer:

```text
Name:
Date:
```

Maintainer:

```text
Name:
Date:
```

Ratification method:

```text
[ ] Pull request with explicit maintainer approval
[ ] Architecture Decision Record with recorded sign-off
[ ] Pinned maintainer comment identifying the ratified commit
```

Ratification references:

```text
Pull request:
ADR:
Ratified commit:
Approval comment:
```

Final decision:

```text
[ ] APPROVED FOR PHASE 1 IMPLEMENTATION
[ ] REVISIONS REQUIRED
[ ] REJECTED
```

Verified baseline:

```text
Tests: 28 passed
Coverage: 73%
Editable installation: successful
CLI help: successful
```

Binding approval statement:

```text
Approval of this document freezes Rubric Schema Version 1 for Phase 1.

All implementation must proceed commit-by-commit against this contract.

Changes to required rubric fields, criterion structure, criterion identity,
weight semantics, score scale, aggregation semantics, validation behavior,
versioning policy, or disclaimer requirements require a new pull request or
Architecture Decision Record review cycle.
```

# 12. Ratification Procedure

1. Commit this document on a documentation-only branch.
2. Open a pull request against main.
3. Verify that the pull request changes only docs/rubric_schema.md.
4. Record the verified repository baseline in the pull request.
5. Obtain explicit maintainer approval.
6. Merge the approved document into main.
7. Record the merged commit hash.
8. Optionally create an annotated rubric-schema-v1-ratified Git tag.
9. Begin Phase 1 implementation only after ratification.
