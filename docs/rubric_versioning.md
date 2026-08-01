# Rubric Versioning Policy

Status: PROPOSED FOR PHASE 1 APPROVAL

## 1. Purpose and Scope

This document defines the authoritative versioning, compatibility, migration, deprecation, release, and governance policy for rubrics governed by Rubric Schema Version 1 in the eas-curation repository.

This policy is Phase 1, Step 2 of the Magnum-informed foundation roadmap. It is a documentation-only policy. It does not implement runtime rubric integration, compatibility adapters, review-engine behavior, automatic reference-rubric loading, model prompts, LLM configuration, scoring changes, cache changes, CLI changes, or packaging changes.

This policy MUST be interpreted consistently with `docs/rubric_schema.md`. If this document appears to conflict with that ratified contract, the ratified schema controls until an approved amendment resolves the conflict.

## 2. Normative Terminology

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are normative requirements.

For this policy:

- **Published** means released, merged for supported use, or used to produce a critique or other durable evaluation record.
- **Parser compatibility** means whether a parser can structurally validate and interpret a rubric's `schema_version` without implicit repair or migration.
- **Editorial rubric compatibility** means whether a rubric revision preserves the meaning and expected outcomes of an earlier revision with the same `rubric_id`.
- **Existing result** means a score, status, gate, aggregation, or critique that can be produced under a published rubric revision.
- **Migration mapping** means an explicit, reviewable record that maps old identities or values to replacements and states what cannot be reconstructed without reevaluation.
- **Supported-version window** means the explicitly recorded set or range of schema and rubric versions accepted for a defined use.

## 3. Relationship Between `schema_version` and `rubric_version`

Every released rubric MUST record all of the following required provenance:

```yaml
schema_version: 1
rubric_id: example_rubric
rubric_version: 1.0.0
```

`schema_version` and `rubric_version` are independent:

- `schema_version` identifies parser and structural compatibility.
- `rubric_version` identifies the editorial content version of one stable `rubric_id`.
- A change to one version does not automatically require a change to the other.
- A version change MUST be selected from the actual compatibility impact. It MUST NOT be selected merely to avoid migration, deprecation, or review obligations.

A parser that supports a schema does not thereby guarantee editorial compatibility between two rubric versions. Conversely, an editorially modest change cannot make an unsupported schema version parser-compatible.

Future critiques MUST preserve the exact `schema_version`, `rubric_id`, and `rubric_version` used to produce them. They MUST NOT substitute a newer rubric version as if it had produced an earlier result.

## 4. Integer Schema-Version Policy

`schema_version` MUST be an integer. Rubric Schema Version 1 uses:

```yaml
schema_version: 1
```

Rubric Schema Version 1 is the only supported Phase 1 schema version. A missing, non-integer, or unsupported `schema_version` MUST be rejected explicitly. Phase 1 MUST NOT perform implicit schema migration, silent correction, or best-effort repair.

A new integer schema version is REQUIRED for an incompatible structural change, including:

- changing a schema field's type incompatibly;
- adding a required schema field that older parsers cannot handle;
- removing a required schema field;
- changing a field's structural meaning incompatibly;
- changing criterion identity rules;
- changing score-band structure incompatibly; or
- changing aggregation structure incompatibly.

A new schema version does not by itself classify the editorial change to a particular rubric. If a rubric's scoring meaning also changes, its `rubric_version` MUST be incremented independently under this policy.

## 5. Semantic Rubric-Version Policy

`rubric_version` MUST follow Semantic Versioning in `MAJOR.MINOR.PATCH` form. For a stable `rubric_id`:

- increment **PATCH** for backward-compatible, non-semantic corrections;
- increment **MINOR** for backward-compatible additive editorial changes; and
- increment **MAJOR** for incompatible scoring, interpretation, identity, or outcome changes.

A released version MUST NOT be reused for different content. Each released rubric revision MUST have a unique combination of `rubric_id` and `rubric_version`.

When a change contains multiple classes, the highest required class controls.

## 6. Patch-Version Changes

