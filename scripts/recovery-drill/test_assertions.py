from __future__ import annotations

import assertions


def valid_python_envelope() -> dict:
    return {
        "origin": "graph-projector",
        "error_type": "PermanentMutationError",
        "error": "unsupported mutation_type: bogus",
        "failed_at": "2026-01-01T00:00:00+00:00",
        "source_topic": "graph.mutation-requested.v1",
        "source_partition": 0,
        "source_offset": 3,
        "key": "invalid",
        "headers": [],
        "failed_event": {"event_id": "e-1"},
    }


def test_assert_dlq_envelope_accepts_a_well_formed_python_envelope() -> None:
    failures = assertions.assert_dlq_envelope(
        valid_python_envelope(),
        expected_origin="graph-projector",
        expected_source_topic="graph.mutation-requested.v1",
        content_field="failed_event",
    )
    assert failures == []


def test_assert_dlq_envelope_flags_missing_fields() -> None:
    envelope = valid_python_envelope()
    del envelope["error_type"]
    del envelope["failed_event"]

    failures = assertions.assert_dlq_envelope(
        envelope,
        expected_origin="graph-projector",
        expected_source_topic="graph.mutation-requested.v1",
        content_field="failed_event",
    )

    assert any("error_type" in f for f in failures)
    assert any("failed_event" in f for f in failures)


def test_assert_dlq_envelope_flags_wrong_origin_and_topic() -> None:
    envelope = valid_python_envelope()
    envelope["origin"] = "wrong-worker"
    envelope["source_topic"] = "wrong.topic.v1"

    failures = assertions.assert_dlq_envelope(
        envelope,
        expected_origin="graph-projector",
        expected_source_topic="graph.mutation-requested.v1",
        content_field="failed_event",
    )

    assert any("origin" in f for f in failures)
    assert any("source_topic" in f for f in failures)


def test_assert_dlq_envelope_works_for_go_shaped_envelope_with_value_field() -> None:
    envelope = {
        "origin": "realtime-gateway",
        "error_type": "*errors.errorString",
        "error": "realtime event missing tenant_id",
        "failed_at": "2026-01-01T00:00:00Z",
        "source_topic": "alert.created.v1",
        "source_partition": 0,
        "source_offset": 9,
        "key": "alert-1",
        "headers": [],
        "value": '{"event_type":"alert.created.v1"}',
    }

    failures = assertions.assert_dlq_envelope(
        envelope,
        expected_origin="realtime-gateway",
        expected_source_topic="alert.created.v1",
        content_field="value",
    )

    assert failures == []


def test_assert_offset_advanced_past_passes_when_offset_moves_beyond_target() -> None:
    assert assertions.assert_offset_advanced_past(before=3, after=5, target_offset=3) == []


def test_assert_offset_advanced_past_fails_when_offset_does_not_move() -> None:
    failures = assertions.assert_offset_advanced_past(before=3, after=3, target_offset=3)
    assert any("did not advance" in f for f in failures)


def test_assert_offset_advanced_past_fails_when_still_at_or_before_target() -> None:
    failures = assertions.assert_offset_advanced_past(before=1, after=3, target_offset=4)
    assert any("has not passed target offset" in f for f in failures)


def test_assert_offset_unchanged_passes_when_equal() -> None:
    assert assertions.assert_offset_unchanged(before=2, after=2) == []


def test_assert_offset_unchanged_fails_when_it_moved() -> None:
    failures = assertions.assert_offset_unchanged(before=2, after=3)
    assert any("advanced for a transient failure" in f for f in failures)


def test_assert_no_dlq_message_passes_when_empty() -> None:
    assert assertions.assert_no_dlq_message([]) == []


def test_assert_no_dlq_message_fails_when_present() -> None:
    failures = assertions.assert_no_dlq_message([{"value": "x"}])
    assert "1" in failures[0]


def test_assert_exactly_one_dlq_message_passes() -> None:
    assert assertions.assert_exactly_one_dlq_message([{"value": "x"}]) == []


def test_assert_exactly_one_dlq_message_fails_on_zero_or_many() -> None:
    assert assertions.assert_exactly_one_dlq_message([]) != []
    assert assertions.assert_exactly_one_dlq_message([{"a": 1}, {"b": 2}]) != []


def test_assert_row_count_unchanged_passes_when_both_equal_expected() -> None:
    assert assertions.assert_row_count_unchanged(before=1, after=1) == []


def test_assert_row_count_unchanged_fails_on_duplicate_row() -> None:
    failures = assertions.assert_row_count_unchanged(before=1, after=2)
    assert any("after replay = 2" in f for f in failures)


def test_assert_row_count_unchanged_fails_if_baseline_was_already_wrong() -> None:
    failures = assertions.assert_row_count_unchanged(before=0, after=1)
    assert any("before replay = 0" in f for f in failures)
