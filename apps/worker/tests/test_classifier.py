from proofhire_contracts import ArtifactPriority, SourceArtifactType

from proofhire_worker.ingestion.classifier import classify, is_excluded, is_secret_like_path


def test_readme_is_p0():
    artifact_type, priority = classify("README.md")
    assert artifact_type == SourceArtifactType.README
    assert priority == ArtifactPriority.P0


def test_package_json_is_p0_manifest():
    artifact_type, priority = classify("package.json")
    assert artifact_type == SourceArtifactType.DEPENDENCY_MANIFEST
    assert priority == ArtifactPriority.P0


def test_github_workflow_is_p0_ci():
    artifact_type, priority = classify(".github/workflows/ci.yml")
    assert artifact_type == SourceArtifactType.CI_CONFIG
    assert priority == ArtifactPriority.P0


def test_dockerfile_is_p0():
    artifact_type, priority = classify("infra/docker/Dockerfile")
    assert artifact_type == SourceArtifactType.DOCKER
    assert priority == ArtifactPriority.P0


def test_test_file_is_p1():
    _, priority = classify("apps/api/tests/test_jwt.py")
    assert priority == ArtifactPriority.P1


def test_arbitrary_source_file_is_p2():
    _, priority = classify("apps/api/proofhire_api/routers/github.py")
    assert priority == ArtifactPriority.P2


def test_node_modules_is_excluded():
    assert is_excluded("node_modules/foo/index.js") is True


def test_binary_extension_is_excluded():
    assert is_excluded("assets/logo.png") is True


def test_env_file_is_excluded_and_flagged_secret_like():
    assert is_excluded(".env") is True
    assert is_secret_like_path(".env.production") is True


def test_normal_source_file_is_not_excluded():
    assert is_excluded("apps/api/proofhire_api/main.py") is False
