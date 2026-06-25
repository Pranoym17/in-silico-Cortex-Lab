from app.core.database import Base
from app import models


def test_foundation_models_are_registered():
    assert set(Base.metadata.tables) == {"users", "experiments", "blocks", "jobs", "results", "library_entries"}


def test_result_model_has_cp9_metadata_columns():
    result_columns = set(Base.metadata.tables["results"].columns.keys())

    assert {
        "owner_id",
        "s3_key",
        "format",
        "dtype",
        "shape",
        "vertex_count",
        "timestep_count",
        "sample_rate_hz",
        "model_name",
        "model_version",
        "metadata_json",
    }.issubset(result_columns)


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


def test_library_entry_model_has_public_metadata_columns():
    columns = set(Base.metadata.tables["library_entries"].columns.keys())

    assert {
        "experiment_id",
        "owner_id",
        "slug",
        "title",
        "description",
        "tags",
        "featured",
        "run_count",
        "published_at",
    }.issubset(columns)
