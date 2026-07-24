from __future__ import annotations

import json

import build_evidence


def passing_sections() -> dict:
    return {
        "backup": {"artifact": "backup-2026.tar", "creation_result": "pass", "validation_result": "pass"},
        "restore": {"result": "pass", "duration_seconds": 12.5, "verified": {"organizations": {"count": 2}}},
        "replay": {
            "topic": "alert.created.v1",
            "group": "signalchord-alert-projector-v1",
            "partitions": [0],
            "requested_time_range": {"to": "2026-01-01T00:00:00Z"},
            "offsets_before": {"alert.created.v1-0": 5},
            "offsets_after": {"alert.created.v1-0": 4},
            "result": "pass",
        },
        "python_poison_message": {
            "source_topic": "graph.mutation-requested.v1",
            "dlq_topic": "graph.mutation-requested.v1.dlq",
            "source_offset": 3,
            "dlq_offset": 0,
            "metadata_assertions": {"origin": "pass", "error_type": "pass"},
            "healthy_following_message_result": "pass",
        },
        "go_poison_message": {
            "source_topic": "alert.created.v1",
            "dlq_topic": "alert.created.v1.dlq",
            "source_offset": 6,
            "dlq_offset": 0,
            "metadata_assertions": {"origin": "pass"},
            "healthy_following_message_result": "pass",
        },
        "transient_failure": {
            "dlq_absent": True,
            "acknowledgment_absent": True,
            "retry_redelivery_result": "pass",
        },
        "duplicate_suppression": {"assertions": {"row_count_unchanged": "pass"}, "result": "pass"},
        "cleanup": {"result": "pass"},
    }


def test_build_evidence_all_passing_sections_yields_overall_pass() -> None:
    evidence = build_evidence.build_evidence(
        run_id="123",
        git_sha="abc123",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:10:00+00:00",
        environment="kind-recovery-drill",
        sections=passing_sections(),
    )

    assert evidence["overall_result"] == "pass"
    assert evidence["failed_assertions"] == []
    assert evidence["total_duration_seconds"] == 600.0
    assert evidence["schema_version"] == 1


def test_validate_evidence_accepts_a_well_formed_passing_document() -> None:
    evidence = build_evidence.build_evidence(
        run_id="123",
        git_sha="abc123",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:10:00+00:00",
        environment="kind-recovery-drill",
        sections=passing_sections(),
    )

    assert build_evidence.validate_evidence(evidence) == []


def test_validate_evidence_reports_every_missing_top_level_field() -> None:
    failures = build_evidence.validate_evidence({})
    for field in build_evidence.REQUIRED_TOP_LEVEL_FIELDS:
        assert any(field in failure for failure in failures), field


def test_validate_evidence_reports_missing_section_fields() -> None:
    evidence = build_evidence.build_evidence(
        run_id="1",
        git_sha="a",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        environment="test",
        sections={},
    )
    failures = build_evidence.validate_evidence(evidence)
    assert any("backup.artifact" in failure for failure in failures)
    assert any("restore.result" in failure for failure in failures)


def test_collect_failed_assertions_flags_a_failing_result_field() -> None:
    sections = passing_sections()
    sections["restore"]["result"] = "fail"

    failed = build_evidence.collect_failed_assertions(sections)

    assert "restore.result" in failed


def test_collect_failed_assertions_includes_section_reported_failures() -> None:
    sections = passing_sections()
    sections["python_poison_message"]["failures"] = ["dlq envelope missing error_type"]

    failed = build_evidence.collect_failed_assertions(sections)

    assert "python_poison_message: dlq envelope missing error_type" in failed


def test_collect_failed_assertions_flags_missing_section_entirely() -> None:
    sections = passing_sections()
    del sections["cleanup"]

    failed = build_evidence.collect_failed_assertions(sections)

    assert "cleanup: section missing or malformed" in failed


def test_build_evidence_any_failure_flips_overall_result_to_fail() -> None:
    sections = passing_sections()
    sections["transient_failure"]["dlq_absent"] = False

    evidence = build_evidence.build_evidence(
        run_id="1",
        git_sha="a",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:05+00:00",
        environment="test",
        sections=sections,
    )

    assert evidence["overall_result"] == "fail"
    assert "transient_failure.dlq_absent" in evidence["failed_assertions"]


def test_load_sections_reports_missing_files_as_failures(tmp_path) -> None:
    (tmp_path / "backup.json").write_text(json.dumps({"artifact": "x", "creation_result": "pass", "validation_result": "pass"}))

    sections, failures = build_evidence.load_sections(tmp_path)

    assert sections["backup"]["artifact"] == "x"
    assert sections["restore"] == {}
    assert any("restore.json" in failure for failure in failures)


def test_load_sections_reports_malformed_json(tmp_path) -> None:
    (tmp_path / "backup.json").write_text("{not json")

    _, failures = build_evidence.load_sections(tmp_path)

    assert any("backup.json" in failure for failure in failures)


def test_main_writes_artifact_even_when_drill_failed(tmp_path) -> None:
    sections_dir = tmp_path / "sections"
    sections_dir.mkdir()
    sections = passing_sections()
    sections["cleanup"]["result"] = "fail"
    for name, value in sections.items():
        (sections_dir / f"{name}.json").write_text(json.dumps(value))
    output = tmp_path / "evidence.json"

    exit_code = build_evidence.main(
        [
            "--sections-dir",
            str(sections_dir),
            "--run-id",
            "42",
            "--git-sha",
            "deadbeef",
            "--started-at",
            "2026-01-01T00:00:00+00:00",
            "--finished-at",
            "2026-01-01T00:05:00+00:00",
            "--environment",
            "kind-recovery-drill",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 1
    assert output.exists()
    written = json.loads(output.read_text())
    assert written["overall_result"] == "fail"
    assert "cleanup.result" in written["failed_assertions"]


def test_main_succeeds_when_every_section_passes(tmp_path) -> None:
    sections_dir = tmp_path / "sections"
    sections_dir.mkdir()
    for name, value in passing_sections().items():
        (sections_dir / f"{name}.json").write_text(json.dumps(value))
    output = tmp_path / "evidence.json"

    exit_code = build_evidence.main(
        [
            "--sections-dir",
            str(sections_dir),
            "--run-id",
            "42",
            "--git-sha",
            "deadbeef",
            "--started-at",
            "2026-01-01T00:00:00+00:00",
            "--finished-at",
            "2026-01-01T00:05:00+00:00",
            "--environment",
            "kind-recovery-drill",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    written = json.loads(output.read_text())
    assert written["overall_result"] == "pass"
