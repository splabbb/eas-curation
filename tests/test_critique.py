"""Behavioral tests for deterministic critique generation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from eas.critique import CritiqueError, generate_critique
from eas.rubric import MAGNUM_DISCLAIMER, parse_rubric_document


def rubric_document() -> dict[str, Any]:
    """Return a small valid rubric with deliberately ordered criteria."""
    return {
        "schema_version": 1,
        "rubric_id": "critique_test",
        "rubric_version": "1.2.3",
        "title": "Critique test",
        "description": "Critique behavior fixture.",
        "scope": "hybrid",
        "metadata": {"author": "Test", "disclaimer": MAGNUM_DISCLAIMER},
        "score_scale": {"minimum": 0, "maximum": 5},
        "aggregation": {"method": "weighted_mean", "normalize_weights": True},
        "criteria": [
            {
                "criterion_id": "image_first",
                "name": "Image first",
                "level": "image",
                "weight": 1,
                "required": True,
                "description": "Inspect the image.",
                "score_bands": [
                    {"minimum": 0, "maximum": 5, "label": "Review", "guidance": "Review."}
                ],
            },
            {
                "criterion_id": "portfolio_second",
                "name": "Portfolio second",
                "level": "portfolio",
                "weight": 1,
                "required": True,
                "description": "Inspect the portfolio.",
                "score_bands": [
                    {"minimum": 0, "maximum": 5, "label": "Review", "guidance": "Review."}
                ],
            },
        ],
    }


def test_generate_critique_preserves_provenance_and_rubric_order() -> None:
    rubric = parse_rubric_document(rubric_document())
    critique = generate_critique(
        rubric,
        {"portfolio_second": "Second note", "image_first": "First note"},
    )
    assert (critique.schema_version, critique.rubric_id, critique.rubric_version) == (
        1,
        "critique_test",
        "1.2.3",
    )
    assert tuple(item.criterion_id for item in critique.observations) == (
        "image_first",
        "portfolio_second",
    )
    assert tuple(item.observation for item in critique.observations) == (
        "First note",
        "Second note",
    )


def test_generate_critique_is_deterministic_and_does_not_mutate_inputs() -> None:
    rubric = parse_rubric_document(rubric_document())
    observations = {"image_first": " First note ", "portfolio_second": "Second note"}
    before = observations.copy()
    first = generate_critique(rubric, observations)
    second = generate_critique(rubric, observations)
    assert first == second
    assert observations == before
    assert first.observations[0].observation == "First note"


def test_critique_is_immutable_and_json_compatible() -> None:
    rubric = parse_rubric_document(rubric_document())
    critique = generate_critique(
        rubric,
        {"image_first": "First", "portfolio_second": "Second"},
    )
    with pytest.raises(FrozenInstanceError):
        critique.rubric_id = "changed"  # type: ignore[misc]
    assert critique.to_dict()["observations"][0]["level"] == "image"


@pytest.mark.parametrize(
    "observations, message",
    [
        ({"image_first": "Only"}, "missing criterion IDs: portfolio_second"),
        (
            {"image_first": "First", "portfolio_second": "Second", "unknown": "No"},
            "unknown criterion IDs: unknown",
        ),
        ({"image_first": " ", "portfolio_second": "Second"}, "must be non-empty"),
        ({"image_first": 1, "portfolio_second": "Second"}, "must be a string"),
    ],
)
def test_generate_critique_rejects_invalid_observations(
    observations: dict[str, Any],
    message: str,
) -> None:
    rubric = parse_rubric_document(rubric_document())
    with pytest.raises(CritiqueError, match=message):
        generate_critique(rubric, observations)  # type: ignore[arg-type]


def test_generate_critique_rejects_invalid_boundary_types() -> None:
    rubric = parse_rubric_document(rubric_document())
    with pytest.raises(TypeError, match="validated Rubric"):
        generate_critique(object(), {})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a mapping"):
        generate_critique(rubric, [])  # type: ignore[arg-type]
