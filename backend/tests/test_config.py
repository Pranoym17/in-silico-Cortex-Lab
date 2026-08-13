from app.core.config import Settings


def test_cors_origins_supports_legacy_and_multiple_configured_origins():
    settings = Settings(
        frontend_origin="https://app.cortexlab.example/",
        frontend_origins="https://staging.cortexlab.example, https://app.cortexlab.example/",
    )

    assert settings.cors_origins == [
        "https://app.cortexlab.example",
        "https://staging.cortexlab.example",
    ]