A PATCH increment is REQUIRED when all changes are backward-compatible and do not alter scoring meaning, applicability, evidence expectations, evaluation outcomes, or provenance identity.

PATCH changes include:

- spelling corrections;
- formatting corrections;
- non-semantic documentation clarifications; and
- metadata corrections that do not alter scoring meaning or provenance identity.

A wording change is not PATCH merely because it is presented as editorial. If it changes what a criterion evaluates or how a score is interpreted, it is a MAJOR change.

## 7. Minor-Version Changes

A MINOR increment is REQUIRED for backward-compatible, optional additions that preserve all existing valid results and interpretations.

MINOR changes include:

- adding optional non-scoring metadata permitted by the active schema;
- adding optional human-review guidance;
- adding non-breaking tags or `evidence_guidance`; and
- adding an optional criterion only when existing results remain valid and unchanged.

An optional criterion addition qualifies as MINOR only when its omission does not invalidate prior assessments, alter prior normalized weights or aggregate results, introduce pass, fail, review, or gating effects, or change the meaning of existing criteria. Otherwise, the change is MAJOR.

A MINOR change MUST NOT introduce a new schema field absent from the active schema. Structural extensibility requires an independently approved schema change.

## 8. Major-Version Changes

A MAJOR increment is REQUIRED whenever a rubric revision can change an existing result, scoring interpretation, required evidence, applicability, identity, aggregation, or decision outcome.

MAJOR changes include:

- changing a criterion weight;
- changing a criterion's `required` status;
- removing a criterion;
- semantically redefining a criterion;
- replacing a published `criterion_id`;
- changing the score scale;
- changing aggregation semantics;
- changing score-band boundaries or guidance in a way that changes score interpretation;
- changing pass, fail, or review thresholds or behavior; and
- changing gating behavior in a way that affects outcomes.

A major rubric revision MAY remain on `schema_version: 1` when its structure still conforms to the frozen Schema Version 1 contract. A structurally incompatible change requires a new schema version as well as any independently required rubric-version change.

## 9. Criterion-ID Immutability

A published `criterion_id` is immutable. It MUST NOT be renamed, recycled, or reassigned to a different meaning.

A display-name clarification MAY retain the identity only when the criterion's scoring meaning is unchanged. A renamed or redefined criterion whose meaning changes MUST receive a new `criterion_id` and a MAJOR rubric-version increment.

Replacement of a published `criterion_id` requires:

1. a new criterion identity;
2. a MAJOR rubric-version increment;
3. a migration mapping from the old identity to the new identity;
4. an explanation of semantic differences; and
5. a statement identifying results that require reevaluation or cannot be reconstructed.

Deleted identifiers MUST remain reserved and MUST NOT be reused.

## 10. Backward-Compatibility Policy

Parser compatibility and editorial rubric compatibility MUST be evaluated and recorded separately.

A change is parser-backward-compatible only when documents valid under the supported prior schema remain structurally interpretable under the stated parser contract. Phase 1 recognizes only Schema Version 1 and performs no implicit migration.

A rubric revision is editorially backward-compatible only when previously valid assessments remain valid, retain the same meaning, and preserve their results without reevaluation. PATCH and MINOR revisions MUST satisfy that standard. MAJOR revisions are not presumed editorially backward-compatible.

Compatibility claims SHOULD identify the compared versions and the evidence supporting the claim. A parser accepting two rubric files MUST NOT be treated as proof that their editorial outcomes are compatible.

## 11. Forward-Compatibility Policy

Phase 1 parsers and validators MUST NOT assume that an unknown `schema_version` is forward-compatible. Unsupported schema versions MUST be rejected explicitly.

Consumers MUST NOT ignore unknown required structures, reinterpret unknown fields, or silently downgrade a rubric to Schema Version 1. A future schema version MAY define explicit forward-compatibility behavior only through a new approved schema and review cycle.

Editorial consumers MUST use the exact released rubric version required by a critique, workflow, or reproducibility claim. A newer version MUST NOT be substituted unless the consuming process explicitly permits that supported-version window and records the actual version used.

## 12. Supported-Version Policy

During Phase 1:

