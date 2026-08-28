"""Production packaging and mobile release safety contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_container_packages_every_runtime_model_without_secrets():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "training/artifacts/structural" in dockerfile
    assert "training/artifacts/semantic" in dockerfile
    assert "structural-2026.02/artifacts" in dockerfile
    assert "GEMINI_API_KEY" not in dockerfile
    assert dockerignore.startswith("**\n")


def test_container_uses_production_only_dependencies():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    requirements = (ROOT / "backend/requirements-prod.txt").read_text(
        encoding="utf-8"
    )

    assert "requirements-prod.txt" in dockerfile
    assert "opencv-python-headless" in requirements.lower()
    for development_package in ("pytest", "respx", "qrcode", "pandas"):
        assert development_package not in requirements.lower()


def test_render_blueprint_is_free_and_secretless():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    prepare_script = (ROOT / "deploy/render/prepare.ps1").read_text(
        encoding="utf-8"
    )

    assert "plan: free" in blueprint
    assert "runtime: static" in blueprint
    assert "region: singapore" in blueprint
    assert "QRGUARD_GEMINI_API_KEY" not in blueprint
    assert "GEMINI_API_KEY" not in blueprint
    assert "name: qrguard-api-osswt" in blueprint
    assert "qrguard-api-osswt.onrender.com" in prepare_script
    assert "qrguard-app-osswt.onrender.com" in blueprint


def test_android_release_uses_api_36_https_and_real_signing():
    gradle = (ROOT / "app/android/app/build.gradle.kts").read_text(encoding="utf-8")
    manifest = (ROOT / "app/android/app/src/main/AndroidManifest.xml").read_text(
        encoding="utf-8"
    )
    settings = (ROOT / "app/lib/services/settings_service.dart").read_text(
        encoding="utf-8"
    )

    assert 'applicationId = "com.osswt.qrguard"' in gradle
    assert "targetSdk = 36" in gradle
    assert 'signingConfigs.getByName("debug")' not in gradle
    assert 'android:usesCleartextTraffic="false"' in manifest
    assert "QRGUARD_BACKEND_URL" in settings


def test_web_release_has_https_backend_injection_and_privacy_policy():
    script = (ROOT / "deploy/web/deploy.ps1").read_text(encoding="utf-8")
    policy = (ROOT / "deploy/web/privacy.html").read_text(encoding="utf-8")

    assert "QRGUARD_BACKEND_URL=$BackendUrl" in script
    assert "QRGUARD_CORS_ORIGINS=$webUrl" in script
    assert "does not persist uploaded images or raw payloads" in policy
