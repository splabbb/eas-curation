"""Application-level orchestration for deterministic curation runs."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eas.run_manifest import RunManifest

from eas.brief import ProjectBrief
from eas.clustering import ExactDuplicateReport, find_exact_duplicates
from eas.integrity import IntegrityReport, generate_integrity_report
from eas.pipeline import ImageCurationPipeline, ImageResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CurationRunRequest:
    """Immutable configuration for one curation run.

    Attributes:
        input_dir: Directory containing source images.
        output_dir: Directory receiving selected files and JSON reports.
        top_n: Maximum number of eligible images to select.
        threshold: Minimum technical quality score in the inclusive range 0..1.
        model_name: OpenCLIP model name used by the vision analyzer.
        deduplicate: Whether exact duplicate detection runs before analysis.
        dry_run: Whether all filesystem writes are disabled.
        project_brief: Optional validated project brief.
    """

    input_dir: Path
    output_dir: Path
    top_n: int
    threshold: float
    model_name: str
    deduplicate: bool = True
    dry_run: bool = False
    project_brief: ProjectBrief | None = None

    def __post_init__(self) -> None:
        """Validate the application boundary without modifying caller input."""
        if not isinstance(self.input_dir, Path):
            raise TypeError("input_dir must be a pathlib.Path")
        if not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be a pathlib.Path")
        if isinstance(self.top_n, bool) or not isinstance(self.top_n, int):
            raise TypeError("top_n must be an integer")
        if self.top_n < 1:
            raise ValueError("top_n must be at least 1")
        if isinstance(self.threshold, bool) or not isinstance(
            self.threshold,
            (int, float),
        ):
            raise TypeError("threshold must be a number")
        if not math.isfinite(float(self.threshold)):
            raise ValueError("threshold must be finite")
        if not 0.0 <= float(self.threshold) <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if not isinstance(self.model_name, str):
            raise TypeError("model_name must be a string")
        if not self.model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        if not isinstance(self.deduplicate, bool):
            raise TypeError("deduplicate must be a boolean")
        if not isinstance(self.dry_run, bool):
            raise TypeError("dry_run must be a boolean")
        if self.project_brief is not None and not isinstance(
            self.project_brief,
            ProjectBrief,
        ):
            raise TypeError(
                "project_brief must be a ProjectBrief or None"
            )


@dataclass(frozen=True)
class CurationRunResult:
    """Immutable structured result for one complete curation run."""

    input_dir: str
    output_dir: str
    dry_run: bool
    discovered_paths: tuple[str, ...]
    analyzed_results: tuple[ImageResult, ...]
    selected_results: tuple[ImageResult, ...]
    failed_analysis_paths: tuple[str, ...]
    duplicate_report: ExactDuplicateReport | None
    integrity_report: IntegrityReport | None
    written_artifacts: tuple[str, ...]
    manifest: RunManifest | None = None

    @property
    def discovered_count(self) -> int:
        """Return the number of discovered source assets."""
        return len(self.discovered_paths)

    @property
    def analyzed_count(self) -> int:
        """Return the number of successfully analyzed assets."""
        return len(self.analyzed_results)

    @property
    def selected_count(self) -> int:
        """Return the number of selected assets."""
        return len(self.selected_results)

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible representation."""
        return {
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "dry_run": self.dry_run,
            "summary": {
                "discovered_count": self.discovered_count,
                "analyzed_count": self.analyzed_count,
                "failed_analysis_count": len(
                    self.failed_analysis_paths
                ),
                "selected_count": self.selected_count,
            },
            "discovered_paths": list(self.discovered_paths),
            "analyzed_results": [
                result.to_dict()
                for result in self.analyzed_results
            ],
            "selected_results": [
                result.to_dict()
                for result in self.selected_results
            ],
            "failed_analysis_paths": list(
                self.failed_analysis_paths
            ),
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
            "written_artifacts": list(self.written_artifacts),
            "manifest": (
                self.manifest.to_dict()
                if self.manifest is not None
                else None
            ),
        }