- the only supported schema version is integer `1`;
- all other schema versions MUST be rejected explicitly; and
- there is no implicit schema migration.

Each released rubric or consuming workflow MUST record its supported-version window in release documentation, an ADR, or another repository-controlled record. The record MUST identify:

- supported `schema_version` values;
- supported `rubric_id` values;
- accepted `rubric_version` values or ranges;
- the support start date or release;
- any announced end-of-support date or release;
- the responsible maintainer; and
- links or paths to applicable deprecation notices and migration mappings.

A supported-version window MUST NOT be inferred only from whatever a parser happens to accept. If no rubric-version range is declared, consumers MUST use an exact `rubric_version` match.

## 13. Migration Policy

No implicit schema migration is allowed in Phase 1. Unsupported schemas MUST be rejected before rubric content is interpreted.

Any future explicit migration MUST be separately designed, reviewed, and approved. This document does not implement a compatibility adapter.

When a released change requires migration, the release MUST provide a repository-controlled migration record containing:

- source and target `schema_version`, `rubric_id`, and `rubric_version`;
- field, criterion, score, or status mappings;
- deprecated and replacement identifiers;
- lossy transformations and information that cannot be reconstructed;
- whether reevaluation is required;
- validation and rollback instructions; and
- the approving PR or ADR.

Migration mappings MUST be explicit and deterministic. They MUST NOT rewrite historical critique provenance. Historical records retain the exact rubric provenance that produced them.

## 14. Deprecation Policy

Deprecation is an announcement, not removal and not implicit migration. A deprecated supported version remains supported until the recorded end of its support window.

A deprecation notice MUST be stored in repository-controlled release notes, an ADR, or a dedicated documentation record and MUST identify:

- the deprecated schema version, rubric version, field, or criterion identity;
- the reason for deprecation;
- the recommended replacement, if any;
- the migration mapping or its repository path;
- the announcement date;
- the earliest removal or end-of-support release;
- compatibility and reevaluation impacts; and
- the approving maintainer and PR or ADR.

Published `criterion_id` values remain immutable after deprecation. A replacement uses a new identity. Deprecation MUST NOT introduce outcome-changing behavior without the required MAJOR increment and governance review.

## 15. Architecture Decision Record Requirements

Major structural or semantic changes require a new PR or ADR review cycle. Major schema changes and major rubric changes MUST have an ADR unless the ratified governing record explicitly approves an equivalent documented review path.

The recommended ADR path is:

```text
docs/adr/XXXX-rubric-change.md
```

An ADR MUST record:

- context and problem;
- decision;
- alternatives considered;
- parser-compatibility impact;
- editorial-compatibility impact;
- migration impact and mappings;
- deprecation and supported-version-window impact;
- critique-provenance impact;
- reviewer;
- maintainer approval; and
- approval date.

An ADR does not waive required schema validation, version increments, migration records, or release approval.

## 16. Release and Approval Responsibilities

The change author MUST classify the change, update the appropriate independent version or versions, provide compatibility and migration analysis, preserve stable identities, and ensure released artifacts record complete provenance.

The reviewer MUST verify consistency with `docs/rubric_schema.md`, version classification, parser and editorial compatibility as separate concerns, required mappings and notices, and the absence of implicit runtime or schema behavior.

The maintainer MUST approve supported-version windows, major changes, deprecation deadlines, migrations, and releases. Approval MUST reference the exact reviewed commit.

A release MUST NOT be represented as approved before the required review is recorded and the approved commit is identifiable.

## 17. Change-Classification Examples

