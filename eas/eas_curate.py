"""EAS Curation CLI Entry Point"""
import sys
import logging
from pathlib import Path

import click
from eas.pipeline import ImageCurationPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True),
    required=True,
    help="Input directory containing images",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="./output",
    help="Output directory for results",
)
@click.option(
    "--top-n",
    type=int,
    default=10,
    help="Number of top images to select",
)
@click.option(
    "--threshold",
    type=float,
    default=0.5,
    help="Quality score threshold",
)
@click.option(
    "--model",
    type=str,
    default="ViT-B/32",
    help="CLIP model to use",
)
@click.option(
    "--cache-dir",
    type=click.Path(),
    default="./.eas_cache",
    help="Cache directory for embeddings",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run without saving results",
)
@click.option(
    "--explain",
    is_flag=True,
    help="Show detailed analysis",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output",
)
def main(
    input: str,
    output: str,
    top_n: int,
    threshold: float,
    model: str,
    cache_dir: str,
    dry_run: bool,
    explain: bool,
    verbose: bool,
):
    """🖼️  EAS Image Curation Pipeline - Automated image quality assessment and selection."""

    try:
        input_dir = Path(input)
        output_dir = Path(output)

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

        results = pipeline.run(input_dir=str(input_dir), output_dir=str(output_dir), dry_run=dry_run)

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