class CurationRunService:
    """Coordinate existing curation components through one public boundary."""

    def run(self, request: CurationRunRequest) -> CurationRunResult:
        """Execute one deterministic curation run.

        Args:
            request: Validated immutable run configuration.

        Returns:
            Immutable run facts, selections, reports, and artifact paths.

        Raises:
            TypeError: If the request has the wrong boundary type.
            NotADirectoryError: If the input directory does not exist.
            PermissionError: If required filesystem access is denied.
            ValueError: If an existing component rejects configuration.
            OSError: If an output operation fails.
        """
        if not isinstance(request, CurationRunRequest):
            raise TypeError(
                "request must be a CurationRunRequest"
            )

        input_dir = request.input_dir.expanduser().resolve()
        output_dir = request.output_dir.expanduser().resolve()

        logger.info(
            "Starting curation run: input=%s output=%s dry_run=%s",
            input_dir,
            output_dir,
            request.dry_run,
        )

        pipeline = ImageCurationPipeline(
            {
                "top_n": request.top_n,
                "threshold": float(request.threshold),
                "model_name": request.model_name.strip(),
            }
        )

        discovered = pipeline.discover_images(str(input_dir))

        duplicate_report: ExactDuplicateReport | None = None
        integrity_report: IntegrityReport | None = None

        if request.deduplicate:
            duplicate_report = find_exact_duplicates(discovered)
            integrity_report = generate_integrity_report(
                duplicate_report
            )
            analysis_paths = duplicate_report.representative_paths
        else:
            analysis_paths = list(discovered)

        analyzed = pipeline.process_images(analysis_paths)
        selected = pipeline.select_top_n(analyzed)

        successful_paths = {
            str(Path(result.path).expanduser().resolve())
            for result in analyzed
        }
        failed_analysis_paths = tuple(
            str(path)
            for path in analysis_paths
            if str(path.expanduser().resolve())
            not in successful_paths
        )

        written_artifacts: tuple[str, ...] = ()

        if not request.dry_run and discovered:
            written_artifacts = self._write_outputs(
                pipeline=pipeline,
                selected=selected,
                output_dir=output_dir,
                duplicate_report=duplicate_report,
                integrity_report=integrity_report,
            )

        provisional_result = CurationRunResult(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            dry_run=request.dry_run,
            discovered_paths=tuple(
                str(path)
                for path in discovered
            ),
            analyzed_results=tuple(analyzed),
            selected_results=tuple(selected),
            failed_analysis_paths=failed_analysis_paths,
            duplicate_report=duplicate_report,
            integrity_report=integrity_report,
            written_artifacts=written_artifacts,
        )

        from eas.run_manifest import build_run_manifest

        manifest = build_run_manifest(
            request,
            provisional_result,
        )

        if request.dry_run or not discovered:
            result = replace(
                provisional_result,
                manifest=manifest,
            )
        else:
            manifest_path = output_dir / "run_manifest.json"
            self._write_json_atomic(
                manifest_path,
                manifest.to_dict(),
            )
            result = replace(
                provisional_result,
                written_artifacts=(
                    *written_artifacts,
                    str(manifest_path),
                ),
                manifest=manifest,
            )

        logger.info(
            "Curation run completed: discovered=%d analyzed=%d "
            "failed_analysis=%d selected=%d artifacts=%d",
            result.discovered_count,
            result.analyzed_count,
            len(result.failed_analysis_paths),
            result.selected_count,
            len(result.written_artifacts),
        )
        return result

    def _write_outputs(
        self,
        *,
        pipeline: ImageCurationPipeline,
        selected: list[ImageResult],
        output_dir: Path,
        duplicate_report: ExactDuplicateReport | None,
        integrity_report: IntegrityReport | None,
    ) -> tuple[str, ...]:
        """Write selected files and factual reports."""
        pipeline.save_results(selected, str(output_dir))

        artifacts: list[Path] = [
            output_dir / "selected",
            output_dir / "results.json",
        ]

        if duplicate_report is not None:
            duplicate_path = output_dir / "duplicates.json"
            self._write_json_atomic(
                duplicate_path,
                duplicate_report.to_dict(),
            )
            artifacts.append(duplicate_path)

        if integrity_report is not None:
            integrity_path = output_dir / "integrity.json"
            self._write_json_atomic(
                integrity_path,
                integrity_report.to_dict(),
            )
            artifacts.append(integrity_path)

        return tuple(str(path) for path in artifacts)

    @staticmethod
    def _write_json_atomic(
        target: Path,
        payload: dict[str, Any],
    ) -> None:
        """Write one UTF-8 JSON document using atomic replacement."""
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.tmp")
        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)


def run_curation(
    request: CurationRunRequest,
) -> CurationRunResult:
    """Execute a curation run through the canonical application service."""
    return CurationRunService().run(request)


__all__ = [
    "CurationRunRequest",
    "CurationRunResult",
    "CurationRunService",
    "run_curation",
]
