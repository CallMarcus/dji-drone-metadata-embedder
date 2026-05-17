"""Tests for scripts/generate_changelog.py.

The historical bug this guards against: on a tag push event the workflow
calls the script with ``--version 1.3.1`` *after* v1.3.1 has been pushed,
so ``get_latest_release_tag()`` was returning v1.3.1 itself and the script
found zero commits "since v1.3.1". Tags between v1.1.2 and v1.3.0 silently
produced empty changelogs as a result. The fix accepts an ``exclude`` arg
so callers can ask for the latest tag *other than* the one being published.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import List


def _load_module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "generate_changelog.py"
    spec = importlib.util.spec_from_file_location("generate_changelog", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _patch_tags(monkeypatch, module, tags: List[str]) -> None:
    """Replace run_git_command so the tag list lookup returns *tags*."""
    def fake(args):
        # `tag --list --sort=-version:refname` — return the canned list.
        if args[:2] == ["tag", "--list"]:
            return "\n".join(tags)
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(module, "run_git_command", fake)


class TestGetLatestReleaseTag:
    def test_returns_newest_tag_when_no_exclude(self, monkeypatch):
        module = _load_module()
        _patch_tags(monkeypatch, module, ["v1.3.1", "v1.3.0", "v1.2.0", "v1.1.2"])
        assert module.get_latest_release_tag() == "v1.3.1"

    def test_skips_excluded_v_prefixed_tag(self, monkeypatch):
        """When publishing v1.3.1, asking for the previous tag must return v1.3.0."""
        module = _load_module()
        _patch_tags(monkeypatch, module, ["v1.3.1", "v1.3.0", "v1.2.0", "v1.1.2"])
        assert module.get_latest_release_tag(exclude="v1.3.1") == "v1.3.0"

    def test_skips_excluded_bare_version(self, monkeypatch):
        """Workflows pass the version without the v prefix; both forms must match."""
        module = _load_module()
        _patch_tags(monkeypatch, module, ["v1.3.1", "v1.3.0"])
        assert module.get_latest_release_tag(exclude="1.3.1") == "v1.3.0"

    def test_skips_excluded_when_repo_uses_bare_tags(self, monkeypatch):
        """A tag named ``1.3.1`` (no leading v) is excluded just the same."""
        module = _load_module()
        _patch_tags(monkeypatch, module, ["1.3.1", "1.3.0"])
        assert module.get_latest_release_tag(exclude="1.3.1") == "1.3.0"

    def test_ignores_non_version_tags(self, monkeypatch):
        module = _load_module()
        _patch_tags(monkeypatch, module, ["release-candidate", "v1.3.1", "v1.3.0"])
        assert module.get_latest_release_tag(exclude="1.3.1") == "v1.3.0"

    def test_returns_none_when_only_excluded_tag_exists(self, monkeypatch):
        """First-ever release: nothing earlier to compare against."""
        module = _load_module()
        _patch_tags(monkeypatch, module, ["v1.3.1"])
        assert module.get_latest_release_tag(exclude="1.3.1") is None

    def test_returns_none_when_no_tags(self, monkeypatch):
        module = _load_module()
        _patch_tags(monkeypatch, module, [""])
        assert module.get_latest_release_tag() is None
