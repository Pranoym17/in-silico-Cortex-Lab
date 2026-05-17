from app.core.database import Base
from app import models


def test_foundation_models_are_registered():
    assert set(Base.metadata.tables) == {"users", "experiments", "blocks", "jobs", "results"}


def test_expected_enums_match_contract():
    assert [status.value for status in models.ExperimentStatus] == ["draft", "ready", "archived"]
    assert [block_type.value for block_type in models.BlockType] == ["image", "text", "audio"]
    assert [status.value for status in models.JobStatus] == [
        "queued",
        "warming",
        "running",
        "streaming",
        "complete",
        "failed",
        "cancelled",
    ]

