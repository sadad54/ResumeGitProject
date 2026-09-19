"""Error monitoring (Track C) — specifically the PRD §27 guarantee that an
error tracker doesn't become the place private source code leaks to."""

from proofhire_api.error_monitoring import _scrub, configure_error_monitoring


def test_is_a_no_op_without_a_dsn():
    assert configure_error_monitoring("", environment="test", service="api") is False


def test_scrubber_strips_local_variables_from_every_frame():
    """A stack trace from evidence extraction has the user's file contents in
    local variables. Those must not leave the process."""
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"function": "extract", "vars": {"content": "SECRET_KEY=abc"}},
                            {"function": "inner", "vars": {"snippet": "private code"}},
                        ]
                    }
                }
            ]
        }
    }

    scrubbed = _scrub(event, {})

    for frame in scrubbed["exception"]["values"][0]["stacktrace"]["frames"]:
        assert "vars" not in frame


def test_scrubber_drops_request_body_and_redacts_credential_headers():
    event = {
        "request": {
            "data": {"selected_text": "pasted job description"},
            "headers": {
                "Authorization": "Bearer eyJ...",
                "Cookie": "session=abc",
                "X-Api-Key": "k",
                "Content-Type": "application/json",
            },
        }
    }

    scrubbed = _scrub(event, {})

    assert "data" not in scrubbed["request"]
    headers = scrubbed["request"]["headers"]
    assert headers["Authorization"] == "[redacted]"
    assert headers["Cookie"] == "[redacted]"
    assert headers["X-Api-Key"] == "[redacted]"
    assert headers["Content-Type"] == "application/json"


def test_scrubber_tags_the_event_with_the_trace_id():
    scrubbed = _scrub({}, {})
    assert "trace_id" in scrubbed["tags"]
