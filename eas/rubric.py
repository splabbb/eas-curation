"""Immutable Rubric Schema Version 1 models, loading, and validation.

This module intentionally has no runtime integration with the curation pipeline.
Callers must explicitly supply rubric text, a mapping, or a filesystem path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Collection, Mapping, Sequence
import math
import re

import yaml


ABSOLUTE_WEIGHT_TOLERANCE = 1e-6
SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_SCOPES = frozenset({"image", "portfolio", "hybrid"})
SUPPORTED_CRITERION_LEVELS = frozenset({"image", "portfolio"})
SUPPORTED_AGGREGATION_METHODS = frozenset({"weighted_mean"})
PROJECTBRIEF_FIELDS = frozenset(
    {
        "title",
        "synopsis",
        "themes",
        "subjects",
        "locations",
        "visual_intent",
        "desired_sequence_roles",
        "avoid",
        "semantic_prompts",
    }
)

MAGNUM_DISCLAIMER = """This rubric is independently authored for the eas-curation project.

It is informed by general, publicly discussed editorial portfolio-review
concepts and photographic evaluation practices.

It is not an official Magnum Photos rubric, policy, review framework,
endorsement, certification, recommendation, or publication standard.

Use of the term "Magnum-informed" indicates general editorial inspiration
only. It does not indicate affiliation, authorization, sponsorship,
approval, representation, or endorsement by Magnum Photos or any of its
members.

The rubric provides configurable review guidance and does not guarantee
editorial acceptance, publication, professional recognition, legal
compliance, factual authenticity, or any particular selection outcome.

