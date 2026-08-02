"""Deterministic, immutable reporting of repository-produced integrity facts.

This module converts validated exact-duplicate reports into structured factual
findings. It does not fingerprint files, score rubric criteria, make decisions,
execute gating, access the network, or load runtime models.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eas.clustering import ExactDuplicateGroup, ExactDuplicateReport


class FindingCode:
    """Stable machine-readable integrity finding codes."""

    EXACT_DUPLICATE = "exact_duplicate"
    FINGERPRINT_FAILED = "fingerprint_failed"


_SUPPORTED_FINDING_CODES = frozenset(
    {
        FindingCode.EXACT_DUPLICATE,
        FindingCode.FINGERPRINT_FAILED,
    }
)


class IntegrityError(ValueError):
    """Raised when caller-supplied integrity facts are malformed."""


@dataclass(frozen=True)
class IntegrityFinding:
    """One immutable, factual integrity finding.

    Attributes:
        code: Stable machine-readable finding identity.
        message: Human-readable factual explanation.
        affected_paths: Exact source paths associated with the finding.
    """

    code: str
    message: str
    affected_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject malformed findings without silently repairing them."""
        if not isinstance(self.code, str) or self.code not in _SUPPORTED_FINDING_CODES:
            raise IntegrityError(f"unsupported integrity finding code: {self.code!r}")
        if not isinstance(self.message, str) or not self.message.strip():
            raise IntegrityError("integrity finding message must be a non-empty string")
        if not isinstance(self.affected_paths, tuple):
            raise IntegrityError("affected_paths must be a tuple")
        if not self.affected_paths:
            raise IntegrityError("affected_paths must not be empty")
        if any(not isinstance(path, str) or not path for path in self.affected_paths):
            raise IntegrityError("affected_paths must contain only non-empty strings")
        if len(self.affected_paths) != len(set(self.affected_paths)):
            raise IntegrityError("affected_paths must not contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation preserving path order."""
        return {
            "code": self.code,
            "message": self.message,
            "affected_paths": list(self.affected_paths),
        }


@dataclass(frozen=True)
class IntegrityReport:
    """Immutable collection of deterministic integrity findings."""

    findings: tuple[IntegrityFinding, ...]

    def __post_init__(self) -> None:
        """Reject malformed report collections explicitly."""
        if not isinstance(self.findings, tuple):
            raise IntegrityError("findings must be a tuple")
        if any(not isinstance(finding, IntegrityFinding) for finding in self.findings):
            raise IntegrityError("findings must contain only IntegrityFinding objects")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible report in deterministic finding order."""
        return {"findings": [finding.to_dict() for finding in self.findings]}


def _path_key(path: str) -> tuple[str, str]:
    """Return a deterministic case-insensitive path ordering key."""
    return path.casefold(), path


def _validate_duplicate_group(group: ExactDuplicateGroup) -> None:
    """Validate facts consumed from one duplicate group."""
    if not isinstance(group, ExactDuplicateGroup):
        raise IntegrityError("duplicate groups must be ExactDuplicateGroup objects")
    if not isinstance(group.sha256, str) or len(group.sha256) != 64:
        raise IntegrityError("duplicate group sha256 must be a 64-character string")
    try:
        int(group.sha256, 16)
    except ValueError as exc:
        raise IntegrityError("duplicate group sha256 must be hexadecimal") from exc
    if not isinstance(group.member_paths, tuple) or not group.member_paths:
        raise IntegrityError("duplicate group member_paths must be a non-empty tuple")
    if any(not isinstance(path, str) or not path for path in group.member_paths):
        raise IntegrityError("duplicate group member_paths must contain non-empty strings")
    if len(group.member_paths) != len(set(group.member_paths)):
        raise IntegrityError("duplicate group member_paths must not contain duplicates")
    if group.representative_path not in group.member_paths:
        raise IntegrityError("duplicate group representative_path must be a member path")


def generate_integrity_report(duplicate_report: ExactDuplicateReport) -> IntegrityReport:
    """Generate factual integrity findings from exact-duplicate results.

    Duplicate detection remains the responsibility of :mod:`eas.clustering`.
    This function performs no filesystem access. One finding is emitted for
    every exact-duplicate group and every failed fingerprint path. Groups that
    represent unique content do not produce findings.

    Ordering is independent of caller ordering: findings are ordered by code,
    then by affected path using the repository's case-insensitive path style.
    The caller-supplied report is never mutated.

    Args:
        duplicate_report: Repository-produced exact-duplicate report.

    Returns:
        An immutable integrity report.

    Raises:
        TypeError: If ``duplicate_report`` has the wrong boundary type.
        IntegrityError: If contained source facts are malformed.
    """
    if not isinstance(duplicate_report, ExactDuplicateReport):
        raise TypeError("duplicate_report must be an ExactDuplicateReport")

    generated: list[IntegrityFinding] = []
    for group in duplicate_report.groups:
        _validate_duplicate_group(group)
        if not group.is_duplicate:
            continue
        member_paths = tuple(sorted(group.member_paths, key=_path_key))
        generated.append(
            IntegrityFinding(
                code=FindingCode.EXACT_DUPLICATE,
                message=(
                    f"{len(member_paths)} files have identical SHA-256 content "
                    f"{group.sha256}."
                ),
                affected_paths=member_paths,
            )
        )

    if not isinstance(duplicate_report.failed_paths, tuple):
        raise IntegrityError("failed_paths must be a tuple")
    if any(not isinstance(path, str) or not path for path in duplicate_report.failed_paths):
        raise IntegrityError("failed_paths must contain only non-empty strings")
    if len(duplicate_report.failed_paths) != len(set(duplicate_report.failed_paths)):
        raise IntegrityError("failed_paths must not contain duplicates")

    for path in sorted(duplicate_report.failed_paths, key=_path_key):
        generated.append(
            IntegrityFinding(
                code=FindingCode.FINGERPRINT_FAILED,
                message=f"Content fingerprint generation failed for {path}.",
                affected_paths=(path,),
            )
        )

    findings = tuple(
        sorted(
            generated,
            key=lambda finding: (
                finding.code,
                tuple(_path_key(path) for path in finding.affected_paths),
                finding.message,
            ),
        )
    )
    return IntegrityReport(findings=findings)


__all__ = [
    "FindingCode",
    "IntegrityError",
    "IntegrityFinding",
    "IntegrityReport",
    "generate_integrity_report",
]
