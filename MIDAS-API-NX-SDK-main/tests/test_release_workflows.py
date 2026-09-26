"""Regression guards for the two independent package release routes.

GitHub's release event cannot use path filters. A prefix guard is therefore
part of the publish safety boundary: a JavaScript release must never enter the
PyPI jobs, and a Python release must never enter the npm job.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
NPM_WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"
NPM_PACKAGE = ROOT / "packages" / "typescript"


def _workflow(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_python_publish_route_requires_py_tag_prefix():
    workflow = _workflow(PYTHON_WORKFLOW)

    assert workflow.count("startsWith(github.event.release.tag_name, 'py-v')") == 2
    assert 'tag="${RELEASE_TAG#py-v}"' in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "npm publish" not in workflow
    assert "paths:" not in workflow


def test_npm_publish_route_requires_js_tag_prefix_and_oidc():
    workflow = _workflow(NPM_WORKFLOW)

    assert workflow.count("startsWith(github.event.release.tag_name, 'js-v')") == 1
    assert 'tag="${RELEASE_TAG#js-v}"' in workflow
    assert "id-token: write" in workflow
    assert "node-version: \"24\"" in workflow
    assert 'npm install --global "npm@^11.5.1"' in workflow
    assert "npm publish --access public" in workflow
    assert "gh-action-pypi-publish" not in workflow
    assert "paths:" not in workflow


def test_npm_release_notes_are_packaged_and_prefix_aware():
    package = json.loads((NPM_PACKAGE / "package.json").read_text(encoding="utf-8"))
    releasing = (NPM_PACKAGE / "RELEASING.md").read_text(encoding="utf-8")
    changelog = (NPM_PACKAGE / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "CHANGELOG.md" in package["files"]
    assert "js-vX.Y.Z" in releasing
    assert "preceding `js-v*` tag explicitly" in releasing
    assert "automatic selection" in releasing and "`py-v*`" in releasing
    assert "## Unreleased" in changelog
