"""Behavioral tests for deterministic integrity reporting."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

from eas.clustering import ExactDuplicateGroup, ExactDuplicateReport
from eas.integrity import (
    FindingCode,
    IntegrityError,
    IntegrityFinding,
    IntegrityReport,
    generate_integrity_report,
)


def _group(*paths: str, cluster_id: int = 1, digest: str = "a" * 64) -> ExactDuplicateGroup:
    return ExactDuplicateGroup(
        cluster_id=cluster_id,
        sha256=digest,
        representative_path=min(paths, key=str.casefold),
        member_paths=tuple(paths),
        size_bytes=10,
    )


def _report(
    groups: tuple[ExactDuplicateGroup, ...] = (),
    failed_paths: tuple[str, ...] = (),
) -> ExactDuplicateReport:
    fingerprinted = sum(len(group.member_paths) for group in groups)
    return ExactDuplicateReport(
        input_count=fingerprinted + len(failed_paths),
        fingerprinted_count=fingerprinted,
        failed_count=len(failed_paths),
        unique_content_count=len(groups),
        duplicate_file_count=sum(group.duplicate_count for group in groups),
        groups=groups,
        failed_paths=failed_paths,
    )


def test_empty_source_report_produces_empty_report() -> None:
    report = generate_integrity_report(_report())
    assert report == IntegrityReport(findings=())
    assert report.to_dict() == {"findings": []}


def test_unique_content_group_does_not_produce_a_finding() -> None:
    assert generate_integrity_report(_report((_group("/a.jpg"),))).findings == ()


def test_duplicate_group_produces_exact_factual_finding() -> None:
    report = generate_integrity_report(_report((_group("/b.jpg", "/a.jpg"),)))
    finding = report.findings[0]
    assert finding.code == FindingCode.EXACT_DUPLICATE
    assert finding.affected_paths == ("/a.jpg", "/b.jpg")
    assert "a" * 64 in finding.message


def test_failed_paths_produce_individual_findings() -> None:
    report = generate_integrity_report(_report(failed_paths=("/z.jpg", "/a.jpg")))
    assert tuple(item.code for item in report.findings) == (
        FindingCode.FINGERPRINT_FAILED,
        FindingCode.FINGERPRINT_FAILED,
    )
    assert tuple(item.affected_paths for item in report.findings) == (
        ("/a.jpg",),
        ("/z.jpg",),
    )


def test_order_is_deterministic_across_source_permutations() -> None:
    first = _group("/z.jpg", "/y.jpg", cluster_id=2, digest="b" * 64)
    second = _group("/b.jpg", "/a.jpg", cluster_id=1, digest="a" * 64)
    left = generate_integrity_report(_report((first, second), ("/x.jpg", "/c.jpg")))
    right = generate_integrity_report(_report((second, first), ("/c.jpg", "/x.jpg")))
    assert left == right


def test_generation_does_not_mutate_source_report() -> None:
    source = _report((_group("/b.jpg", "/a.jpg"),), ("/missing.jpg",))
    before = source.to_dict()
    generate_integrity_report(source)
    assert source.to_dict() == before


def test_report_is_deeply_immutable() -> None:
    report = generate_integrity_report(_report((_group("/a.jpg", "/b.jpg"),)))
    with pytest.raises(FrozenInstanceError):
        report.findings = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.findings[0].message = "changed"  # type: ignore[misc]


def test_report_is_json_compatible() -> None:
    report = generate_integrity_report(
        _report((_group("/a.jpg", "/b.jpg"),), ("/missing.jpg",))
    )
    serialized = json.dumps(report.to_dict())
    assert "exact_duplicate" in serialized
    assert "fingerprint_failed" in serialized


def test_repeated_generation_is_equal() -> None:
    source = _report((_group("/a.jpg", "/b.jpg"),), ("/missing.jpg",))
    assert generate_integrity_report(source) == generate_integrity_report(source)


def test_wrong_report_boundary_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="ExactDuplicateReport"):
        generate_integrity_report(object())  # type: ignore[arg-type]


@pytest.mark.parametrize("code", ["", "unknown", 1, None])
def test_unknown_finding_codes_are_rejected(code: object) -> None:
    with pytest.raises(IntegrityError, match="unsupported"):
        IntegrityFinding(code=code, message="Fact", affected_paths=("/a.jpg",))  # type: ignore[arg-type]


@pytest.mark.parametrize("message", ["", " ", 1, None])
def test_empty_or_invalid_messages_are_rejected(message: object) -> None:
    with pytest.raises(IntegrityError, match="message"):
        IntegrityFinding(
            code=FindingCode.FINGERPRINT_FAILED,
            message=message,  # type: ignore[arg-type]
            affected_paths=("/a.jpg",),
        )


@pytest.mark.parametrize(
    "paths",
    [[], (), ("",), (1,), ("/a.jpg", "/a.jpg")],
)
def test_invalid_affected_paths_are_rejected(paths: object) -> None:
    with pytest.raises(IntegrityError, match="affected_paths"):
        IntegrityFinding(
            code=FindingCode.FINGERPRINT_FAILED,
            message="Fact",
            affected_paths=paths,  # type: ignore[arg-type]
        )


def test_malformed_findings_collection_is_rejected() -> None:
    with pytest.raises(IntegrityError, match="findings must be a tuple"):
        IntegrityReport(findings=[])  # type: ignore[arg-type]
    with pytest.raises(IntegrityError, match="IntegrityFinding"):
        IntegrityReport(findings=(object(),))  # type: ignore[arg-type]


def test_duplicate_failed_paths_are_rejected() -> None:
    with pytest.raises(IntegrityError, match="failed_paths must not contain duplicates"):
        generate_integrity_report(_report(failed_paths=("/a.jpg", "/a.jpg")))


def test_malformed_duplicate_group_is_rejected() -> None:
    group = ExactDuplicateGroup(
        cluster_id=1,
        sha256="not-a-digest",
        representative_path="/a.jpg",
        member_paths=("/a.jpg", "/b.jpg"),
        size_bytes=10,
    )
    with pytest.raises(IntegrityError, match="sha256"):
        generate_integrity_report(_report((group,)))


def test_integrity_report_has_no_decision_or_score_fields() -> None:
    report = generate_integrity_report(_report((_group("/a.jpg", "/b.jpg"),)))
    assert not hasattr(report, "score")
    assert not hasattr(report, "passed")
    assert not hasattr(report, "decision")
    assert set(report.to_dict()) == {"findings"}
