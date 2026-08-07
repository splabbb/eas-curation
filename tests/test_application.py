"""Behavioral tests for the unified curation run contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest
from PIL import Image

from eas.application import (
    CurationRunRequest,
    CurationRunResult,
    CurationRunService,
    run_curation,
)
from eas.integrity import FindingCode
from eas.vision import VisionAnalyzer


@pytest.fixture(autouse=True)
def disable_optional_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep application tests deterministic and independent of OpenCLIP."""

    def skip_model_loading(analyzer: VisionAnalyzer) -> None:
        analyzer.model = None
        analyzer.preprocess = None
        analyzer.tokenizer = None
        analyzer.text_features = None

    monkeypatch.setattr(
        VisionAnalyzer,
        "_load_model",
        skip_model_loading,
    )


def create_image(
    path: Path,
    *,
    color: tuple[int, int, int] = (128, 128, 128),
) -> Path:
    """Create one small valid RGB image."""
    Image.new(
        "RGB",
        (32, 32),
        color,
    ).save(path)
    return path


def make_request(
    input_dir: Path,
    output_dir: Path,
    *,
    deduplicate: bool = True,
    dry_run: bool = True,
    top_n: int = 10,
    threshold: float = 0.0,
) -> CurationRunRequest:
    """Create a valid application request for one test run."""
    return CurationRunRequest(
        input_dir=input_dir,
        output_dir=output_dir,
        top_n=top_n,
        threshold=threshold,
        model_name="ViT-B/32",
        deduplicate=deduplicate,
        dry_run=dry_run,
    )


def test_request_is_immutable(
    tmp_path: Path,
) -> None:
    """The public request contract must be immutable."""
    request = make_request(
        tmp_path,
        tmp_path / "output",
    )

    with pytest.raises(FrozenInstanceError):
        request.top_n = 20  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "exception"),
    [
        ("input_dir", "input", TypeError),
        ("output_dir", "output", TypeError),
        ("top_n", True, TypeError),
        ("top_n", 0, ValueError),
        ("threshold", True, TypeError),
        ("threshold", -0.1, ValueError),
        ("threshold", 1.1, ValueError),
        ("threshold", float("nan"), ValueError),
        ("model_name", 1, TypeError),
        ("model_name", " ", ValueError),
        ("deduplicate", 1, TypeError),
        ("dry_run", 0, TypeError),
        ("project_brief", object(), TypeError),
    ],
)
def test_request_rejects_invalid_boundary_values(
    tmp_path: Path,
    field: str,
    value: object,
    exception: type[Exception],
) -> None:
    """Invalid application-boundary values must fail explicitly."""
    values: dict[str, object] = {
        "input_dir": tmp_path,
        "output_dir": tmp_path / "output",
        "top_n": 10,
        "threshold": 0.0,
        "model_name": "ViT-B/32",
        "deduplicate": True,
        "dry_run": True,
        "project_brief": None,
    }
    values[field] = value

    with pytest.raises(exception):
        CurationRunRequest(**values)  # type: ignore[arg-type]


def test_service_rejects_wrong_request_type() -> None:
    """The service must enforce its public request boundary."""
    with pytest.raises(TypeError, match="CurationRunRequest"):
        CurationRunService().run(object())  # type: ignore[arg-type]


def test_missing_input_directory_raises(
    tmp_path: Path,
) -> None:
    """A missing input directory must retain the existing exception."""
    request = make_request(
        tmp_path / "missing",
        tmp_path / "output",
    )

    with pytest.raises(NotADirectoryError):
        run_curation(request)


def test_empty_input_directory_returns_empty_result(
    tmp_path: Path,
) -> None:
    """An empty directory is a successful run with no image results."""
    output_dir = tmp_path / "output"
    request = make_request(
        tmp_path,
        output_dir,
    )

    result = run_curation(request)

    assert result.discovered_paths == ()
    assert result.analyzed_results == ()
    assert result.selected_results == ()
    assert result.failed_analysis_paths == ()
    assert result.duplicate_report is not None
    assert result.duplicate_report.input_count == 0
    assert result.integrity_report is not None
    assert result.integrity_report.findings == ()
    assert result.written_artifacts == ()
    assert result.manifest is not None
    assert result.manifest.summary.discovered_count == 0
    assert result.manifest.artifacts == ()
    assert not output_dir.exists()


