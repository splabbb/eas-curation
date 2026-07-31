"""Command-line interface for the EAS image-curation pipeline."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import click

from eas.brief import ProjectBrief, load_project_brief
from eas.pipeline import ImageCurationPipeline

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    """Configure process-wide logging for the CLI."""

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def _resolve_brief(brief_path: str | None) -> ProjectBrief | None:
    """Load a project brief when one was supplied."""

    if brief_path is None:
        return None

    return load_project_brief(brief_path)


def _build_config(
    *,
    top_n: int,
    threshold: float,
    model: str,
    cache_dir: str,
    deduplicate: bool,
    explain: bool,
    verbose: bool,
    brief: ProjectBrief | None,
) -> dict[str, Any]:
    """Build the pipeline configuration dictionary."""

    return {
        "top_n": top_n,
        "threshold": threshold,
        "model_name": model,
        "cache_dir": cache_dir,
        "deduplicate": deduplicate,
        "explain": explain,
        "verbose": verbose,
        "project_brief": brief.to_dict() if brief is not None else None,
    }


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--input",
    "input_path",
    "-i",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        path_type=Path,
    ),
    required=True,
    help="Directory containing source images.",
)
@click.option(
    "--output",
    "output_path",
    "-o",
    type=click.Path(
        file_okay=False,
        dir_okay=True,
        path_type=Path,
    ),
    default=Path("./output"),
    show_default=True,
    help="Directory for selected images and JSON reports.",
)
@click.option(
    "--top-n",
    type=click.IntRange(min=1),
    default=None,
    help=(
        "Number of final images to select. When omitted, uses "
        "selection.final_count from --brief, otherwise 10."
    ),
)
@click.option(
    "--threshold",
    type=click.FloatRange(min=0.0, max=1.0),
    default=0.5,
    show_default=True,
    help="Minimum quality score required for selection.",
)
@click.option(
    "--model",
    type=str,
    default="ViT-B/32",
    show_default=True,
    help="OpenCLIP model name.",
)
@click.option(
    "--cache-dir",
    type=click.Path(
        file_okay=False,
        dir_okay=True,
        path_type=Path,
    ),
    default=Path("./.eas_cache"),
    show_default=True,
    help="Directory reserved for model and embedding caches.",
)
@click.option(
    "--brief",
    "brief_path",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
    default=None,
    help="Validated YAML project brief.",
)
@click.option(
    "--deduplicate/--no-deduplicate",
    default=True,
    show_default=True,
    help="Remove byte-identical files before expensive image analysis.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Analyze and rank images without writing reports or selected files.",
)
@click.option(
    "--explain",
    is_flag=True,
    help="Reserve detailed-analysis mode for pipeline components that support it.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable debug logging and full exception tracebacks.",
)
def main(
    input_path: Path,
    output_path: Path,
    top_n: int | None,
    threshold: float,
    model: str,
    cache_dir: Path,
    brief_path: Path | None,
    deduplicate: bool,
    dry_run: bool,
    explain: bool,
    verbose: bool,
) -> None:
    """Curate, deduplicate, score, rank, and export image selections."""

    _configure_logging(verbose)

    try:
        brief = _resolve_brief(
            str(brief_path) if brief_path is not None else None
        )
        effective_top_n = (
            top_n
            if top_n is not None
            else brief.selection.final_count
            if brief is not None
            else 10
        )

        config = _build_config(
            top_n=effective_top_n,
            threshold=threshold,
            model=model,
            cache_dir=str(cache_dir.expanduser()),
            deduplicate=deduplicate,
            explain=explain,
            verbose=verbose,
            brief=brief,
        )
        pipeline = ImageCurationPipeline(config)

        resolved_input = input_path.expanduser().resolve()
        resolved_output = output_path.expanduser().resolve()

        click.echo("\nStarting image curation pipeline")
        click.echo(f"Input: {resolved_input}")
        click.echo(f"Output: {resolved_output}")
        click.echo(f"Final selection size: {effective_top_n}")
        click.echo(
            "Exact duplicate detection: "
            + ("enabled" if deduplicate else "disabled")
        )
        click.echo(f"Dry run: {'yes' if dry_run else 'no'}")

        if brief is not None:
            click.echo(f"Project brief: {brief.title}")
            click.echo(f"Brief source: {brief.source_path}")

        results = pipeline.run(
            input_dir=str(resolved_input),
            output_dir=str(resolved_output),
            dry_run=dry_run,
        )

        click.echo("\nPipeline completed")
        click.echo(f"Selected images: {len(results)}")

        if dry_run:
            click.echo("No files were written because --dry-run was used.")
        else:
            click.echo(f"Selected files: {resolved_output / 'selected'}")
            click.echo(f"Ranking report: {resolved_output / 'results.json'}")
            if deduplicate:
                click.echo(
                    f"Duplicate report: {resolved_output / 'duplicates.json'}"
                )

    except KeyboardInterrupt:
        click.echo("\nPipeline interrupted by user.", err=True)
        raise click.exceptions.Exit(130)
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError) as exc:
        logger.error("Configuration or input error: %s", exc, exc_info=verbose)
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        logger.exception("Fatal pipeline error")
        if verbose:
            raise click.ClickException(str(exc)) from exc
        click.echo(
            "\nPipeline failed. Re-run with --verbose for a full traceback.",
            err=True,
        )
        raise click.exceptions.Exit(1) from exc


if __name__ == "__main__":
    main()
