"""Validated YAML project-brief support."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SelectionSettings:
    """Selection settings supplied by an editorial brief."""

    candidate_count: int = 200
    final_count: int = 50
    max_per_burst: int = 2
    duplicate_hash_distance: int = 6
    burst_window_seconds: float = 3.0


@dataclass(frozen=True)
class ProjectBrief:
    """Normalized project and editorial context."""

    source_path: str
    schema_version: int
    title: str
    synopsis: str
    themes: tuple[str, ...]
    subjects: tuple[str, ...]
    locations: tuple[str, ...]
    visual_intent: str
    desired_sequence_roles: tuple[str, ...]
    avoid: tuple[str, ...]
    selection: SelectionSettings
    require_original_metadata: bool
    flag_missing_metadata: bool
    synthetic_images_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)

    @property
    def semantic_prompts(self) -> tuple[str, ...]:
        """Return text suitable for later CLIP relevance scoring."""

        values = [
            self.synopsis,
            self.visual_intent,
            *self.themes,
            *self.subjects,
            *self.locations,
        ]
        return tuple(
            value.strip()
            for value in values
            if value and value.strip()
        )


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")

    return value


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()

    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")

    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must contain only strings")

    return tuple(
        item.strip()
        for item in value
        if item.strip()
    )


def _positive_integer(
    value: Any,
    field: str,
    default: int,
) -> int:
    result = default if value is None else int(value)

    if result < 1:
        raise ValueError(f"{field} must be at least 1")

    return result


def load_project_brief(path: str | Path) -> ProjectBrief:
    """Load and validate a YAML project brief."""

    source = Path(path).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(
            f"Project brief not found: {source}"
        )

    raw = yaml.safe_load(
        source.read_text(encoding="utf-8")
    )
    root = _mapping(raw, "document")

    schema_version = int(
        root.get("schema_version", 1)
    )
    if schema_version != 1:
        raise ValueError(
            "Only project brief schema_version 1 "
            "is currently supported"
        )

    project = _mapping(
        root.get("project"),
        "project",
    )
    editorial = _mapping(
        root.get("editorial"),
        "editorial",
    )
    selection_data = _mapping(
        root.get("selection"),
        "selection",
    )
    provenance = _mapping(
        root.get("provenance"),
        "provenance",
    )

    title = str(
        project.get("title", "")
    ).strip()
    synopsis = str(
        project.get("synopsis", "")
    ).strip()

    if not title:
        raise ValueError(
            "project.title is required"
        )

    if not synopsis:
        raise ValueError(
            "project.synopsis is required"
        )

    duplicate_distance = int(
        selection_data.get(
            "duplicate_hash_distance",
            6,
        )
    )
    if not 0 <= duplicate_distance <= 64:
        raise ValueError(
            "selection.duplicate_hash_distance "
            "must be between 0 and 64"
        )

    burst_window = float(
        selection_data.get(
            "burst_window_seconds",
            3.0,
        )
    )
    if burst_window < 0:
        raise ValueError(
            "selection.burst_window_seconds "
            "cannot be negative"
        )

    selection = SelectionSettings(
        candidate_count=_positive_integer(
            selection_data.get("candidate_count"),
            "selection.candidate_count",
            200,
        ),
        final_count=_positive_integer(
            selection_data.get("final_count"),
            "selection.final_count",
            50,
        ),
        max_per_burst=_positive_integer(
            selection_data.get("max_per_burst"),
            "selection.max_per_burst",
            2,
        ),
        duplicate_hash_distance=duplicate_distance,
        burst_window_seconds=burst_window,
    )

    if selection.final_count > selection.candidate_count:
        raise ValueError(
            "selection.final_count cannot exceed "
            "selection.candidate_count"
        )

    return ProjectBrief(
        source_path=str(source),
        schema_version=schema_version,
        title=title,
        synopsis=synopsis,
        themes=_string_list(
            project.get("themes"),
            "project.themes",
        ),
        subjects=_string_list(
            project.get("subjects"),
            "project.subjects",
        ),
        locations=_string_list(
            project.get("locations"),
            "project.locations",
        ),
        visual_intent=str(
            editorial.get("visual_intent", "")
        ).strip(),
        desired_sequence_roles=_string_list(
            editorial.get(
                "desired_sequence_roles"
            ),
            "editorial.desired_sequence_roles",
        ),
        avoid=_string_list(
            editorial.get("avoid"),
            "editorial.avoid",
        ),
        selection=selection,
        require_original_metadata=bool(
            provenance.get(
                "require_original_metadata",
                False,
            )
        ),
        flag_missing_metadata=bool(
            provenance.get(
                "flag_missing_metadata",
                True,
            )
        ),
        synthetic_images_allowed=bool(
            provenance.get(
                "synthetic_images_allowed",
                False,
            )
        ),
    )