Users remain responsible for editorial decisions, rights clearance,
provenance verification, privacy obligations, and lawful use of all images
and associated metadata."""

_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class IssueCode:
    """Stable machine-readable Schema Version 1 validation issue codes."""

    MISSING_SCHEMA_VERSION = "missing_schema_version"
    NON_INTEGER_SCHEMA_VERSION = "non_integer_schema_version"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    MISSING_RUBRIC_VERSION = "missing_rubric_version"
    INVALID_RUBRIC_VERSION = "invalid_rubric_version"
    MISSING_RUBRIC_ID = "missing_rubric_id"
    MISSING_TITLE = "missing_title"
    MISSING_DESCRIPTION = "missing_description"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    MISSING_METADATA = "missing_metadata"
    MISSING_AUTHOR = "missing_author"
    INVALID_DISCLAIMER = "invalid_disclaimer"
    INVALID_SCORE_SCALE = "invalid_score_scale"
    UNSUPPORTED_AGGREGATION_METHOD = "unsupported_aggregation_method"
    INVALID_NORMALIZE_WEIGHTS = "invalid_normalize_weights"
    MISSING_CRITERIA = "missing_criteria"
    EMPTY_CRITERIA = "empty_criteria"
    INVALID_CRITERION = "invalid_criterion"
    MISSING_CRITERION_ID = "missing_criterion_id"
    DUPLICATE_CRITERION_ID = "duplicate_criterion_id"
    MISSING_CRITERION_NAME = "missing_criterion_name"
    MISSING_CRITERION_DESCRIPTION = "missing_criterion_description"
    UNSUPPORTED_CRITERION_LEVEL = "unsupported_criterion_level"
    MISSING_WEIGHT = "missing_weight"
    INVALID_WEIGHT = "invalid_weight"
    NEGATIVE_WEIGHT = "negative_weight"
    NON_FINITE_WEIGHT = "non_finite_weight"
    NON_BOOLEAN_REQUIRED = "non_boolean_required"
    MISSING_SCORE_BANDS = "missing_score_bands"
    EMPTY_SCORE_BANDS = "empty_score_bands"
    INVALID_SCORE_BAND = "invalid_score_band"
    INVALID_SCORE_BAND_BOUNDS = "invalid_score_band_bounds"
    SCORE_BAND_OUTSIDE_SCALE = "score_band_outside_scale"
    OVERLAPPING_SCORE_BANDS = "overlapping_score_bands"
    NONDETERMINISTIC_SCORE_BAND_ORDER = "nondeterministic_score_band_order"
    MISSING_SCORE_BAND_LABEL = "missing_score_band_label"
    MISSING_SCORE_BAND_GUIDANCE = "missing_score_band_guidance"
    UNKNOWN_PROJECTBRIEF_FIELD = "unknown_projectbrief_field"
    INVALID_TAGS = "invalid_tags"
    INVALID_EVIDENCE_GUIDANCE = "invalid_evidence_guidance"
    INVALID_GATING_STRUCTURE = "invalid_gating_structure"
    NON_BOOLEAN_GATING_ENABLED = "non_boolean_gating_enabled"
    ZERO_TOTAL_SOURCE_WEIGHT = "zero_total_source_weight"


@dataclass(frozen=True, order=True)
class ValidationIssue:
    """One deterministic validation failure."""

    path: str
    code: str
    message: str


@dataclass(frozen=True)
class RubricMetadata:
    """Authorship and provenance metadata."""

    author: str
    disclaimer: str
    created_at: str | None = None
    updated_at: str | None = None
    reference_documents: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoreScale:
    """Global inclusive numeric score range."""

    minimum: float
    maximum: float


@dataclass(frozen=True)
class AggregationConfig:
    """Schema-level aggregation configuration."""

    method: str
    normalize_weights: bool


@dataclass(frozen=True)
class ScoreBand:
    """Inclusive score range and its human-review interpretation."""

    minimum: float
    maximum: float
    label: str
    guidance: str

    def contains(self, score: float) -> bool:
        """Return whether ``score`` belongs to this inclusive band."""

        return self.minimum <= score <= self.maximum


@dataclass(frozen=True)
class GatingConfig:
    """Inactive Phase 1 gating declaration."""

    enabled: bool


@dataclass(frozen=True)
class Criterion:
    """One ordered rubric evaluation dimension."""

    criterion_id: str
    name: str
    level: str
    weight: float
    required: bool
    description: str
    score_bands: tuple[ScoreBand, ...]
    projectbrief_fields: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    evidence_guidance: str | None = None
    gating: GatingConfig | None = None


@dataclass(frozen=True)
class Rubric:
    """A validated, immutable Schema Version 1 rubric."""

    schema_version: int
    rubric_id: str
    rubric_version: str
    title: str
    description: str
    scope: str
    metadata: RubricMetadata
    score_scale: ScoreScale
    aggregation: AggregationConfig
    criteria: tuple[Criterion, ...]

    @property
    def criteria_by_id(self) -> Mapping[str, Criterion]:
        """Return an immutable criterion lookup preserving source order."""

        return MappingProxyType(
            {criterion.criterion_id: criterion for criterion in self.criteria}
        )

    @property
    def total_source_weight(self) -> float:
        """Return the unmodified sum of source criterion weights."""

        return math.fsum(criterion.weight for criterion in self.criteria)


@dataclass(frozen=True)
class ValidationResult:
    """Validation issues and the model built only after successful validation."""

    issues: tuple[ValidationIssue, ...]
    rubric: Rubric | None = None

    @property
    def is_valid(self) -> bool:
        """Return whether validation succeeded."""

        return not self.issues and self.rubric is not None


class RubricError(Exception):
    """Base class for explicit rubric boundary errors."""


class RubricLoadError(RubricError):
    """A rubric document could not be loaded."""

    def __init__(self, code: str, message: str, source: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.source = source


class RubricValidationError(RubricError):
    """A loaded document does not conform to Schema Version 1."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            f"Rubric validation failed with {len(self.issues)} issue(s)"
        )


class RubricAggregationError(RubricError):
    """Caller-supplied scores cannot be aggregated safely."""