| Change | Required classification | Additional requirement |
| --- | --- | --- |
| Spelling or formatting correction | PATCH | Meaning and outcomes must remain unchanged. |
| Non-semantic documentation clarification | PATCH | Must not alter scoring interpretation. |
| Optional non-scoring metadata addition | MINOR | Metadata must already be permitted by the schema. |
| Optional guidance addition | MINOR | Must remain human-review guidance and preserve outcomes. |
| Optional criterion addition that preserves existing results | MINOR | Prior validity, normalized weights, aggregates, and decisions must remain unchanged. |
| Criterion weight change | MAJOR | Record compatibility and reevaluation impact. |
| Criterion required-status change | MAJOR | Record applicability and assessment impact. |
| Criterion semantic redefinition | MAJOR | Assign a new identity when meaning changes. |
| Published `criterion_id` replacement | MAJOR | Provide a new identity and migration mapping. |
| Score-scale change | MAJOR | Also use a new schema version if the structure changes incompatibly. |
| Aggregation-semantic change | MAJOR | Also use a new schema version if the aggregation structure changes incompatibly. |
| Pass, fail, or gating behavior change | MAJOR | Record outcome and reevaluation impact. |
| Incompatible schema field type change | New schema version | Independently increment affected rubric versions as required. |
| Add incompatible required schema field | New schema version | No implicit migration is permitted. |
| Remove incompatible required schema field | New schema version | Provide explicit migration planning. |

## 18. Invalid or Prohibited Versioning Practices

The following practices are prohibited:

- using a non-integer `schema_version`;
- accepting an unsupported schema version silently;
- performing implicit schema migration in Phase 1;
- treating `schema_version` and `rubric_version` as one coupled counter;
- overwriting or reusing a released `rubric_version` for different content;
- changing content without changing the required version;
- selecting a lower version class merely to avoid migration, deprecation, or review obligations;
- replacing, recycling, or semantically reassigning a published `criterion_id`;
- calling an outcome-changing criterion addition optional to classify it as MINOR;
- claiming editorial compatibility solely because a parser accepts both versions;
- substituting newer rubric provenance in a historical critique;
- silently correcting invalid version fields;
- inventing a schema field absent from the ratified contract; and
- using this policy to introduce runtime scoring, gating, adapter, CLI, cache, packaging, prompt, or model-configuration behavior.

## 19. Ratified Schema v1 Provenance

```text
Authoritative schema:
docs/rubric_schema.md

Ratification PR:
#2

Approved source commit:
3bbdb2240f182fabb25e4a02a27e878a94a595af

Ratified merge commit:
db85599

Ratification tag:
rubric-schema-v1-ratified
```

The ratification tag resolves to the merge commit containing the approved source commit on `main`. This policy does not alter the ratified schema.

## 20. Maintenance Checklist

For every proposed schema or rubric change, maintainers and reviewers MUST verify:

- [ ] The change is compared with the exact released source version.
- [ ] Parser compatibility and editorial compatibility are assessed separately.
- [ ] `schema_version` remains an integer.
- [ ] Unsupported schema versions are rejected explicitly.
- [ ] The required schema-version change is applied, if any.
- [ ] The required PATCH, MINOR, or MAJOR rubric increment is applied.
- [ ] `rubric_id` remains stable for revisions of the same rubric.
- [ ] Published `criterion_id` values remain immutable.
- [ ] New identities and migration mappings exist for semantic replacements.
- [ ] Deprecation notices contain dates, replacements, and support windows.
- [ ] Supported-version windows are recorded explicitly.
- [ ] Released rubric provenance includes `schema_version`, `rubric_id`, and `rubric_version`.
- [ ] Future critique provenance preserves the exact rubric used.
- [ ] Lossy migration and reevaluation requirements are documented.
- [ ] Major structural or semantic changes have a new PR or ADR review cycle.
- [ ] No runtime behavior or new schema fields are introduced implicitly.
- [ ] The approval references the exact reviewed commit.

## 21. Approval and Amendment Procedure

This policy becomes binding for Phase 1 after a documentation-only pull request receives explicit maintainer approval and is merged into `main`. Approval MUST identify the reviewed commit.

An amendment MUST:

1. use a new branch and pull request;
2. state the reason and affected policy sections;
3. classify compatibility, migration, deprecation, and provenance impacts;
4. remain consistent with the ratified schema or explicitly initiate the required schema PR or ADR cycle;
5. receive explicit maintainer approval; and
6. record the approved source and merge commits.

Major structural or semantic amendments require an ADR. No amendment may retroactively change the provenance or declared meaning of a previously released rubric or critique.