def test_dry_run_is_write_free(
    tmp_path: Path,
) -> None:
    """Dry runs must analyze and select without writing any output."""
    create_image(tmp_path / "image.jpg")
    output_dir = tmp_path / "output"

    result = run_curation(
        make_request(
            tmp_path,
            output_dir,
            dry_run=True,
        )
    )

    assert result.discovered_count == 1
    assert result.analyzed_count == 1
    assert result.selected_count == 1
    assert result.written_artifacts == ()
    assert result.manifest is not None
    assert result.manifest.dry_run is True
    assert result.manifest.artifacts == ()
    assert not output_dir.exists()


def test_deduplication_uses_one_representative(
    tmp_path: Path,
) -> None:
    """Byte-identical files must be analyzed through one representative."""
    first = create_image(tmp_path / "a.jpg")
    second = tmp_path / "b.jpg"
    second.write_bytes(first.read_bytes())

    result = run_curation(
        make_request(
            tmp_path,
            tmp_path / "output",
            deduplicate=True,
        )
    )

    assert result.discovered_count == 2
    assert result.analyzed_count == 1
    assert result.selected_count == 1
    assert result.duplicate_report is not None
    assert result.duplicate_report.duplicate_file_count == 1
    assert result.duplicate_report.representative_paths == [
        first.resolve()
    ]

    assert result.integrity_report is not None
    assert len(result.integrity_report.findings) == 1
    assert (
        result.integrity_report.findings[0].code
        == FindingCode.EXACT_DUPLICATE
    )
    assert result.integrity_report.findings[0].affected_paths == (
        str(first.resolve()),
        str(second.resolve()),
    )


def test_deduplication_can_be_disabled(
    tmp_path: Path,
) -> None:
    """Disabling deduplication must analyze every discovered path."""
    first = create_image(tmp_path / "a.jpg")
    second = tmp_path / "b.jpg"
    second.write_bytes(first.read_bytes())

    result = run_curation(
        make_request(
            tmp_path,
            tmp_path / "output",
            deduplicate=False,
        )
    )

    assert result.discovered_count == 2
    assert result.analyzed_count == 2
    assert result.selected_count == 2
    assert result.duplicate_report is None
    assert result.integrity_report is None


def test_corrupt_images_are_preserved_as_failed_analysis_paths(
    tmp_path: Path,
) -> None:
    """Skipped corrupt assets must remain visible in structured results."""
    valid = create_image(tmp_path / "valid.jpg")
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"not-an-image")

    result = run_curation(
        make_request(
            tmp_path,
            tmp_path / "output",
            deduplicate=False,
        )
    )

    assert result.discovered_count == 2
    assert result.analyzed_count == 1
    assert result.selected_count == 1
    assert result.analyzed_results[0].path == str(valid.resolve())
    assert result.failed_analysis_paths == (
        str(corrupt.resolve()),
    )


def test_output_run_writes_expected_artifacts(
    tmp_path: Path,
) -> None:
    """A non-dry run must export selected files and factual reports."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    first = create_image(input_dir / "a.jpg")
    second = input_dir / "b.jpg"
    second.write_bytes(first.read_bytes())

    output_dir = tmp_path / "output"
    result = run_curation(
        make_request(
            input_dir,
            output_dir,
            dry_run=False,
        )
    )

    expected_artifacts = (
        str(output_dir.resolve() / "selected"),
        str(output_dir.resolve() / "results.json"),
        str(output_dir.resolve() / "duplicates.json"),
        str(output_dir.resolve() / "integrity.json"),
        str(output_dir.resolve() / "run_manifest.json"),
    )

    assert result.written_artifacts == expected_artifacts
    assert (output_dir / "selected").is_dir()
    assert (output_dir / "results.json").is_file()
    assert (output_dir / "duplicates.json").is_file()
    assert (output_dir / "integrity.json").is_file()
    assert (output_dir / "run_manifest.json").is_file()
    assert result.manifest is not None
    manifest_data = json.loads(
        (output_dir / "run_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest_data == result.manifest.to_dict()
    assert result.manifest.artifacts == expected_artifacts[:-1]
    assert (
        str(output_dir.resolve() / "run_manifest.json")
        not in result.manifest.artifacts
    )
    assert not (output_dir / "run_manifest.json.tmp").exists()

    selected_files = tuple(
        (output_dir / "selected").iterdir()
    )
    assert len(selected_files) == 1

    duplicate_data = json.loads(
        (output_dir / "duplicates.json").read_text(
            encoding="utf-8"
        )
    )
    integrity_data = json.loads(
        (output_dir / "integrity.json").read_text(
            encoding="utf-8"
        )
    )

    assert duplicate_data["summary"]["input_count"] == 2
    assert duplicate_data["summary"]["duplicate_file_count"] == 1
    assert (
        integrity_data["findings"][0]["code"]
        == FindingCode.EXACT_DUPLICATE
    )


def test_disabled_deduplication_writes_only_legacy_outputs(
    tmp_path: Path,
) -> None:
    """No duplicate or integrity report is written when disabled."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "image.jpg")

    output_dir = tmp_path / "output"
    result = run_curation(
        make_request(
            input_dir,
            output_dir,
            deduplicate=False,
            dry_run=False,
        )
    )

    assert result.written_artifacts == (
        str(output_dir.resolve() / "selected"),
        str(output_dir.resolve() / "results.json"),
        str(output_dir.resolve() / "run_manifest.json"),
    )
    assert (output_dir / "results.json").is_file()
    assert (output_dir / "run_manifest.json").is_file()
    assert not (output_dir / "duplicates.json").exists()
    assert not (output_dir / "integrity.json").exists()
    assert result.manifest is not None
    assert result.manifest.reports.duplicate_report is None
    assert result.manifest.reports.integrity_report is None


