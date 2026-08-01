"""Acceptance tests for the approved source-only reference rubric."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from eas.rubric import MAGNUM_DISCLAIMER, load_rubric_path


REFERENCE_RUBRIC = (
    Path(__file__).resolve().parents[1] / "docs" / "magnum_informed_rubric.yaml"
)


def test_approved_reference_rubric_contract() -> None:
    rubric = load_rubric_path(REFERENCE_RUBRIC)

    assert rubric.schema_version == 1
    assert rubric.rubric_id == "magnum_informed_portfolio_review"
    assert rubric.rubric_version == "1.0.0"
    assert rubric.scope == "hybrid"
    assert len(rubric.criteria) == 9
    assert rubric.total_source_weight == pytest.approx(9.75)
    assert rubric.aggregation.method == "weighted_mean"
    assert rubric.aggregation.normalize_weights is True
    assert rubric.score_scale.minimum == 0
    assert rubric.score_scale.maximum == 5
    assert rubric.metadata.disclaimer == MAGNUM_DISCLAIMER


def test_reference_criterion_order_identity_and_levels() -> None:
    rubric = load_rubric_path(REFERENCE_RUBRIC)
    criterion_ids = tuple(item.criterion_id for item in rubric.criteria)

    assert criterion_ids == (
        "technical_quality",
        "composition",
        "narrative_contribution",
        "project_relevance",
        "distinctiveness",
        "cohesion",
        "sequence_support",
        "subject_coverage",
        "portfolio_integrity",
    )
    assert len(criterion_ids) == len(set(criterion_ids))
    assert {item.level for item in rubric.criteria} == {"image", "portfolio"}
    assert tuple(rubric.criteria_by_id) == criterion_ids


def test_reference_model_is_deeply_immutable() -> None:
    rubric = load_rubric_path(REFERENCE_RUBRIC)

    assert isinstance(rubric.criteria, tuple)
    assert isinstance(rubric.criteria_by_id, MappingProxyType)
    assert isinstance(rubric.metadata.tags, tuple)
    assert isinstance(rubric.metadata.reference_documents, tuple)
    assert all(isinstance(item.score_bands, tuple) for item in rubric.criteria)
    assert all(isinstance(item.tags, tuple) for item in rubric.criteria)
    assert all(isinstance(item.projectbrief_fields, tuple) for item in rubric.criteria)
    with pytest.raises(FrozenInstanceError):
        rubric.scope = "image"  # type: ignore[misc]
    with pytest.raises(TypeError):
        rubric.criteria_by_id["new"] = rubric.criteria[0]  # type: ignore[index]


def test_reference_gating_is_structural_and_disabled() -> None:
    rubric = load_rubric_path(REFERENCE_RUBRIC)
    declared = [item.gating for item in rubric.criteria if item.gating is not None]

    assert declared
    assert all(item.enabled is False for item in declared)
    assert not hasattr(rubric, "passed")
    assert not hasattr(rubric, "decision")
