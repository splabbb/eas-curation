#!/usr/bin/env python3
"""CLI entry point for EAS curation pipeline."""

import sys
import logging
import click
from pathlib import Path
from eas.pipeline import ImageCurationPipeline

logger = logging.getLogger(__name__)


@click.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="./output",
    help="Output directory for curated images",
)
@click.option(
    "--top-n",
    "-n",
    type=int,
    default=100,
    help="Number of top images to select",
)
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.5,
    help="Quality score threshold (0-1)",
)
@click.option(
    "--model",
    "-m",
    type=str,
    default="ViT-B/32",
    help="CLIP model to use",
)
@click.option(
    "--cache-dir",
    "-c",
    type=click.Path(),
    default="./.eas_cache",
    help="Cache directory for embeddings",
)
@click.option(
    "--explain/--no-explain",
    default=False,
    help="Provide explanations for scores",
)
@click.option(
    "--verbose/--quiet",
    "-v/-q",
    default=False,
    help="Verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run without saving results",
)
def main(
    input_dir,
    output_dir,
    top_n,
    threshold,
    model,
    cache_dir,
    explain,
    verbose,
    dry_run,
):
    """Curate images using embedding-based quality scoring."""
    try:
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        config = {
            "top_n": top_n,
            "threshold": threshold,
            "model_name": model,
            "cache_dir": cache_dir,
            "explain": explain,
            "verbose": verbose,
        }

        pipeline = ImageCurationPipeline(config)

        click.echo(f"\n🚀 Starting image curation pipeline...")
        click.echo(f"📁 Input: {input_dir}")
        click.echo(f"📊 Looking for top {top_n} images\n")

        results = pipeline.run(input_dir=input_dir, output_dir=output_dir, dry_run=dry_run)

        click.echo(f"\n✅ Pipeline completed!")
        click.echo(f"📸 Found {len(results)} images")

        if not dry_run:
            click.echo(f"💾 Results saved to: {output_dir}")

    except KeyboardInterrupt:
        click.echo("\n⚠️  Pipeline interrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=verbose)
        click.echo(f"\n❌ Pipeline failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