def test_result_is_immutable_and_json_compatible(
    tmp_path: Path,
) -> None:
    """Run results must be frozen and serializable without encoders."""
    create_image(tmp_path / "image.jpg")

    result = run_curation(
        make_request(
            tmp_path,
            tmp_path / "output",
        )
    )

    assert isinstance(result, CurationRunResult)

    with pytest.raises(FrozenInstanceError):
        result.dry_run = False  # type: ignore[misc]

    serialized = json.dumps(result.to_dict())

    assert "discovered_count" in serialized
    assert "selected_results" in serialized
    assert str((tmp_path / "image.jpg").resolve()) in serialized
    assert result.manifest is not None
    assert json.loads(serialized)["manifest"] == result.manifest.to_dict()


def test_repeated_dry_runs_are_equal(
    tmp_path: Path,
) -> None:
    """Repeated runs over unchanged input must return equal facts."""
    create_image(
        tmp_path / "b.jpg",
        color=(64, 64, 64),
    )
    create_image(
        tmp_path / "a.jpg",
        color=(192, 192, 192),
    )
    request = make_request(
        tmp_path,
        tmp_path / "output",
    )

    first = run_curation(request)
    second = run_curation(request)

    assert first == second
    assert first.discovered_paths == (
        str((tmp_path / "a.jpg").resolve()),
        str((tmp_path / "b.jpg").resolve()),
    )
    assert first.manifest is not None
    assert first.manifest == second.manifest


def test_empty_non_dry_run_preserves_legacy_no_write_behavior(
    tmp_path: Path,
) -> None:
    """An empty non-dry run must not create output artifacts."""
    output_dir = tmp_path / "output"

    result = run_curation(
        make_request(
            tmp_path,
            output_dir,
            dry_run=False,
        )
    )

    assert result.discovered_paths == ()
    assert result.selected_results == ()
    assert result.written_artifacts == ()
    assert result.duplicate_report is not None
    assert result.integrity_report is not None
    assert result.manifest is not None
    assert result.manifest.artifacts == ()
    assert result.manifest.summary.discovered_count == 0
    assert not output_dir.exists()


def test_manifest_write_failure_propagates_and_preserves_existing_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A manifest write failure must not roll back existing outputs."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "image.jpg")
    output_dir = tmp_path / "output"
    service = CurationRunService()
    original_write_json_atomic = service._write_json_atomic
    expected_error = PermissionError(
        "manifest destination is not writable"
    )

    def fail_manifest_only(
        target: Path,
        payload: dict[str, object],
    ) -> None:
        if target.name == "run_manifest.json":
            raise expected_error
        original_write_json_atomic(target, payload)

    monkeypatch.setattr(
        service,
        "_write_json_atomic",
        fail_manifest_only,
    )

    with pytest.raises(PermissionError) as raised:
        service.run(
            make_request(
                input_dir,
                output_dir,
                dry_run=False,
            )
        )

    assert raised.value is expected_error
    assert (output_dir / "selected").is_dir()
    assert (output_dir / "results.json").is_file()
    assert (output_dir / "duplicates.json").is_file()
    assert (output_dir / "integrity.json").is_file()
    assert not (output_dir / "run_manifest.json").exists()


def test_result_without_attached_manifest_serializes_null(
    tmp_path: Path,
) -> None:
    """The compatible manifest field defaults to null."""
    result = CurationRunResult(
        input_dir=str(tmp_path.resolve()),
        output_dir=str((tmp_path / "output").resolve()),
        dry_run=True,
        discovered_paths=(),
        analyzed_results=(),
        selected_results=(),
        failed_analysis_paths=(),
        duplicate_report=None,
        integrity_report=None,
        written_artifacts=(),
    )

    assert result.manifest is None
    assert result.to_dict()["manifest"] is None
