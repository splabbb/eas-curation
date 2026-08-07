"""Deterministic, immutable run-manifest construction.

This module transforms an existing validated curation request and completed
curation result into a JSON-compatible manifest. It performs no filesystem
writes and does not repeat discovery, analysis, duplicate detection, integrity
generation, ranking, or export behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eas import __version__
from eas.application import CurationRunRequest, CurationRunResult
from eas.clustering import ExactDuplicateReport
from eas.integrity import IntegrityReport
from eas.pipeline import ImageResult


MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RunManifestRequest:
    """Resolved effective configuration for one curation run."""

    input_dir: str
    output_dir: str
    top_n: int
    threshold: float
    model_name: str
    deduplicate: bool
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible representation."""
        return {
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "top_n": self.top_n,
            "threshold": self.threshold,
            "model_name": self.model_name,
            "deduplicate": self.deduplicate,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class RunManifestSummary:
    """Counts derived from completed run facts."""

    discovered_count: int
    analyzed_count: int
    failed_analysis_count: int
    selected_count: int
    fingerprint_failed_count: int

    def to_dict(self) -> dict[str, int]:
        """Return a deterministic JSON-compatible representation."""
        return {
            "discovered_count": self.discovered_count,
            "analyzed_count": self.analyzed_count,
            "failed_analysis_count": self.failed_analysis_count,
            "selected_count": self.selected_count,
            "fingerprint_failed_count": self.fingerprint_failed_count,
        }


@dataclass(frozen=True)
class ProjectBriefProvenance:
    """Approved non-editorial ProjectBrief provenance."""

    source_path: str
    schema_version: int
    title: str

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible representation."""
        return {
            "source_path": self.source_path,
            "schema_version": self.schema_version,
            "title": self.title,
        }


@dataclass(frozen=True)
class RunManifestFailures:
    """Distinct fingerprint and image-analysis failure paths."""

    fingerprint_failed_paths: tuple[str, ...]
    analysis_failed_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        """Return fresh JSON lists preserving repository order."""
        return {
            "fingerprint_failed_paths": list(self.fingerprint_failed_paths),
            "analysis_failed_paths": list(self.analysis_failed_paths),
        }


@dataclass(frozen=True)
class RunManifestReports:
    """Existing duplicate and integrity report state."""

    duplicate_report: ExactDuplicateReport | None
    integrity_report: IntegrityReport | None

    def to_dict(self) -> dict[str, Any]:
        """Return existing report payloads without redesigning them."""
        return {
            "duplicate_report": (
                self.duplicate_report.to_dict()
                if self.duplicate_report is not None
                else None
            ),
            "integrity_report": (
                self.integrity_report.to_dict()
                if self.integrity_report is not None
                else None
            ),
        }


@dataclass(frozen=True)
class RunManifest:
    """Immutable Schema Version 1 curation run manifest."""

    schema_version: int
    application_version: str
    request: RunManifestRequest
    summary: RunManifestSummary
    project_brief: ProjectBriefProvenance | None
    discovered_paths: tuple[str, ...]
    analyzed_results: tuple[ImageResult, ...]
    selected_results: tuple[ImageResult, ...]
    failures: RunManifestFailures
    reports: RunManifestReports
    artifacts: tuple[str, ...]
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        """Return the authoritative deterministic manifest payload."""
        return {
            "schema_version": self.schema_version,
            "application_version": self.application_version,
            "request": self.request.to_dict(),
            "summary": self.summary.to_dict(),
            "project_brief": (
                self.project_brief.to_dict()
                if self.project_brief is not None
                else None
            ),
            "discovered_paths": list(self.discovered_paths),
            "analyzed_results": [item.to_dict() for item in self.analyzed_results],
            "selected_results": [item.to_dict() for item in self.selected_results],
            "failures": self.failures.to_dict(),
            "reports": self.reports.to_dict(),
            "artifacts": list(self.artifacts),
            "dry_run": self.dry_run,
        }


def _validate_request_result_consistency(
    request: CurationRunRequest,
    result: CurationRunResult,
) -> None:
    """Reject request and result facts that describe different runs."""
    request_input = str(request.input_dir.expanduser().resolve())
    if request_input != result.input_dir:
        raise ValueError("request and result input_dir values do not match")

    request_output = str(request.output_dir.expanduser().resolve())
    if request_output != result.output_dir:
        raise ValueError("request and result output_dir values do not match")

    if request.dry_run is not result.dry_run:
        raise ValueError("request and result dry_run values do not match")


def _project_brief_provenance(
    request: CurationRunRequest,
) -> ProjectBriefProvenance | None:
    """Return only the approved ProjectBrief provenance fields."""
    brief = request.project_brief
    if brief is None:
        return None

    return ProjectBriefProvenance(
        source_path=brief.source_path,
        schema_version=brief.schema_version,
        title=brief.title,
    )


def build_run_manifest(
    request: CurationRunRequest,
    result: CurationRunResult,
) -> RunManifest:
    """Build a manifest from existing request and completed-result facts.

    Args:
        request: Validated effective application request.
        result: Completed immutable application result.

    Returns:
        An immutable, deterministic, JSON-compatible run manifest.

    Raises:
        TypeError: If either argument has the wrong public boundary type.
        ValueError: If request and result identity facts disagree.
    """
    if not isinstance(request, CurationRunRequest):
        raise TypeError("request must be a CurationRunRequest")
    if not isinstance(result, CurationRunResult):
        raise TypeError("result must be a CurationRunResult")

    _validate_request_result_consistency(request, result)

    duplicate_report = result.duplicate_report
    fingerprint_failed_paths = (
        duplicate_report.failed_paths if duplicate_report is not None else ()
    )

    return RunManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        application_version=__version__,
        request=RunManifestRequest(
            input_dir=result.input_dir,
            output_dir=result.output_dir,
            top_n=request.top_n,
            threshold=float(request.threshold),
            model_name=request.model_name,
            deduplicate=request.deduplicate,
            dry_run=request.dry_run,
        ),
        summary=RunManifestSummary(
            discovered_count=result.discovered_count,
            analyzed_count=result.analyzed_count,
            failed_analysis_count=len(result.failed_analysis_paths),
            selected_count=result.selected_count,
            fingerprint_failed_count=len(fingerprint_failed_paths),
        ),
        project_brief=_project_brief_provenance(request),
        discovered_paths=tuple(result.discovered_paths),
        analyzed_results=tuple(result.analyzed_results),
        selected_results=tuple(result.selected_results),
        failures=RunManifestFailures(
            fingerprint_failed_paths=tuple(fingerprint_failed_paths),
            analysis_failed_paths=tuple(result.failed_analysis_paths),
        ),
        reports=RunManifestReports(
            duplicate_report=duplicate_report,
            integrity_report=result.integrity_report,
        ),
        artifacts=tuple(result.written_artifacts),
        dry_run=result.dry_run,
    )


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "RunManifest",
    "build_run_manifest",
]
