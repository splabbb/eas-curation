"""Deterministic, immutable critique generation for validated rubrics.

This module is a standalone Phase 1 consumer of :mod:`eas.rubric`. It does
not score criteria, aggregate scores, make decisions, execute gating, access
the network, or load runtime models.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from eas.rubric import Criterion, Rubric


class CritiqueError(ValueError):
    """Raised when caller-supplied critique observations are invalid."""


@dataclass(frozen=True)
class CriterionObservation:
    """One immutable observation tied to an ordered rubric criterion."""

    criterion_id: str
    criterion_name: str
    level: str
    observation: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return asdict(self)


@dataclass(frozen=True)
class Critique:
    """Structured critique with exact rubric-version provenance."""

    schema_version: int
    rubric_id: str
    rubric_version: str
    observations: tuple[CriterionObservation, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation preserving source order."""
        return {
            "schema_version": self.schema_version,
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "observations": [item.to_dict() for item in self.observations],
        }


def _validated_observation(
    criterion: Criterion,
    value: object,
) -> CriterionObservation:
    """Validate and normalize one caller-supplied observation."""
    if not isinstance(value, str):
        raise CritiqueError(
            f"observation for {criterion.criterion_id!r} must be a string"
        )
    observation = value.strip()
    if not observation:
        raise CritiqueError(
            f"observation for {criterion.criterion_id!r} must be non-empty"
        )
    return CriterionObservation(
        criterion_id=criterion.criterion_id,
        criterion_name=criterion.name,
        level=criterion.level,
        observation=observation,
    )


def generate_critique(
    rubric: Rubric,
    observations: Mapping[str, str],
) -> Critique:
    """Generate a deterministic critique from a validated rubric.

    The observation mapping must contain exactly one non-empty string for each
    rubric criterion. Output order follows rubric source order, independent of
    mapping insertion order. Inputs are never mutated.

    Args:
        rubric: A validated immutable Schema Version 1 rubric.
        observations: Criterion IDs mapped to human-authored observations.

    Returns:
        An immutable critique preserving exact rubric provenance.

    Raises:
        TypeError: If either public argument has the wrong boundary type.
        CritiqueError: If criterion IDs are missing or unknown, or an
            observation is not a non-empty string.
    """
    if not isinstance(rubric, Rubric):
        raise TypeError("rubric must be a validated Rubric")
    if not isinstance(observations, Mapping):
        raise TypeError("observations must be a mapping")

    known_ids = tuple(item.criterion_id for item in rubric.criteria)
    known_set = frozenset(known_ids)
    supplied_set = frozenset(observations)

    unknown = tuple(sorted(supplied_set - known_set))
    missing = tuple(item for item in known_ids if item not in supplied_set)
    if unknown or missing:
        details: list[str] = []
        if missing:
            details.append(f"missing criterion IDs: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown criterion IDs: {', '.join(unknown)}")
        raise CritiqueError("; ".join(details))

    generated = tuple(
        _validated_observation(criterion, observations[criterion.criterion_id])
        for criterion in rubric.criteria
    )
    return Critique(
        schema_version=rubric.schema_version,
        rubric_id=rubric.rubric_id,
        rubric_version=rubric.rubric_version,
        observations=generated,
    )


__all__ = [
    "CriterionObservation",
    "Critique",
    "CritiqueError",
    "generate_critique",
]
