"""CLI tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from click.testing import CliRunner

from eas.application import CurationRunRequest
from eas.eas_curate import main


def test_cli_requires_arguments() -> None:
    """CLI should fail without required arguments."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [],
    )
    assert result.exit_code != 0


def test_cli_dry_run(
    tmp_path: Path,
) -> None:
    """Dry run should succeed."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--input",
            str(tmp_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0


def test_cli_delegates_to_application_service(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """CLI should construct one typed request and delegate execution."""
    captured: list[CurationRunRequest] = []

    def fake_run_curation(
        request: CurationRunRequest,
    ) -> SimpleNamespace:
        captured.append(request)
        return SimpleNamespace(
            selected_count=0,
            failed_analysis_paths=(),
            written_artifacts=(),
            duplicate_report=None,
        )

    monkeypatch.setattr(
        "eas.eas_curate.run_curation",
        fake_run_curation,
    )

    output_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--input",
            str(tmp_path),
            "--output",
            str(output_dir),
            "--top-n",
            "7",
            "--threshold",
            "0.25",
            "--model",
            "test-model",
            "--no-deduplicate",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(captured) == 1

    request = captured[0]
    assert request.input_dir == tmp_path.resolve()
    assert request.output_dir == output_dir.resolve()
    assert request.top_n == 7
    assert request.threshold == 0.25
    assert request.model_name == "test-model"
    assert request.deduplicate is False
    assert request.dry_run is True
    assert request.project_brief is None
    assert "Pipeline completed" in result.output
    assert "Selected images: 0" in result.output
    assert "No files were written" in result.output


def test_cli_reports_application_artifacts(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """CLI should present artifacts returned by the application boundary."""

    def fake_run_curation(
        request: CurationRunRequest,
    ) -> SimpleNamespace:
        output = request.output_dir
        return SimpleNamespace(
            selected_count=2,
            failed_analysis_paths=("/failed.jpg",),
            written_artifacts=(
                str(output / "selected"),
                str(output / "results.json"),
                str(output / "duplicates.json"),
                str(output / "integrity.json"),
            ),
            duplicate_report=object(),
        )

    monkeypatch.setattr(
        "eas.eas_curate.run_curation",
        fake_run_curation,
    )

    output_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--input",
            str(tmp_path),
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Selected images: 2" in result.output
    assert "Failed image analyses: 1" in result.output
    assert f"Selected files: {output_dir.resolve() / 'selected'}" in result.output
    assert f"Ranking report: {output_dir.resolve() / 'results.json'}" in result.output
    assert f"Duplicate report: {output_dir.resolve() / 'duplicates.json'}" in result.output
    assert f"Integrity report: {output_dir.resolve() / 'integrity.json'}" in result.output
