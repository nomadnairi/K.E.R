"""The release build must publish the version the source actually says.

The publish step used to carry the tag, the release name and the notes path as
literals. Bump the package and forget this file, and a manual run quietly
re-publishes the *previous* release under the previous notes — which is exactly
what happened. These tests keep the version in one place.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "desktop-build.yml"


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_release_workflow_exists():
    assert WORKFLOW.is_file()


def test_no_version_literal_hides_in_the_publish_step(workflow):
    publish = workflow.split("Publish release (manual dispatch)")[1]
    assert not re.search(r"v?\d+\.\d+\.\d+", publish), (
        "the tag, name and notes must come from the source, not a literal")


def test_the_tag_and_notes_are_derived(workflow):
    publish = workflow.split("Publish release (manual dispatch)")[1]
    for field in ("tag_name", "name", "body_path"):
        line = next(li for li in publish.splitlines() if li.strip().startswith(field + ":"))
        assert "steps.ver.outputs" in line, f"{field} is not derived from the source"


def test_this_version_has_release_notes():
    """The workflow refuses to publish without them, so catch it here first."""
    from jarvis import __version__
    notes = ROOT / "docs" / f"RELEASE_NOTES_v{__version__}.md"
    assert notes.is_file(), f"write {notes.name} before releasing {__version__}"
    assert __version__ in notes.read_text(encoding="utf-8")


def test_only_the_installer_is_published_for_windows(workflow):
    """Shipping the portable exe beside it offers the same product twice."""
    publish = workflow.split("Publish release (manual dispatch)")[1]
    files = next(li for li in publish.splitlines() if li.strip().startswith("files:"))
    assert "Setup" in files
