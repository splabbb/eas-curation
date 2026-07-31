"""Tests for validated project-brief loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from eas.brief import load_project_brief


def test_load_project_brief(
    tmp_path: Path,
) -> None:
    """A valid brief should load normalized settings."""

    path = tmp_path / "brief.yaml"
    path.write_text(
        """
schema_version: 1

project:
  title: "Test project"
  synopsis: "A factual documentary test project."

selection:
  candidate_count: 100
  final_count: 20
  max_per_burst: 2
  duplicate_hash_distance: 6
  burst_window_seconds: 3.0
""".strip(),
        encoding="utf-8",
    )

    brief = load_project_brief(path)

    assert brief.title == "Test project"
    assert brief.selection.candidate_count == 100
    assert brief.selection.final_count == 20
    assert brief.selection.max_per_burst == 2


def test_project_title_is_required(
    tmp_path: Path,
) -> None:
    """A brief without a title should be rejected."""

    path = tmp_path / "brief.yaml"
    path.write_text(
        """
schema_version: 1

project:
  synopsis: "This project has no title."
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="project.title",
    ):
        load_project_brief(path)


def test_final_count_cannot_exceed_candidate_count(
    tmp_path: Path,
) -> None:
    """The final edit cannot exceed the candidate pool."""

    path = tmp_path / "brief.yaml"
    path.write_text(
        """
schema_version: 1

project:
  title: "Invalid counts"
  synopsis: "Testing invalid selection counts."

selection:
  candidate_count: 20
  final_count: 50
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="final_count",
    ):
        load_project_brief(path)