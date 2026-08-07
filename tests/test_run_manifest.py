"""Focused behavioral tests for deterministic run manifests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from eas import __version__
from eas.application import CurationRunRequest, CurationRunResult
from eas.brief import ProjectBrief, SelectionSettings
from eas.clustering import ExactDuplicateGroup, ExactDuplicateReport
from eas.integrity import FindingCode, IntegrityFinding, IntegrityReport
from eas.pipeline import ImageResult
from eas.run_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RunManifest,
    build_run_manifest,
)
from eas.vision import QualityMetrics


def make_image_result(path: str, score: float) -> ImageResult:
    """Create one immutable image result."""
    return ImageResult(
        path=path,
        score=score,
        passed=True,
        metrics=QualityMetrics(
            sharpness=0.8,
            exposure=0.7,
            contrast=0.6,
            dynamic_range=0.5,
            resolution=0.9,
            clipping=1.0,
            aesthetic=0.5,
        ),
    )


def make_request(
    tmp_path: Path,
    *,
    deduplicate: bool = True,
    dry_run: bool = False,
    project_brief: ProjectBrief | None = None,
) -> CurationRunRequest:
    """Create a valid effective run request."""
    return CurationRunRequest(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        top_n=7,
        threshold=0.25,
        model_name="requested-model",
        deduplicate=deduplicate,
        dry_run=dry_run,
        project_brief=project_brief,
    )


def make_duplicate_report(
    input_dir: Path,
    *,
    failed_paths: tuple[str, ...] = (),
) -> ExactDuplicateReport:
    """Create a deterministic duplicate report."""
    first = str((input_dir / "a.jpg").resolve())
    second = str((input_dir / "b.jpg").resolve())
    group = ExactDuplicateGroup(
        cluster_id=1,
        sha256="a" * 64,
        representative_path=first,
        member_paths=(first, second),
        size_bytes=100,
    )
    return ExactDuplicateReport(
        input_count=2 + len(failed_paths),
        fingerprinted_count=2,
        failed_count=len(failed_paths),
        unique_content_count=1,
        duplicate_file_count=1,
        groups=(group,),
        failed_paths=failed_paths,
    )


def make_integrity_report(input_dir: Path) -> IntegrityReport:
    """Create a deterministic integrity report."""
    first = str((input_dir / "a.jpg").resolve())
    second = str((input_dir / "b.jpg").resolve())
    return IntegrityReport(
        findings=(
            IntegrityFinding(
                code=FindingCode.EXACT_DUPLICATE,
                message=(
                    "2 files have identical SHA-256 content "
                    f"{'a' * 64}."
                ),
                affected_paths=(first, second),
            ),
        )
    )


def make_result(
    tmp_path: Path,
    *,
    dry_run: bool = False,
    duplicate_report: ExactDuplicateReport | None = None,
    integrity_report: IntegrityReport | None = None,
    failed_analysis_paths: tuple[str, ...] = (),
    empty: bool = False,
    written_artifacts: tuple[str, ...] | None = None,
) -> CurationRunResult:
    """Create a completed immutable application result."""
    input_dir = (tmp_path / "input").resolve()
    output_dir = (tmp_path / "output").resolve()

    if empty:
        discovered_paths: tuple[str, ...] = ()
        analyzed_results: tuple[ImageResult, ...] = ()
        selected_results: tuple[ImageResult, ...] = ()
    else:
        first = make_image_result(str(input_dir / "a.jpg"), 0.9)
        second = make_image_result(str(input_dir / "b.jpg"), 0.8)
        discovered_paths = (
            str(input_dir / "b.jpg"),
            str(input_dir / "a.jpg"),
        )
        analyzed_results = (second, first)
        selected_results = (first, second)

    if written_artifacts is not None:
        artifacts = written_artifacts
    elif dry_run or empty:
        artifacts = ()
    elif duplicate_report is None:
        artifacts = (
            str(output_dir / "selected"),
            str(output_dir / "results.json"),
        )
    else:
        artifacts = (
            str(output_dir / "selected"),
            str(output_dir / "results.json"),
            str(output_dir / "duplicates.json"),
            str(output_dir / "integrity.json"),
        )

    return CurationRunResult(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        dry_run=dry_run,
        discovered_paths=discovered_paths,
        analyzed_results=analyzed_results,
        selected_results=selected_results,
        failed_analysis_paths=failed_analysis_paths,
        duplicate_report=duplicate_report,
        integrity_report=integrity_report,
        written_artifacts=artifacts,
    )


def make_project_brief(tmp_path: Path) -> ProjectBrief:
    """Create a brief containing fields excluded from the manifest."""
    return ProjectBrief(
        source_path=str((tmp_path / "brief.yaml").resolve()),
        schema_version=1,
        title="Manifest project",
        synopsis="Editorial synopsis must not be embedded.",
        themes=("theme",),
        subjects=("subject",),
        locations=("location",),
        visual_intent="Editorial intent must not be embedded.",
        desired_sequence_roles=("opener",),
        avoid=("avoid",),
        selection=SelectionSettings(),
        require_original_metadata=False,
        flag_missing_metadata=True,
        synthetic_images_allowed=False,
    )


def test_valid_manifest_construction(tmp_path: Path) -> None:
    """Build the approved manifest from request and result facts."""
    duplicate_report = make_duplicate_report(tmp_path / "input")
    integrity_report = make_integrity_report(tmp_path / "input")
    request = make_request(
        tmp_path,
        project_brief=make_project_brief(tmp_path),
    )
    result = make_result(
        tmp_path,
        duplicate_report=duplicate_report,
        integrity_report=integrity_report,
    )

    manifest = build_run_manifest(request, result)

    assert isinstance(manifest, RunManifest)
    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION == 1
    assert manifest.application_version == __version__
    assert manifest.request.to_dict() == {
        "input_dir": result.input_dir,
        "output_dir": result.output_dir,
        "top_n": 7,
        "threshold": 0.25,
        "model_name": "requested-model",
        "deduplicate": True,
        "dry_run": False,
    }
    assert manifest.summary.to_dict() == {
        "discovered_count": 2,
        "analyzed_count": 2,
        "failed_analysis_count": 0,
        "selected_count": 2,
        "fingerprint_failed_count": 0,
    }
    assert manifest.discovered_paths == result.discovered_paths
    assert manifest.analyzed_results == result.analyzed_results
    assert manifest.selected_results == result.selected_results
    assert manifest.artifacts == result.written_artifacts
    assert manifest.dry_run is False


def test_wrong_request_boundary_type_is_rejected(tmp_path: Path) -> None:
    """The request argument must enforce its public type."""
    with pytest.raises(TypeError, match="CurationRunRequest"):
        build_run_manifest(
            object(),  # type: ignore[arg-type]
            make_result(tmp_path),
        )


def test_wrong_result_boundary_type_is_rejected(tmp_path: Path) -> None:
    """The result argument must enforce its public type."""
    with pytest.raises(TypeError, match="CurationRunResult"):
        build_run_manifest(
            make_request(tmp_path),
            object(),  # type: ignore[arg-type]
        )


def test_input_path_mismatch_is_rejected(tmp_path: Path) -> None:
    """Request and result input paths must agree."""
    request = replace(
        make_request(tmp_path),
        input_dir=tmp_path / "different-input",
    )
    with pytest.raises(ValueError, match="input_dir"):
        build_run_manifest(request, make_result(tmp_path))


def test_output_path_mismatch_is_rejected(tmp_path: Path) -> None:
    """Request and result output paths must agree."""
    request = replace(
        make_request(tmp_path),
        output_dir=tmp_path / "different-output",
    )
    with pytest.raises(ValueError, match="output_dir"):
        build_run_manifest(request, make_result(tmp_path))


def test_dry_run_mismatch_is_rejected(tmp_path: Path) -> None:
    """Request and result dry-run values must agree."""
    with pytest.raises(ValueError, match="dry_run"):
        build_run_manifest(
            make_request(tmp_path, dry_run=True),
            make_result(tmp_path, dry_run=False),
        )


def test_manifest_and_nested_structures_are_immutable(tmp_path: Path) -> None:
    """The top-level manifest and nested structures are immutable."""
    manifest = build_run_manifest(
        make_request(tmp_path),
        make_result(tmp_path),
    )

    with pytest.raises(FrozenInstanceError):
        manifest.dry_run = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.request.top_n = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.summary.selected_count = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.failures.analysis_failed_paths = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.reports.integrity_report = None  # type: ignore[misc]

    assert isinstance(manifest.discovered_paths, tuple)
    assert isinstance(manifest.analyzed_results, tuple)
    assert isinstance(manifest.selected_results, tuple)
    assert isinstance(manifest.failures.fingerprint_failed_paths, tuple)
    assert isinstance(manifest.failures.analysis_failed_paths, tuple)
    assert isinstance(manifest.artifacts, tuple)


def test_exact_top_level_keys_and_order(tmp_path: Path) -> None:
    """Top-level serialization follows the authoritative order."""
    payload = build_run_manifest(
        make_request(tmp_path),
        make_result(tmp_path),
    ).to_dict()
    assert tuple(payload) == (
        "schema_version",
        "application_version",
        "request",
        "summary",
        "project_brief",
        "discovered_paths",
        "analyzed_results",
        "selected_results",
        "failures",
        "reports",
        "artifacts",
        "dry_run",
    )


def test_repeated_construction_and_serialization_are_deterministic(
    tmp_path: Path,
) -> None:
    """Equal inputs produce equal manifests and serialized payloads."""
    request = make_request(tmp_path)
    result = make_result(tmp_path)

    first = build_run_manifest(request, result)
    second = build_run_manifest(request, result)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert json.dumps(first.to_dict()) == json.dumps(second.to_dict())


def test_manifest_payload_is_json_compatible(tmp_path: Path) -> None:
    """The complete payload serializes without a custom encoder."""
    payload = build_run_manifest(
        make_request(tmp_path),
        make_result(tmp_path),
    ).to_dict()
    serialized = json.dumps(payload)
    assert '"schema_version": 1' in serialized
    assert f'"application_version": "{__version__}"' in serialized


def test_builder_does_not_mutate_request_or_result(tmp_path: Path) -> None:
    """Manifest construction leaves caller-owned facts unchanged."""
    request = make_request(
        tmp_path,
        project_brief=make_project_brief(tmp_path),
    )
    result = make_result(
        tmp_path,
        duplicate_report=make_duplicate_report(tmp_path / "input"),
        integrity_report=make_integrity_report(tmp_path / "input"),
    )
    request_before = request
    result_before = result
    result_payload_before = result.to_dict()

    build_run_manifest(request, result)

    assert request == request_before
    assert result == result_before
    assert result.to_dict() == result_payload_before


def test_empty_run_is_represented_without_artifacts(tmp_path: Path) -> None:
    """An empty completed run produces an in-memory manifest."""
    empty_duplicates = ExactDuplicateReport(
        input_count=0,
        fingerprinted_count=0,
        failed_count=0,
        unique_content_count=0,
        duplicate_file_count=0,
        groups=(),
        failed_paths=(),
    )
    manifest = build_run_manifest(
        make_request(tmp_path),
        make_result(
            tmp_path,
            duplicate_report=empty_duplicates,
            integrity_report=IntegrityReport(findings=()),
            empty=True,
        ),
    )

    assert manifest.summary.to_dict() == {
        "discovered_count": 0,
        "analyzed_count": 0,
        "failed_analysis_count": 0,
        "selected_count": 0,
        "fingerprint_failed_count": 0,
    }
    assert manifest.discovered_paths == ()
    assert manifest.analyzed_results == ()
    assert manifest.selected_results == ()
    assert manifest.artifacts == ()
    assert not (tmp_path / "output").exists()


def test_dry_run_is_represented_without_artifacts(tmp_path: Path) -> None:
    """A dry run produces a manifest without filesystem writes."""
    manifest = build_run_manifest(
        make_request(tmp_path, dry_run=True),
        make_result(tmp_path, dry_run=True),
    )
    assert manifest.request.dry_run is True
    assert manifest.dry_run is True
    assert manifest.artifacts == ()
    assert not (tmp_path / "output").exists()


def test_deduplication_enabled_preserves_existing_reports(
    tmp_path: Path,
) -> None:
    """Existing duplicate and integrity payloads are preserved."""
    duplicate_report = make_duplicate_report(tmp_path / "input")
    integrity_report = make_integrity_report(tmp_path / "input")
    manifest = build_run_manifest(
        make_request(tmp_path, deduplicate=True),
        make_result(
            tmp_path,
            duplicate_report=duplicate_report,
            integrity_report=integrity_report,
        ),
    )
    assert manifest.reports.to_dict() == {
        "duplicate_report": duplicate_report.to_dict(),
        "integrity_report": integrity_report.to_dict(),
    }


def test_deduplication_disabled_has_null_reports(tmp_path: Path) -> None:
    """Disabled deduplication has null report payloads."""
    manifest = build_run_manifest(
        make_request(tmp_path, deduplicate=False),
        make_result(
            tmp_path,
            duplicate_report=None,
            integrity_report=None,
        ),
    )
    assert manifest.reports.to_dict() == {
        "duplicate_report": None,
        "integrity_report": None,
    }
    assert manifest.failures.fingerprint_failed_paths == ()
    assert manifest.summary.fingerprint_failed_count == 0


def test_fingerprint_and_analysis_failures_remain_distinct(
    tmp_path: Path,
) -> None:
    """Failure collections preserve their distinct source facts."""
    fingerprint_failures = (
        str((tmp_path / "input" / "missing-a.jpg").resolve()),
        str((tmp_path / "input" / "missing-z.jpg").resolve()),
    )
    analysis_failures = (
        str((tmp_path / "input" / "corrupt-a.jpg").resolve()),
        str((tmp_path / "input" / "corrupt-z.jpg").resolve()),
    )
    manifest = build_run_manifest(
        make_request(tmp_path),
        make_result(
            tmp_path,
            duplicate_report=make_duplicate_report(
                tmp_path / "input",
                failed_paths=fingerprint_failures,
            ),
            integrity_report=make_integrity_report(tmp_path / "input"),
            failed_analysis_paths=analysis_failures,
        ),
    )
    assert manifest.failures.to_dict() == {
        "fingerprint_failed_paths": list(fingerprint_failures),
        "analysis_failed_paths": list(analysis_failures),
    }
    assert manifest.summary.fingerprint_failed_count == 2
    assert manifest.summary.failed_analysis_count == 2


def test_result_collection_order_is_preserved(tmp_path: Path) -> None:
    """Discovery, analysis, and selection order are not recomputed."""
    result = make_result(tmp_path)
    payload = build_run_manifest(
        make_request(tmp_path),
        result,
    ).to_dict()
    assert payload["discovered_paths"] == list(result.discovered_paths)
    assert [item["path"] for item in payload["analyzed_results"]] == [
        item.path for item in result.analyzed_results
    ]
    assert [item["path"] for item in payload["selected_results"]] == [
        item.path for item in result.selected_results
    ]


def test_project_brief_provenance_contains_only_approved_fields(
    tmp_path: Path,
) -> None:
    """Only source path, schema version, and title are embedded."""
    manifest = build_run_manifest(
        make_request(
            tmp_path,
            project_brief=make_project_brief(tmp_path),
        ),
        make_result(tmp_path),
    )
    assert manifest.project_brief is not None
    assert manifest.project_brief.to_dict() == {
        "source_path": str((tmp_path / "brief.yaml").resolve()),
        "schema_version": 1,
        "title": "Manifest project",
    }


def test_absent_project_brief_serializes_as_null(tmp_path: Path) -> None:
    """A request without a brief has null provenance."""
    payload = build_run_manifest(
        make_request(tmp_path, project_brief=None),
        make_result(tmp_path),
    ).to_dict()
    assert payload["project_brief"] is None


def test_application_version_and_requested_model_are_preserved(
    tmp_path: Path,
) -> None:
    """Version and model provenance use approved sources."""
    manifest = build_run_manifest(
        make_request(tmp_path),
        make_result(tmp_path),
    )
    assert manifest.application_version == __version__
    assert manifest.request.model_name == "requested-model"


def test_existing_written_artifact_order_is_preserved(
    tmp_path: Path,
) -> None:
    """The builder copies existing artifact facts without appending."""
    artifacts = (
        str((tmp_path / "output" / "second.json").resolve()),
        str((tmp_path / "output" / "first.json").resolve()),
    )
    manifest = build_run_manifest(
        make_request(tmp_path),
        make_result(tmp_path, written_artifacts=artifacts),
    )
    assert manifest.artifacts == artifacts
    assert manifest.to_dict()["artifacts"] == list(artifacts)
    assert all(
        not path.endswith("run_manifest.json")
        for path in manifest.artifacts
    )


def test_manifest_omits_unapproved_fields(tmp_path: Path) -> None:
    """The payload contains no inferred or out-of-scope facts."""
    payload = build_run_manifest(
        make_request(
            tmp_path,
            project_brief=make_project_brief(tmp_path),
        ),
        make_result(tmp_path),
    ).to_dict()
    serialized = json.dumps(payload).casefold()
    forbidden = (
        "timestamp",
        "uuid",
        "host",
        "process_id",
        "rubric",
        "critique",
        "gating",
        "decision",
        "fallback",
        "openclip_loaded",
        "technical_only",
        "synopsis",
        "themes",
        "subjects",
        "locations",
        "visual_intent",
        "desired_sequence_roles",
        "avoid",
        "semantic_prompts",
    )
    for field in forbidden:
        assert field not in serialized
