"""Tests for exact duplicate detection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eas.clustering import (
    calculate_sha256,
    find_exact_duplicates,
)


def test_calculate_sha256(
    tmp_path: Path,
) -> None:
    """The checksum should match hashlib."""

    path = tmp_path / "image.jpg"
    content = b"test-image-content"
    path.write_bytes(content)

    expected = hashlib.sha256(
        content
    ).hexdigest()

    assert calculate_sha256(path) == expected


def test_exact_duplicates_are_grouped(
    tmp_path: Path,
) -> None:
    """Byte-identical files should share one group."""

    first = tmp_path / "a.jpg"
    second = tmp_path / "b.jpg"
    unique = tmp_path / "c.jpg"

    first.write_bytes(b"identical-image")
    second.write_bytes(b"identical-image")
    unique.write_bytes(b"different-image")

    report = find_exact_duplicates(
        [first, second, unique]
    )

    assert report.input_count == 3
    assert report.fingerprinted_count == 3
    assert report.failed_count == 0
    assert report.unique_content_count == 2
    assert report.duplicate_file_count == 1
    assert len(report.duplicate_groups) == 1

    duplicate_group = report.duplicate_groups[0]

    assert duplicate_group.duplicate_count == 1
    assert duplicate_group.representative_path == str(
        first.resolve()
    )
    assert duplicate_group.member_paths == (
        str(first.resolve()),
        str(second.resolve()),
    )


def test_representative_selection_is_deterministic(
    tmp_path: Path,
) -> None:
    """Input ordering must not affect the representative."""

    first = tmp_path / "a.jpg"
    second = tmp_path / "z.jpg"

    first.write_bytes(b"same")
    second.write_bytes(b"same")

    report = find_exact_duplicates(
        [second, first]
    )

    assert report.representative_paths == [
        first.resolve()
    ]


def test_missing_file_is_reported(
    tmp_path: Path,
) -> None:
    """A missing file should not stop processing."""

    valid = tmp_path / "valid.jpg"
    missing = tmp_path / "missing.jpg"

    valid.write_bytes(b"valid")

    report = find_exact_duplicates(
        [valid, missing]
    )

    assert report.input_count == 2
    assert report.fingerprinted_count == 1
    assert report.failed_count == 1
    assert report.unique_content_count == 1
    assert report.failed_paths == (
        str(missing.resolve()),
    )


def test_report_is_json_serializable(
    tmp_path: Path,
) -> None:
    """The report should serialize without custom encoders."""

    path = tmp_path / "image.jpg"
    path.write_bytes(b"image")

    report = find_exact_duplicates([path])

    serialized = json.dumps(
        report.to_dict()
    )

    assert "unique_content_count" in serialized
    assert str(path.resolve()) in serialized