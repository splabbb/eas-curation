"""Exact duplicate detection for image files.

This module performs deterministic SHA-256 grouping before expensive
image decoding or machine-learning inference. Source files are never
modified, moved, or deleted.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileFingerprint:
    """Content fingerprint for one source file."""

    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)


@dataclass(frozen=True)
class ExactDuplicateGroup:
    """Files sharing the same SHA-256 digest."""

    cluster_id: int
    sha256: str
    representative_path: str
    member_paths: tuple[str, ...]
    size_bytes: int

    @property
    def is_duplicate(self) -> bool:
        """Return whether the group contains multiple files."""

        return len(self.member_paths) > 1

    @property
    def duplicate_count(self) -> int:
        """Return the number of redundant files in the group."""

        return max(0, len(self.member_paths) - 1)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "cluster_id": self.cluster_id,
            "sha256": self.sha256,
            "representative_path": self.representative_path,
            "member_paths": list(self.member_paths),
            "size_bytes": self.size_bytes,
            "is_duplicate": self.is_duplicate,
            "duplicate_count": self.duplicate_count,
        }


@dataclass(frozen=True)
class ExactDuplicateReport:
    """Summary and groups produced by exact duplicate detection."""

    input_count: int
    fingerprinted_count: int
    failed_count: int
    unique_content_count: int
    duplicate_file_count: int
    groups: tuple[ExactDuplicateGroup, ...]
    failed_paths: tuple[str, ...]

    @property
    def representative_paths(self) -> list[Path]:
        """Return one representative path for each unique file body."""

        return [
            Path(group.representative_path)
            for group in self.groups
        ]

    @property
    def duplicate_groups(self) -> tuple[ExactDuplicateGroup, ...]:
        """Return only groups containing redundant files."""

        return tuple(
            group
            for group in self.groups
            if group.is_duplicate
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible report."""

        return {
            "summary": {
                "input_count": self.input_count,
                "fingerprinted_count": self.fingerprinted_count,
                "failed_count": self.failed_count,
                "unique_content_count": self.unique_content_count,
                "duplicate_file_count": self.duplicate_file_count,
                "duplicate_group_count": len(
                    self.duplicate_groups
                ),
            },
            "groups": [
                group.to_dict()
                for group in self.groups
            ],
            "failed_paths": list(self.failed_paths),
        }


def calculate_sha256(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calculate the SHA-256 digest of a file.

    Args:
        path: File to fingerprint.
        chunk_size: Number of bytes read during each iteration.

    Returns:
        The lowercase hexadecimal SHA-256 digest.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path points to a directory.
        PermissionError: If the file cannot be read.
        ValueError: If chunk_size is not positive.
    """

    if chunk_size < 1:
        raise ValueError(
            "chunk_size must be at least 1"
        )

    source = Path(path).expanduser()

    if not source.exists():
        raise FileNotFoundError(
            f"File not found: {source}"
        )

    if not source.is_file():
        raise IsADirectoryError(
            f"Not a regular file: {source}"
        )

    digest = hashlib.sha256()

    with source.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def fingerprint_file(path: Path) -> FileFingerprint:
    """Create a content fingerprint for one file."""

    source = Path(path).expanduser().resolve()
    file_size = source.stat().st_size
    digest = calculate_sha256(source)

    return FileFingerprint(
        path=str(source),
        sha256=digest,
        size_bytes=file_size,
    )


def find_exact_duplicates(
    paths: Iterable[Path],
) -> ExactDuplicateReport:
    """Group files that contain exactly the same bytes.

    A deterministic representative is chosen by sorting member paths
    case-insensitively and retaining the first path. Failed files are
    reported but do not stop processing.

    Args:
        paths: Source file paths.

    Returns:
        ExactDuplicateReport containing all unique-content groups.
    """

    source_paths = sorted(
        (
            Path(path).expanduser().resolve()
            for path in paths
        ),
        key=lambda path: str(path).casefold(),
    )

    fingerprints: list[FileFingerprint] = []
    failed_paths: list[str] = []

    for index, path in enumerate(
        source_paths,
        start=1,
    ):
        logger.info(
            "Fingerprinting %d/%d: %s",
            index,
            len(source_paths),
            path.name,
        )

        try:
            fingerprints.append(
                fingerprint_file(path)
            )
        except (
            FileNotFoundError,
            IsADirectoryError,
            PermissionError,
            OSError,
        ) as exc:
            logger.warning(
                "Unable to fingerprint %s: %s",
                path,
                exc,
            )
            failed_paths.append(str(path))

    grouped: dict[str, list[FileFingerprint]] = {}

    for fingerprint in fingerprints:
        grouped.setdefault(
            fingerprint.sha256,
            [],
        ).append(fingerprint)

    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: min(
            member.path.casefold()
            for member in item[1]
        ),
    )

    groups: list[ExactDuplicateGroup] = []

    for cluster_id, (
        digest,
        members,
    ) in enumerate(ordered_groups, start=1):
        ordered_members = sorted(
            members,
            key=lambda item: item.path.casefold(),
        )

        representative = ordered_members[0]

        groups.append(
            ExactDuplicateGroup(
                cluster_id=cluster_id,
                sha256=digest,
                representative_path=representative.path,
                member_paths=tuple(
                    member.path
                    for member in ordered_members
                ),
                size_bytes=representative.size_bytes,
            )
        )

    duplicate_file_count = sum(
        group.duplicate_count
        for group in groups
    )

    report = ExactDuplicateReport(
        input_count=len(source_paths),
        fingerprinted_count=len(fingerprints),
        failed_count=len(failed_paths),
        unique_content_count=len(groups),
        duplicate_file_count=duplicate_file_count,
        groups=tuple(groups),
        failed_paths=tuple(failed_paths),
    )

    logger.info(
        "Exact duplicate detection: %d input, "
        "%d unique, %d redundant, %d failed",
        report.input_count,
        report.unique_content_count,
        report.duplicate_file_count,
        report.failed_count,
    )

    return report