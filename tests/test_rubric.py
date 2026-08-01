"""Dedicated behavioral tests for Rubric Schema Version 1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import yaml

from eas.rubric import (
    ABSOLUTE_WEIGHT_TOLERANCE,
    MAGNUM_DISCLAIMER,
    PROJECTBRIEF_FIELDS,
    IssueCode,
    RubricAggregationError,
    RubricLoadError,
    RubricValidationError,
    load_rubric_path,
    load_rubric_text,
    parse_rubric_document,
    validate_rubric_document,
    weighted_mean,
)


def valid_document() -> dict[str, Any]:
    """Return a fresh, minimal, valid Schema Version 1 document."""

    return {
        "schema_version": 1,
        "rubric_id": "test_rubric",
        "rubric_version": "1.0.0",
        "title": "Test rubric",
        "description": "A dedicated test rubric.",
        "scope": "hybrid",
        "metadata": {
            "author": "Test author",
            "disclaimer": MAGNUM_DISCLAIMER,
        },
        "score_scale": {"minimum": 0, "maximum": 5},
        "aggregation": {
            "method": "weighted_mean",
            "normalize_weights": True,
        },
        "criteria": [
            {
                "criterion_id": "first",
                "name": "First",
                "description": "First criterion.",
                "level": "image",
                "weight": 1.0,
                "required": True,
                "score_bands": [
                    {
                        "minimum": 0,
                        "maximum": 2,
                        "label": "Low",
                        "guidance": "Requires human review.",
                    },
                    {
                        "minimum": 3,
                        "maximum": 5,
                        "label": "High",
                        "guidance": "Strong result.",
                    },
                ],
            },
            {
                "criterion_id": "second",
                "name": "Second",
                "description": "Second criterion.",
                "level": "portfolio",
                "weight": 3.0,
                "required": False,
                "score_bands": [
                    {
                        "minimum": 0,
                        "maximum": 5,
                        "label": "Review",
                        "guidance": "Review the portfolio evidence.",
                    }
                ],
            },
        ],
    }


def issue_pairs(document: dict[str, Any]) -> list[tuple[str, str]]:
    """Return stable issue path and code pairs for a document."""

    return [(issue.path, issue.code) for issue in validate_rubric_document(document).issues]


def test_valid_document_builds_immutable_ordered_model() -> None:
    source = valid_document()
    before = deepcopy(source)

    result = validate_rubric_document(source)

    assert result.is_valid
    assert result.issues == ()
    assert result.rubric is not None
    rubric = result.rubric
    assert source == before
    assert isinstance(rubric.criteria, tuple)
    assert isinstance(rubric.criteria[0].score_bands, tuple)
    assert tuple(rubric.criteria_by_id) == ("first", "second")
    assert isinstance(rubric.criteria_by_id, MappingProxyType)
    with pytest.raises(TypeError):
        rubric.criteria_by_id["third"] = rubric.criteria[0]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        rubric.title = "Changed"  # type: ignore[misc]


def test_optional_metadata_and_criterion_collections_are_immutable() -> None:
    document = valid_document()
    document["metadata"].update(
        {
            "created_at": "2026-01-01",
            "updated_at": "2026-01-02",
            "reference_documents": ["One", "Two"],
            "tags": ["editorial", "review"],
        }
    )
    document["criteria"][0].update(
        {
            "projectbrief_fields": ["title", "semantic_prompts"],
            "tags": ["image"],
            "evidence_guidance": "Inspect visible evidence only.",
            "gating": {"enabled": False},
        }
    )

    rubric = parse_rubric_document(document)

    assert rubric.metadata.created_at == "2026-01-01"
    assert rubric.metadata.updated_at == "2026-01-02"
    assert rubric.metadata.reference_documents == ("One", "Two")
    assert rubric.metadata.tags == ("editorial", "review")
    assert rubric.criteria[0].projectbrief_fields == ("title", "semantic_prompts")
    assert rubric.criteria[0].tags == ("image",)
    assert rubric.criteria[0].evidence_guidance == "Inspect visible evidence only."
    assert rubric.criteria[0].gating is not None
    assert rubric.criteria[0].gating.enabled is False


@pytest.mark.parametrize("value", [True, False, "1", 1.0, None])
def test_schema_version_requires_non_boolean_integer(value: object) -> None:
    document = valid_document()
    document["schema_version"] = value
    assert issue_pairs(document)[0] == (
        "schema_version",
        IssueCode.NON_INTEGER_SCHEMA_VERSION,
    )


def test_missing_and_unsupported_schema_versions_are_distinct() -> None:
    missing = valid_document()
    missing.pop("schema_version")
    unsupported = valid_document()
    unsupported["schema_version"] = 2

    assert issue_pairs(missing)[0] == ("schema_version", IssueCode.MISSING_SCHEMA_VERSION)
    assert issue_pairs(unsupported)[0] == (
        "schema_version",
        IssueCode.UNSUPPORTED_SCHEMA_VERSION,
    )


@pytest.mark.parametrize(
    "version",
    ["0.0.0", "1.2.3", "1.2.3-alpha.1", "1.2.3+build.5", "1.2.3-rc.1+build"],
)
def test_valid_semantic_versions_are_accepted(version: str) -> None:
    document = valid_document()
    document["rubric_version"] = version
    assert parse_rubric_document(document).rubric_version == version


@pytest.mark.parametrize(
    "version",
    ["01.2.3", "1.02.3", "1.2.03", "1.2", "v1.2.3", "text", 1, None],
)
def test_invalid_semantic_versions_are_rejected(version: object) -> None:
    document = valid_document()
    document["rubric_version"] = version
    assert ("rubric_version", IssueCode.INVALID_RUBRIC_VERSION) in issue_pairs(document)


@pytest.mark.parametrize(
    ("field", "value", "path", "code"),
    [
        ("rubric_id", " ", "rubric_id", IssueCode.MISSING_RUBRIC_ID),
        ("title", 7, "title", IssueCode.MISSING_TITLE),
        ("description", "", "description", IssueCode.MISSING_DESCRIPTION),
        ("scope", "global", "scope", IssueCode.UNSUPPORTED_SCOPE),
        ("metadata", [], "metadata", IssueCode.MISSING_METADATA),
        ("score_scale", None, "score_scale", IssueCode.INVALID_SCORE_SCALE),
        ("criteria", [], "criteria", IssueCode.EMPTY_CRITERIA),
    ],
)
def test_required_rubric_fields_have_stable_issues(
    field: str, value: object, path: str, code: str
) -> None:
    document = valid_document()
    document[field] = value
    assert (path, code) in issue_pairs(document)


def test_missing_rubric_version_has_dedicated_issue() -> None:
    document = valid_document()
    document.pop("rubric_version")
    assert ("rubric_version", IssueCode.MISSING_RUBRIC_VERSION) in issue_pairs(document)


@pytest.mark.parametrize("value", [None, "", " ", 9])
def test_metadata_author_is_required(value: object) -> None:
    document = valid_document()
    document["metadata"]["author"] = value
    assert ("metadata.author", IssueCode.MISSING_AUTHOR) in issue_pairs(document)


@pytest.mark.parametrize("value", [None, "", "wrong", 9])
def test_frozen_disclaimer_is_required_exactly(value: object) -> None:
    document = valid_document()
    document["metadata"]["disclaimer"] = value
    assert ("metadata.disclaimer", IssueCode.INVALID_DISCLAIMER) in issue_pairs(document)


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize("value", ["", " ", 7, []])
def test_optional_metadata_strings_reject_invalid_values(field: str, value: object) -> None:
    document = valid_document()
    document["metadata"][field] = value
    assert (f"metadata.{field}", IssueCode.INVALID_TAGS) in issue_pairs(document)


@pytest.mark.parametrize("field", ["reference_documents", "tags"])
@pytest.mark.parametrize("value", ["tag", [""], [1], {}])
def test_metadata_string_collections_reject_invalid_structures(
    field: str, value: object
) -> None:
    document = valid_document()
    document["metadata"][field] = value
    assert (f"metadata.{field}", IssueCode.INVALID_TAGS) in issue_pairs(document)


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [(True, 5), (0, False), (None, 5), (0, None), ("0", 5), (0, "5"), (0, 0), (6, 5)],
)
def test_score_scale_rejects_invalid_bounds(minimum: object, maximum: object) -> None:
    document = valid_document()
    document["score_scale"] = {"minimum": minimum, "maximum": maximum}
    assert issue_pairs(document)[0] == ("score_scale", IssueCode.INVALID_SCORE_SCALE)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_score_scale_rejects_non_finite_bounds(value: float) -> None:
    document = valid_document()
    document["score_scale"]["minimum"] = value
    assert ("score_scale", IssueCode.INVALID_SCORE_SCALE) in issue_pairs(document)


def test_finite_score_scale_values_are_preserved_without_mutation() -> None:
    document = valid_document()
    document["score_scale"] = {"minimum": -1, "maximum": 5.5}
    before = deepcopy(document)
    rubric = parse_rubric_document(document)
    assert (rubric.score_scale.minimum, rubric.score_scale.maximum) == (-1.0, 5.5)
    assert document == before


@pytest.mark.parametrize(
    ("field", "value", "path", "code"),
    [
        ("method", "mean", "aggregation.method", IssueCode.UNSUPPORTED_AGGREGATION_METHOD),
        ("method", None, "aggregation.method", IssueCode.UNSUPPORTED_AGGREGATION_METHOD),
        ("normalize_weights", 1, "aggregation.normalize_weights", IssueCode.INVALID_NORMALIZE_WEIGHTS),
        ("normalize_weights", "true", "aggregation.normalize_weights", IssueCode.INVALID_NORMALIZE_WEIGHTS),
        ("normalize_weights", None, "aggregation.normalize_weights", IssueCode.INVALID_NORMALIZE_WEIGHTS),
    ],
)
def test_aggregation_configuration_has_stable_issues(
    field: str, value: object, path: str, code: str
) -> None:
    document = valid_document()
    document["aggregation"][field] = value
    assert (path, code) in issue_pairs(document)


@pytest.mark.parametrize("value", [None, "criteria", {}])
def test_criteria_requires_a_list(value: object) -> None:
    document = valid_document()
    document["criteria"] = value
    assert ("criteria", IssueCode.MISSING_CRITERIA) in issue_pairs(document)


def test_criterion_order_and_zero_individual_weight_are_preserved() -> None:
    document = valid_document()
    document["criteria"][0]["weight"] = 0
    rubric = parse_rubric_document(document)
    assert tuple(item.criterion_id for item in rubric.criteria) == ("first", "second")
    assert tuple(rubric.criteria_by_id) == ("first", "second")
    assert rubric.criteria[0].weight == 0.0


@pytest.mark.parametrize("weight", [0, 1e-7, 5e-7])
def test_total_source_weight_at_or_below_tolerance_is_rejected(weight: float) -> None:
    document = valid_document()
    for criterion in document["criteria"]:
        criterion["weight"] = weight
    assert ("criteria", IssueCode.ZERO_TOTAL_SOURCE_WEIGHT) in issue_pairs(document)


@pytest.mark.parametrize(
    ("field", "value", "path", "code"),
    [
        ("criterion_id", "", "criteria[0].criterion_id", IssueCode.MISSING_CRITERION_ID),
        ("name", None, "criteria[0].name", IssueCode.MISSING_CRITERION_NAME),
        ("description", " ", "criteria[0].description", IssueCode.MISSING_CRITERION_DESCRIPTION),
        ("level", "global", "criteria[0].level", IssueCode.UNSUPPORTED_CRITERION_LEVEL),
        ("required", 1, "criteria[0].required", IssueCode.NON_BOOLEAN_REQUIRED),
    ],
)
def test_criterion_required_fields_have_stable_issues(
    field: str, value: object, path: str, code: str
) -> None:
    document = valid_document()
    document["criteria"][0][field] = value
    assert (path, code) in issue_pairs(document)


def test_non_mapping_and_duplicate_criteria_are_rejected() -> None:
    document = valid_document()
    document["criteria"][0] = "bad"
    assert ("criteria[0]", IssueCode.INVALID_CRITERION) in issue_pairs(document)

    duplicate = valid_document()
    duplicate["criteria"][1]["criterion_id"] = "first"
    assert ("criteria[1].criterion_id", IssueCode.DUPLICATE_CRITERION_ID) in issue_pairs(duplicate)


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (True, IssueCode.INVALID_WEIGHT),
        ("1", IssueCode.INVALID_WEIGHT),
        (-1, IssueCode.NEGATIVE_WEIGHT),
        (float("nan"), IssueCode.NON_FINITE_WEIGHT),
        (float("inf"), IssueCode.NON_FINITE_WEIGHT),
        (float("-inf"), IssueCode.NON_FINITE_WEIGHT),
    ],
)
def test_criterion_weight_validation(value: object, code: str) -> None:
    document = valid_document()
    document["criteria"][0]["weight"] = value
    assert ("criteria[0].weight", code) in issue_pairs(document)


def test_missing_weight_has_dedicated_issue() -> None:
    document = valid_document()
    document["criteria"][0].pop("weight")
    assert ("criteria[0].weight", IssueCode.MISSING_WEIGHT) in issue_pairs(document)


@pytest.mark.parametrize("required", [True, False])
def test_boolean_required_values_are_preserved(required: bool) -> None:
    document = valid_document()
    document["criteria"][0]["required"] = required
    assert parse_rubric_document(document).criteria[0].required is required


@pytest.mark.parametrize(
    ("value", "code"),
    [(None, IssueCode.MISSING_SCORE_BANDS), ("bands", IssueCode.MISSING_SCORE_BANDS), ([], IssueCode.EMPTY_SCORE_BANDS)],
)
def test_score_bands_collection_validation(value: object, code: str) -> None:
    document = valid_document()
    document["criteria"][0]["score_bands"] = value
    assert ("criteria[0].score_bands", code) in issue_pairs(document)


@pytest.mark.parametrize(
    ("mutation", "path", "code"),
    [
        ({"minimum": True}, "criteria[0].score_bands[0]", IssueCode.INVALID_SCORE_BAND_BOUNDS),
        ({"maximum": float("nan")}, "criteria[0].score_bands[0]", IssueCode.INVALID_SCORE_BAND_BOUNDS),
        ({"minimum": 4, "maximum": 3}, "criteria[0].score_bands[0]", IssueCode.INVALID_SCORE_BAND_BOUNDS),
        ({"minimum": -1}, "criteria[0].score_bands[0]", IssueCode.SCORE_BAND_OUTSIDE_SCALE),
        ({"maximum": 6}, "criteria[0].score_bands[0]", IssueCode.SCORE_BAND_OUTSIDE_SCALE),
        ({"label": ""}, "criteria[0].score_bands[0].label", IssueCode.MISSING_SCORE_BAND_LABEL),
        ({"guidance": " "}, "criteria[0].score_bands[0].guidance", IssueCode.MISSING_SCORE_BAND_GUIDANCE),
    ],
)
def test_score_band_validation(
    mutation: dict[str, object], path: str, code: str
) -> None:
    document = valid_document()
    document["criteria"][0]["score_bands"][0].update(mutation)
    assert (path, code) in issue_pairs(document)


def test_non_mapping_overlapping_and_out_of_order_bands_are_rejected() -> None:
    non_mapping = valid_document()
    non_mapping["criteria"][0]["score_bands"][0] = "bad"
    assert (
        "criteria[0].score_bands[0]",
        IssueCode.INVALID_SCORE_BAND,
    ) in issue_pairs(non_mapping)

    overlap = valid_document()
    overlap["criteria"][0]["score_bands"][1]["minimum"] = 2
    assert (
        "criteria[0].score_bands[1]",
        IssueCode.OVERLAPPING_SCORE_BANDS,
    ) in issue_pairs(overlap)

    unordered = valid_document()
    unordered["criteria"][0]["score_bands"].reverse()
    pairs = issue_pairs(unordered)
    assert ("criteria[0].score_bands[1]", IssueCode.NONDETERMINISTIC_SCORE_BAND_ORDER) in pairs
    assert ("criteria[0].score_bands[1]", IssueCode.OVERLAPPING_SCORE_BANDS) in pairs


@pytest.mark.parametrize("field", sorted(PROJECTBRIEF_FIELDS))
def test_all_declared_projectbrief_fields_are_accepted(field: str) -> None:
    document = valid_document()
    document["criteria"][0]["projectbrief_fields"] = [field]
    assert parse_rubric_document(document).criteria[0].projectbrief_fields == (field,)


@pytest.mark.parametrize("value", ["title", [""], [1]])
def test_projectbrief_field_collection_rejects_invalid_values(value: object) -> None:
    document = valid_document()
    document["criteria"][0]["projectbrief_fields"] = value
    assert (
        "criteria[0].projectbrief_fields",
        IssueCode.UNKNOWN_PROJECTBRIEF_FIELD,
    ) in issue_pairs(document)


def test_unknown_projectbrief_field_has_indexed_path() -> None:
    document = valid_document()
    document["criteria"][0]["projectbrief_fields"] = ["title", "unknown"]
    assert (
        "criteria[0].projectbrief_fields[1]",
        IssueCode.UNKNOWN_PROJECTBRIEF_FIELD,
    ) in issue_pairs(document)


@pytest.mark.parametrize("value", ["tag", [""], [1], {}])
def test_criterion_tags_reject_invalid_values(value: object) -> None:
    document = valid_document()
    document["criteria"][0]["tags"] = value
    assert ("criteria[0].tags", IssueCode.INVALID_TAGS) in issue_pairs(document)


@pytest.mark.parametrize("value", ["", " ", 9, []])
def test_evidence_guidance_rejects_invalid_values(value: object) -> None:
    document = valid_document()
    document["criteria"][0]["evidence_guidance"] = value
    assert (
        "criteria[0].evidence_guidance",
        IssueCode.INVALID_EVIDENCE_GUIDANCE,
    ) in issue_pairs(document)


@pytest.mark.parametrize("enabled", [True, False])
def test_structural_gating_accepts_boolean_enabled(enabled: bool) -> None:
    document = valid_document()
    document["criteria"][0]["gating"] = {"enabled": enabled}
    gating = parse_rubric_document(document).criteria[0].gating
    assert gating is not None and gating.enabled is enabled


@pytest.mark.parametrize("value", [{}, {"threshold": 3}, {"enabled": False, "policy": "fail"}, "no"])
def test_gating_rejects_missing_or_unknown_structure(value: object) -> None:
    document = valid_document()
    document["criteria"][0]["gating"] = value
    assert (
        "criteria[0].gating",
        IssueCode.INVALID_GATING_STRUCTURE,
    ) in issue_pairs(document)


def test_gating_enabled_must_be_boolean() -> None:
    document = valid_document()
    document["criteria"][0]["gating"] = {"enabled": 0}
    assert (
        "criteria[0].gating.enabled",
        IssueCode.NON_BOOLEAN_GATING_ENABLED,
    ) in issue_pairs(document)


def test_multiple_issues_are_complete_deterministic_and_structured() -> None:
    document = valid_document()
    document["schema_version"] = True
    document["title"] = ""
    document["aggregation"] = {"method": "mean", "normalize_weights": 1}
    document["criteria"][0]["name"] = ""
    before = deepcopy(document)

    first = validate_rubric_document(document)
    second = validate_rubric_document(document)

    expected = [
        ("schema_version", IssueCode.NON_INTEGER_SCHEMA_VERSION),
        ("title", IssueCode.MISSING_TITLE),
        ("aggregation.method", IssueCode.UNSUPPORTED_AGGREGATION_METHOD),
        ("aggregation.normalize_weights", IssueCode.INVALID_NORMALIZE_WEIGHTS),
        ("criteria[0].name", IssueCode.MISSING_CRITERION_NAME),
    ]
    assert [(item.path, item.code) for item in first.issues] == expected
    assert first.issues == second.issues
    assert all(item.path and item.code and item.message for item in first.issues)
    assert first.rubric is None
    assert not first.is_valid
    assert document == before


def test_parse_invalid_document_raises_structured_exception() -> None:
    document = valid_document()
    document["title"] = ""
    with pytest.raises(RubricValidationError) as raised:
        parse_rubric_document(document)
    assert raised.value.issues[0].path == "title"
    assert raised.value.issues[0].code == IssueCode.MISSING_TITLE
    assert "1 issue" in str(raised.value)


def test_yaml_text_and_explicit_path_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = valid_document()
    text = yaml.safe_dump(document, sort_keys=False)
    assert load_rubric_text(text, source="caller").rubric_id == "test_rubric"

    path = tmp_path / "rubric.yaml"
    path.write_text(text, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert load_rubric_path(path).rubric_id == "test_rubric"


@pytest.mark.parametrize(
    ("text", "code"),
    [("metadata: [", "yaml_parse_error"), ("- not\n- a\n- mapping", "non_mapping_document")],
)
def test_yaml_loading_errors_are_typed(text: str, code: str) -> None:
    with pytest.raises(RubricLoadError) as raised:
        load_rubric_text(text, source="memory")
    assert raised.value.code == code
    assert raised.value.source == "memory"
    assert raised.value.__cause__ is not None if code == "yaml_parse_error" else True


def test_path_loading_boundaries_are_typed(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(RubricLoadError) as missing_error:
        load_rubric_path(missing)
    assert missing_error.value.code == "file_not_found"
    assert missing_error.value.source == str(missing)
    assert isinstance(missing_error.value.__cause__, FileNotFoundError)

    invalid = tmp_path / "invalid.yaml"
    invalid.write_bytes(b"\xff\xfe")
    with pytest.raises(RubricLoadError) as encoding_error:
        load_rubric_path(invalid)
    assert encoding_error.value.code == "invalid_encoding"
    assert isinstance(encoding_error.value.__cause__, UnicodeError)


def test_loading_and_validation_errors_remain_distinct() -> None:
    with pytest.raises(RubricValidationError):
        load_rubric_text("schema_version: 1")
    with pytest.raises(RubricLoadError):
        load_rubric_text("[")


def test_no_implicit_lookup_migration_or_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TypeError):
        load_rubric_text(None)  # type: ignore[arg-type]
    document = valid_document()
    document["schema_version"] = 2
    with pytest.raises(RubricValidationError) as raised:
        load_rubric_text(yaml.safe_dump(document))
    assert raised.value.issues[0].code == IssueCode.UNSUPPORTED_SCHEMA_VERSION
    assert document["schema_version"] == 2


def test_weighted_mean_uses_source_weights_and_renormalizes_exclusions() -> None:
    rubric = parse_rubric_document(valid_document())
    assert weighted_mean(rubric, {"first": 5, "second": 1}) == pytest.approx(2.0)
    assert weighted_mean(rubric, {"first": 5}, not_applicable={"second"}) == pytest.approx(5.0)
    assert ABSOLUTE_WEIGHT_TOLERANCE == 1e-6


@pytest.mark.parametrize(
    ("scores", "excluded"),
    [
        ({"first": 5}, ()),
        ({"first": 5, "second": 1, "unknown": 2}, ()),
        ({"first": 5, "second": 1}, {"unknown"}),
        ({"first": 5, "second": 1}, {"first"}),
    ],
)
def test_weighted_mean_rejects_incomplete_unknown_or_overlapping_ids(
    scores: dict[str, float], excluded: object
) -> None:
    rubric = parse_rubric_document(valid_document())
    with pytest.raises(RubricAggregationError):
        weighted_mean(rubric, scores, not_applicable=excluded)  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [True, "1", float("nan"), float("inf"), -1, 6])
def test_weighted_mean_rejects_invalid_scores(score: object) -> None:
    rubric = parse_rubric_document(valid_document())
    with pytest.raises(RubricAggregationError):
        weighted_mean(rubric, {"first": score, "second": 1})  # type: ignore[dict-item]


def test_weighted_mean_rejects_zero_applicable_weight_without_mutation() -> None:
    document = valid_document()
    document["criteria"][0]["weight"] = 0
    rubric = parse_rubric_document(document)
    scores = {"first": 3.0}
    excluded = {"second"}
    scores_before = scores.copy()
    excluded_before = excluded.copy()
    criteria_before = rubric.criteria

    with pytest.raises(RubricAggregationError, match="applicable weight"):
        weighted_mean(rubric, scores, not_applicable=excluded)

    assert scores == scores_before
    assert excluded == excluded_before
    assert rubric.criteria == criteria_before
    assert weighted_mean(rubric, {"first": 1, "second": 5}) == pytest.approx(5.0)
