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
6. provide deterministic validation behavior.
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