class _Validator:
    """Stateful, deterministic validator used for one document only."""

    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def add(self, path: str, code: str, message: str) -> None:
        self.issues.append(ValidationIssue(path, code, message))

    @staticmethod
    def mapping(value: Any) -> Mapping[str, Any] | None:
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def nonempty_string(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        result = float(value)
        return result if math.isfinite(result) else None

    def string_tuple(
        self,
        value: Any,
        path: str,
        code: str,
        *,
        optional: bool = True,
    ) -> tuple[str, ...] | None:
        if value is None and optional:
            return ()
        if not isinstance(value, list) or any(
            self.nonempty_string(item) is None for item in value
        ):
            self.add(path, code, f"{path} must be a list of non-empty strings")
            return None
        return tuple(item.strip() for item in value)

    def validate(self, document: Mapping[str, Any]) -> ValidationResult:
        schema_version = self._schema_version(document)
        rubric_id = self._required_string(
            document, "rubric_id", IssueCode.MISSING_RUBRIC_ID
        )
        rubric_version = self._rubric_version(document)
        title = self._required_string(document, "title", IssueCode.MISSING_TITLE)
        description = self._required_string(
            document, "description", IssueCode.MISSING_DESCRIPTION
        )

        scope_value = document.get("scope")
        scope = self.nonempty_string(scope_value)
        if scope not in SUPPORTED_SCOPES:
            self.add(
                "scope",
                IssueCode.UNSUPPORTED_SCOPE,
                "scope must be exactly 'image', 'portfolio', or 'hybrid'",
            )
            scope = None

        metadata = self._metadata(document.get("metadata"))
        score_scale = self._score_scale(document.get("score_scale"))
        aggregation = self._aggregation(document.get("aggregation"))
        criteria = self._criteria(document.get("criteria"), score_scale)

        if self.issues:
            return ValidationResult(tuple(self.issues))

        assert schema_version is not None
        assert rubric_id is not None
        assert rubric_version is not None
        assert title is not None
        assert description is not None
        assert scope is not None
        assert metadata is not None
        assert score_scale is not None
        assert aggregation is not None
        assert criteria is not None
        return ValidationResult(
            (),
            Rubric(
                schema_version=schema_version,
                rubric_id=rubric_id,
                rubric_version=rubric_version,
                title=title,
                description=description,
                scope=scope,
                metadata=metadata,
                score_scale=score_scale,
                aggregation=aggregation,
                criteria=criteria,
            ),
        )

    def _schema_version(self, document: Mapping[str, Any]) -> int | None:
        if "schema_version" not in document:
            self.add(
                "schema_version",
                IssueCode.MISSING_SCHEMA_VERSION,
                "schema_version is required",
            )
            return None
        value = document["schema_version"]
        if isinstance(value, bool) or not isinstance(value, int):
            self.add(
                "schema_version",
                IssueCode.NON_INTEGER_SCHEMA_VERSION,
                "schema_version must be an integer and must not be Boolean",
            )
            return None
        if value != SUPPORTED_SCHEMA_VERSION:
            self.add(
                "schema_version",
                IssueCode.UNSUPPORTED_SCHEMA_VERSION,
                f"schema_version {value} is unsupported; only 1 is supported",
            )
            return None
        return value

    def _rubric_version(self, document: Mapping[str, Any]) -> str | None:
        if "rubric_version" not in document:
            self.add(
                "rubric_version",
                IssueCode.MISSING_RUBRIC_VERSION,
                "rubric_version is required",
            )
            return None
        value = document["rubric_version"]
        if not isinstance(value, str) or _SEMVER_PATTERN.fullmatch(value) is None:
            self.add(
                "rubric_version",
                IssueCode.INVALID_RUBRIC_VERSION,
                "rubric_version must be valid Semantic Versioning",
            )
            return None
        return value

    def _required_string(
        self, document: Mapping[str, Any], field: str, code: str
    ) -> str | None:
        value = self.nonempty_string(document.get(field))
        if value is None:
            self.add(field, code, f"{field} is required and must be non-empty")
        return value

    def _metadata(self, value: Any) -> RubricMetadata | None:
        data = self.mapping(value)
        if data is None:
            self.add(
                "metadata",
                IssueCode.MISSING_METADATA,
                "metadata is required and must be a mapping",
            )
            return None
        author = self.nonempty_string(data.get("author"))
        if author is None:
            self.add(
                "metadata.author",
                IssueCode.MISSING_AUTHOR,
                "metadata.author is required and must be non-empty",
            )
        disclaimer = self.nonempty_string(data.get("disclaimer"))
        if disclaimer is None or disclaimer != MAGNUM_DISCLAIMER:
            self.add(
                "metadata.disclaimer",
                IssueCode.INVALID_DISCLAIMER,
                "metadata.disclaimer must exactly contain the frozen Magnum disclaimer",
            )
            disclaimer = None
        created_at = self._optional_string(data.get("created_at"), "metadata.created_at")
        updated_at = self._optional_string(data.get("updated_at"), "metadata.updated_at")
        references = self.string_tuple(
            data.get("reference_documents"),
            "metadata.reference_documents",
            IssueCode.INVALID_TAGS,
        )
        tags = self.string_tuple(
            data.get("tags"), "metadata.tags", IssueCode.INVALID_TAGS
        )
        if author is None or disclaimer is None or references is None or tags is None:
            return None
        return RubricMetadata(
            author=author,
            disclaimer=disclaimer,
            created_at=created_at,
            updated_at=updated_at,
            reference_documents=references,
            tags=tags,
        )

    def _optional_string(self, value: Any, path: str) -> str | None:
        if value is None:
            return None
        result = self.nonempty_string(value)
        if result is None:
            self.add(path, IssueCode.INVALID_TAGS, f"{path} must be a non-empty string")
        return result

    def _score_scale(self, value: Any) -> ScoreScale | None:
        data = self.mapping(value)
        minimum = self.number(data.get("minimum")) if data is not None else None
        maximum = self.number(data.get("maximum")) if data is not None else None
        if minimum is None or maximum is None or minimum >= maximum:
            self.add(
                "score_scale",
                IssueCode.INVALID_SCORE_SCALE,
                "score_scale must contain finite numeric minimum and maximum values with minimum < maximum",
            )
            return None
        return ScoreScale(minimum, maximum)

    def _aggregation(self, value: Any) -> AggregationConfig | None:
        data = self.mapping(value)
        method = data.get("method") if data is not None else None
        normalize = data.get("normalize_weights") if data is not None else None
        valid = True
        if method not in SUPPORTED_AGGREGATION_METHODS:
            self.add(
                "aggregation.method",
                IssueCode.UNSUPPORTED_AGGREGATION_METHOD,
                "aggregation.method must be 'weighted_mean'",
            )
            valid = False
        if not isinstance(normalize, bool):
            self.add(
                "aggregation.normalize_weights",
                IssueCode.INVALID_NORMALIZE_WEIGHTS,
                "aggregation.normalize_weights must be Boolean",
            )
            valid = False
        return AggregationConfig(method, normalize) if valid else None

    def _criteria(
        self, value: Any, score_scale: ScoreScale | None
    ) -> tuple[Criterion, ...] | None:
        if value is None:
            self.add("criteria", IssueCode.MISSING_CRITERIA, "criteria is required")
            return None
        if not isinstance(value, list):
            self.add(
                "criteria",
                IssueCode.MISSING_CRITERIA,
                "criteria must be a non-empty list",
            )
            return None
        if not value:
            self.add("criteria", IssueCode.EMPTY_CRITERIA, "criteria must not be empty")
            return None

        result: list[Criterion] = []
        seen_ids: set[str] = set()
        total_weight = 0.0
        all_weights_valid = True
        for index, raw in enumerate(value):
            criterion, weight_valid = self._criterion(
                raw, index, seen_ids, score_scale
            )
            all_weights_valid = all_weights_valid and weight_valid
            if criterion is not None:
                result.append(criterion)
                total_weight += criterion.weight
        if all_weights_valid and total_weight <= ABSOLUTE_WEIGHT_TOLERANCE:
            self.add(
                "criteria",
                IssueCode.ZERO_TOTAL_SOURCE_WEIGHT,
                "the total source criterion weight must be greater than 1e-6",
            )
        return tuple(result) if len(result) == len(value) else None

    def _criterion(
        self,
        value: Any,
        index: int,
        seen_ids: set[str],
        score_scale: ScoreScale | None,
    ) -> tuple[Criterion | None, bool]:
        base = f"criteria[{index}]"
        data = self.mapping(value)
        if data is None:
            self.add(base, IssueCode.INVALID_CRITERION, "criterion must be a mapping")
            return None, False

        criterion_id = self.nonempty_string(data.get("criterion_id"))
        if criterion_id is None:
            self.add(
                f"{base}.criterion_id",
                IssueCode.MISSING_CRITERION_ID,
                "criterion_id is required and must be non-empty",
            )
        elif criterion_id in seen_ids:
            self.add(
                f"{base}.criterion_id",
                IssueCode.DUPLICATE_CRITERION_ID,
                f"criterion_id {criterion_id!r} duplicates an earlier criterion",
            )
            criterion_id = None
        else:
            seen_ids.add(criterion_id)

        name = self.nonempty_string(data.get("name"))
        if name is None:
            self.add(
                f"{base}.name",
                IssueCode.MISSING_CRITERION_NAME,
                "criterion name is required and must be non-empty",
            )
        description = self.nonempty_string(data.get("description"))
        if description is None:
            self.add(
                f"{base}.description",
                IssueCode.MISSING_CRITERION_DESCRIPTION,
                "criterion description is required and must be non-empty",
            )
        level = data.get("level")
        if level not in SUPPORTED_CRITERION_LEVELS:
            self.add(
                f"{base}.level",
                IssueCode.UNSUPPORTED_CRITERION_LEVEL,
                "criterion level must be exactly 'image' or 'portfolio'",
            )
            level = None

        weight, weight_valid = self._weight(data, base)
        required = data.get("required")
        if not isinstance(required, bool):
            self.add(
                f"{base}.required",
                IssueCode.NON_BOOLEAN_REQUIRED,
                "criterion required status must be Boolean",
            )
            required = None

        bands = self._score_bands(data.get("score_bands"), base, score_scale)
        project_fields = self._projectbrief_fields(
            data.get("projectbrief_fields"), base
        )
        tags = self.string_tuple(
            data.get("tags"), f"{base}.tags", IssueCode.INVALID_TAGS
        )
        evidence = self._evidence_guidance(data.get("evidence_guidance"), base)
        gating = self._gating(data.get("gating"), base)

        required_values = (
            criterion_id,
            name,
            description,
            level,
            weight,
            required,
            bands,
            project_fields,
            tags,
        )
        if any(item is None for item in required_values):
            return None, weight_valid
        return (
            Criterion(
                criterion_id=criterion_id,
                name=name,
                level=level,
                weight=weight,
                required=required,
                description=description,
                score_bands=bands,
                projectbrief_fields=project_fields,
                tags=tags,
                evidence_guidance=evidence,
                gating=gating,
            ),
            weight_valid,
        )

    def _weight(self, data: Mapping[str, Any], base: str) -> tuple[float | None, bool]:
        path = f"{base}.weight"
        if "weight" not in data:
            self.add(path, IssueCode.MISSING_WEIGHT, "criterion weight is required")
            return None, False
        raw = data["weight"]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            self.add(path, IssueCode.INVALID_WEIGHT, "weight must be numeric and not Boolean")
            return None, False
        weight = float(raw)
        if not math.isfinite(weight):
            self.add(path, IssueCode.NON_FINITE_WEIGHT, "weight must be finite")
            return None, False
        if weight < 0:
            self.add(path, IssueCode.NEGATIVE_WEIGHT, "weight must be non-negative")
            return None, False
        return weight, True

    def _score_bands(
        self, value: Any, base: str, score_scale: ScoreScale | None
    ) -> tuple[ScoreBand, ...] | None:
        path = f"{base}.score_bands"
        if value is None:
            self.add(path, IssueCode.MISSING_SCORE_BANDS, "score_bands is required")
            return None
        if not isinstance(value, list):
            self.add(path, IssueCode.MISSING_SCORE_BANDS, "score_bands must be a list")
            return None
        if not value:
            self.add(path, IssueCode.EMPTY_SCORE_BANDS, "score_bands must not be empty")
            return None

        result: list[ScoreBand] = []
        previous: ScoreBand | None = None
        for band_index, raw in enumerate(value):
            band_path = f"{path}[{band_index}]"
            data = self.mapping(raw)
            if data is None:
                self.add(
                    band_path,
                    IssueCode.INVALID_SCORE_BAND,
                    "score band must be a mapping",
                )
                continue
            minimum = self.number(data.get("minimum"))
            maximum = self.number(data.get("maximum"))
            bounds_valid = minimum is not None and maximum is not None
            if not bounds_valid or minimum > maximum:
                self.add(
                    band_path,
                    IssueCode.INVALID_SCORE_BAND_BOUNDS,
                    "score band bounds must be finite numbers with minimum <= maximum",
                )
                bounds_valid = False
            elif score_scale is not None and (
                minimum < score_scale.minimum or maximum > score_scale.maximum
            ):
                self.add(
                    band_path,
                    IssueCode.SCORE_BAND_OUTSIDE_SCALE,
                    "score band must remain within the global score scale",
                )
            label = self.nonempty_string(data.get("label"))
            if label is None:
                self.add(
                    f"{band_path}.label",
                    IssueCode.MISSING_SCORE_BAND_LABEL,
                    "score band label is required and must be non-empty",
                )
            guidance = self.nonempty_string(data.get("guidance"))
            if guidance is None:
                self.add(
                    f"{band_path}.guidance",
                    IssueCode.MISSING_SCORE_BAND_GUIDANCE,
                    "score band guidance is required and must be non-empty",
                )
            if bounds_valid and label is not None and guidance is not None:
                band = ScoreBand(minimum, maximum, label, guidance)
                if previous is not None:
                    if (band.minimum, band.maximum) < (
                        previous.minimum,
                        previous.maximum,
                    ):
                        self.add(
                            band_path,
                            IssueCode.NONDETERMINISTIC_SCORE_BAND_ORDER,
                            "score bands must be ordered by ascending minimum and maximum",
                        )
                    if band.minimum <= previous.maximum:
                        self.add(
                            band_path,
                            IssueCode.OVERLAPPING_SCORE_BANDS,
                            "inclusive score bands must not overlap",
                        )
                result.append(band)
                previous = band
        return tuple(result) if len(result) == len(value) else None

    def _projectbrief_fields(self, value: Any, base: str) -> tuple[str, ...] | None:
        path = f"{base}.projectbrief_fields"
        fields = self.string_tuple(
            value, path, IssueCode.UNKNOWN_PROJECTBRIEF_FIELD
        )
        if fields is None:
            return None
        valid = True
        for index, field in enumerate(fields):
            if field not in PROJECTBRIEF_FIELDS:
                self.add(
                    f"{path}[{index}]",
                    IssueCode.UNKNOWN_PROJECTBRIEF_FIELD,
                    f"unknown ProjectBrief field {field!r}",
                )
                valid = False
        return fields if valid else None

    def _evidence_guidance(self, value: Any, base: str) -> str | None:
        if value is None:
            return None
        result = self.nonempty_string(value)
        if result is None:
            self.add(
                f"{base}.evidence_guidance",
                IssueCode.INVALID_EVIDENCE_GUIDANCE,
                "evidence_guidance must be a non-empty human-review string",
            )
        return result

    def _gating(self, value: Any, base: str) -> GatingConfig | None:
        if value is None:
            return None
        path = f"{base}.gating"
        data = self.mapping(value)
        if data is None or set(data) != {"enabled"}:
            self.add(
                path,
                IssueCode.INVALID_GATING_STRUCTURE,
                "gating must contain only the Phase 1 field 'enabled'",
            )
            return None
        enabled = data["enabled"]
        if not isinstance(enabled, bool):
            self.add(
                f"{path}.enabled",
                IssueCode.NON_BOOLEAN_GATING_ENABLED,
                "gating.enabled must be Boolean",
            )
            return None
        return GatingConfig(enabled)


def validate_rubric_document(document: Mapping[str, Any]) -> ValidationResult:
    """Validate a caller-supplied mapping without modifying it.

    Issues are emitted in schema field order, criterion source order, and score
    band source order. No repair, migration, or default rubric is applied.
    """

    if not isinstance(document, Mapping):
        raise TypeError("document must be a mapping")
    return _Validator().validate(document)


def parse_rubric_document(document: Mapping[str, Any]) -> Rubric:
    """Return an immutable rubric or raise :class:`RubricValidationError`."""

    result = validate_rubric_document(document)
    if not result.is_valid:
        raise RubricValidationError(result.issues)
    assert result.rubric is not None
    return result.rubric


def _load_yaml_text(text: str, source: str | None) -> Mapping[str, Any]:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RubricLoadError(
            "yaml_parse_error",
            f"Malformed rubric YAML{f' from {source}' if source else ''}",
            source,
        ) from exc
    if not isinstance(loaded, Mapping):
        raise RubricLoadError(
            "non_mapping_document",
            "Rubric YAML root must be a mapping",
            source,
        )
    return loaded


def load_rubric_text(text: str, *, source: str | None = None) -> Rubric:
    """Safely load and validate caller-supplied YAML text."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return parse_rubric_document(_load_yaml_text(text, source))


def load_rubric_path(path: str | Path) -> Rubric:
    """Load UTF-8 YAML from an explicit path and validate it.

    File-not-found, decoding, permission, and other operating-system failures
    remain distinct typed loading errors and preserve their original causes.
    """

    source = Path(path).expanduser()
    try:
        text = source.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RubricLoadError(
            "file_not_found", f"Rubric file not found: {source}", str(source)
        ) from exc
    except UnicodeError as exc:
        raise RubricLoadError(
            "invalid_encoding",
            f"Rubric file is not valid UTF-8: {source}",
            str(source),
        ) from exc
    except OSError as exc:
        raise RubricLoadError(
            "unreadable_file", f"Rubric file cannot be read: {source}", str(source)
        ) from exc
    return load_rubric_text(text, source=str(source))


def weighted_mean(
    rubric: Rubric,
    scores: Mapping[str, float],
    *,
    not_applicable: Collection[str] = (),
) -> float:
    """Compute a pure schema-level weighted mean for explicit scores.

    Exactly the rubric's criterion IDs must be represented by either ``scores``
    or ``not_applicable``. Scores must be finite and inside the global scale.
    Applicable weights are renormalized without modifying either input.
    """

    excluded = frozenset(not_applicable)
    known_ids = frozenset(item.criterion_id for item in rubric.criteria)
    unknown_scores = frozenset(scores) - known_ids
    unknown_exclusions = excluded - known_ids
    overlap = frozenset(scores) & excluded
    if unknown_scores or unknown_exclusions or overlap:
        raise RubricAggregationError(
            "scores and not_applicable must be disjoint and use known criterion IDs"
        )

    applicable = tuple(
        criterion for criterion in rubric.criteria
        if criterion.criterion_id not in excluded
    )
    missing = tuple(
        criterion.criterion_id for criterion in applicable
        if criterion.criterion_id not in scores
    )
    if missing:
        raise RubricAggregationError(
            f"missing scores for applicable criteria: {', '.join(missing)}"
        )

    weighted_values: list[float] = []
    weights: list[float] = []
    for criterion in applicable:
        raw_score = scores[criterion.criterion_id]
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
            raise RubricAggregationError(
                f"score for {criterion.criterion_id!r} must be numeric and not Boolean"
            )
        score = float(raw_score)
        if not math.isfinite(score):
            raise RubricAggregationError(
                f"score for {criterion.criterion_id!r} must be finite"
            )
        if not rubric.score_scale.minimum <= score <= rubric.score_scale.maximum:
            raise RubricAggregationError(
                f"score for {criterion.criterion_id!r} is outside the global scale"
            )
        weighted_values.append(score * criterion.weight)
        weights.append(criterion.weight)

    total_weight = math.fsum(weights)
    if total_weight <= ABSOLUTE_WEIGHT_TOLERANCE:
        raise RubricAggregationError(
            "total applicable weight must be greater than 1e-6"
        )
    return math.fsum(weighted_values) / total_weight


__all__ = [
    "ABSOLUTE_WEIGHT_TOLERANCE",
    "AggregationConfig",
    "Criterion",
    "GatingConfig",
    "IssueCode",
    "MAGNUM_DISCLAIMER",
    "PROJECTBRIEF_FIELDS",
    "Rubric",
    "RubricAggregationError",
    "RubricError",
    "RubricLoadError",
    "RubricMetadata",
    "RubricValidationError",
    "ScoreBand",
    "ScoreScale",
    "SUPPORTED_SCHEMA_VERSION",
    "ValidationIssue",
    "ValidationResult",
    "load_rubric_path",
    "load_rubric_text",
    "parse_rubric_document",
    "validate_rubric_document",
    "weighted_mean",
]
