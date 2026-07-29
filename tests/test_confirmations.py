"""Asking before doing something powerful.

A capability set to *ask* must stop the action, wait for a real answer, and
refuse if none comes. These tests pin that behaviour, because the failure modes
are the dangerous kind: a prompt nobody answers must not become a yes.
"""

from __future__ import annotations

import threading
import time

import pytest

from jarvis.config.settings import Settings
from jarvis.security.confirm import ConfirmationBroker
from jarvis.security.manager import SecurityManager
from jarvis.security.policy import Capability, CapabilityMode
from jarvis.utils.exceptions import PermissionDenied


# -- the three states -------------------------------------------------------

def test_a_flag_still_means_on_or_off():
    """Callers written before "ask" existed keep working unchanged."""
    manager = SecurityManager({Capability.SHELL_EXEC: True,
                               Capability.FILE_WRITE: False})
    assert manager.mode(Capability.SHELL_EXEC) is CapabilityMode.ON
    assert manager.mode(Capability.FILE_WRITE) is CapabilityMode.OFF


def test_an_unreadable_mode_is_treated_as_refused():
    """A broken setting must never widen what the assistant may do."""
    assert CapabilityMode.coerce("wide-open") is CapabilityMode.OFF
    assert CapabilityMode.coerce("") is CapabilityMode.OFF


def test_settings_map_onto_the_three_states():
    settings = Settings(anthropic_api_key="k", log_file="", audit_log_path="",
                        allow_file_read=True, allow_file_write=True,
                        confirm_file_write=True, allow_shell=False,
                        confirm_shell=True)
    modes = SecurityManager.from_settings(settings).modes()
    assert modes["file_read"] == "on"
    assert modes["file_write"] == "ask"
    # Confirming a capability that is switched off does not switch it on.
    assert modes["shell_exec"] == "off"


def test_ask_is_not_reported_as_allowed():
    """"Allowed" describes what happens without a person present."""
    manager = SecurityManager({Capability.SHELL_EXEC: CapabilityMode.ASK})
    assert manager.is_allowed(Capability.SHELL_EXEC) is False


# -- the broker -------------------------------------------------------------

def test_a_granted_request_lets_the_action_through():
    broker = ConfirmationBroker(timeout=5)
    answer: list[bool] = []

    def asker():
        answer.append(broker.request(Capability.SHELL_EXEC, "rm -rf /tmp/x"))

    thread = threading.Thread(target=asker)
    thread.start()
    for _ in range(100):                      # wait for it to be queued
        if broker.pending():
            break
        time.sleep(0.01)
    pending = broker.pending()
    assert len(pending) == 1
    assert pending[0]["capability"] == "shell_exec"
    assert pending[0]["action"] == "rm -rf /tmp/x"
    assert broker.resolve(pending[0]["id"], True) is True
    thread.join(2)
    assert answer == [True]


def test_a_refused_request_stops_the_action():
    broker = ConfirmationBroker(timeout=5)
    answer: list[bool] = []
    thread = threading.Thread(
        target=lambda: answer.append(broker.request(Capability.FILE_WRITE, "w")))
    thread.start()
    while not broker.pending():
        time.sleep(0.01)
    broker.resolve(broker.pending()[0]["id"], False)
    thread.join(2)
    assert answer == [False]


def test_silence_is_a_no():
    """Nobody answering must never be read as permission."""
    broker = ConfirmationBroker(timeout=0.2)
    started = time.time()
    assert broker.request(Capability.SHELL_EXEC, "sleep") is False
    assert time.time() - started >= 0.2


def test_a_question_is_answered_once():
    broker = ConfirmationBroker(timeout=5)
    thread = threading.Thread(
        target=lambda: broker.request(Capability.SHELL_EXEC, "x"))
    thread.start()
    while not broker.pending():
        time.sleep(0.01)
    request_id = broker.pending()[0]["id"]
    assert broker.resolve(request_id, True) is True
    assert broker.resolve(request_id, False) is False    # too late
    thread.join(2)


def test_answering_something_unknown_changes_nothing():
    assert ConfirmationBroker().resolve("c999", True) is False


def test_secrets_never_reach_the_prompt():
    """The question is shown on screen, so it must not carry a key."""
    broker = ConfirmationBroker(timeout=5)
    threading.Thread(
        target=lambda: broker.request(
            Capability.SHELL_EXEC,
            "curl -H 'Authorization: Bearer sk-ant-api03-verysecrettoken'"),
        daemon=True).start()
    while not broker.pending():
        time.sleep(0.01)
    shown = broker.pending()[0]["action"]
    assert "verysecrettoken" not in shown


# -- the two together -------------------------------------------------------

def _ask_manager(broker: ConfirmationBroker) -> SecurityManager:
    return SecurityManager({Capability.SHELL_EXEC: CapabilityMode.ASK},
                           confirmer=broker)


def test_the_action_runs_once_the_user_agrees():
    broker = ConfirmationBroker(timeout=5)
    manager = _ask_manager(broker)
    outcome: list = []

    def run():
        try:
            manager.require(Capability.SHELL_EXEC, "echo hi")
            outcome.append("ran")
        except PermissionDenied as exc:
            outcome.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    while not broker.pending():
        time.sleep(0.01)
    broker.resolve(broker.pending()[0]["id"], True)
    thread.join(2)
    assert outcome == ["ran"]
    assert manager.audit_trail[-1].allowed is True
    assert "confirmed by user" in manager.audit_trail[-1].detail


def test_refusing_stops_the_action_and_is_audited():
    broker = ConfirmationBroker(timeout=5)
    manager = _ask_manager(broker)
    outcome: list = []

    def run():
        try:
            manager.require(Capability.SHELL_EXEC, "echo hi")
            outcome.append("ran")
        except PermissionDenied:
            outcome.append("stopped")

    thread = threading.Thread(target=run)
    thread.start()
    while not broker.pending():
        time.sleep(0.01)
    broker.resolve(broker.pending()[0]["id"], False)
    thread.join(2)
    assert outcome == ["stopped"]
    assert manager.audit_trail[-1].allowed is False


def test_ask_mode_with_nobody_to_ask_refuses():
    """No interface means no permission — never a silent yes."""
    manager = SecurityManager({Capability.SHELL_EXEC: CapabilityMode.ASK})
    with pytest.raises(PermissionDenied):
        manager.require(Capability.SHELL_EXEC, "echo hi")


def test_allowed_and_refused_capabilities_skip_the_question():
    broker = ConfirmationBroker(timeout=5)
    allowed = SecurityManager({Capability.FILE_READ: CapabilityMode.ON},
                              confirmer=broker)
    allowed.require(Capability.FILE_READ, "read")
    refused = SecurityManager({Capability.FILE_WRITE: CapabilityMode.OFF},
                              confirmer=broker)
    with pytest.raises(PermissionDenied):
        refused.require(Capability.FILE_WRITE, "write")
    assert broker.pending() == []      # neither one asked anybody
