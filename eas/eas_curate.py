#!/usr/bin/env python3
"""EAS Curate - CLI entry point"""
import logging
import sys
from pathlib import Path
import click
from eas.pipeline import ImageCurationPipeline
from eas.config import DEFAULT_MODEL, DEFAULT_CACHE_DIR, DEFAULT_THRESHOLD, DEFAULT_TOP_N, DEFAULT_OUTPUT_DIR, LOG_FORMAT, LOG_DATE_FORMAT

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    if not verbose:
        logging.getLogger("transformers").setLevel(logging.WARNING)
        logging.getLogger("torch").setLevel(logging.WARNING)

@click.command()
@click.argument("input_dir", type=click.Path(exists=False, file_okay=False))
@click.option("--top-n", type=int, default=DEFAULT_TOP_N)
@click.option("--explain/--no-explain", default=False)
@click.option("--verbose/--no-verbose", default=False)
@click.option("--output-dir", type=click.Path(file_okay=False), default=str(DEFAULT_OUTPUT_DIR))
@click.option("--cache-dir", type=click.Path(file_okay=False), default=str(DEFAULT_CACHE_DIR))
@click.option("--threshold", type=float, default=DEFAULT_THRESHOLD)
@click.option("--model", type=str, default=DEFAULT_MODEL)
@click.option("--dry-run/--no-dry-run", default=False)
def main(input_dir, top_n, explain, verbose, output_dir, cache_dir, threshold, model, dry_run):
    """Automated image curation pipeline."""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    try:
        input_path = Path(input_dir)
        if not input_path.exists():
            click.echo(f"Error: {input_dir} not found", err=True)
            sys.exit(1)
        config = {"top_n": top_n, "threshold": threshold, "model_name": model, "cache_dir": cache_dir, "explain": explain, "verbose": verbose}
        pipeline = ImageCurationPipeline(config)
        click.echo(f"Starting pipeline... Input: {input_dir}")
        results = pipeline.run(input_dir=input_dir, output_dir=output_dir, dry_run=dry_run)
        click.echo(f"Done! Found {len(results)} images")
        if not dry_run:
            click.echo(f"Results saved to: {output_dir}")
    except KeyboardInterrupt:
        click.echo("Interrupted", err=True)
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=verbose)
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
