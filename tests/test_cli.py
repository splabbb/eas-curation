"""CLI tests."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

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
