from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


ContentHash = Annotated[str, Field(pattern=r"^sha256:[a-fA-F0-9]{3,}$")]


class DisplaySettings(BaseModel):
    mode: Literal["center", "full_bleed", "side_by_side"] = "center"


class BaseStimulusBlock(BaseModel):
    id: str
    condition: str | None = None
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    content_hash: ContentHash


class ImageBlock(BaseStimulusBlock):
    type: Literal["image"]
    s3_key: str
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    display: DisplaySettings = Field(default_factory=DisplaySettings)


class TextBlock(BaseStimulusBlock):
    type: Literal["text"]
    text: str = Field(min_length=1)
    voice: str = "kokoro_default"

    @model_validator(mode="after")
    def validate_word_count(self) -> "TextBlock":
        if len(self.text.split()) > 1024:
            raise ValueError("text blocks cannot exceed 1024 words")
        return self


class AudioBlock(BaseStimulusBlock):
    type: Literal["audio"]
    s3_key: str
    mime_type: Literal["audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"]
    channels: int = Field(ge=1, le=2)
    sample_rate_hz: int = Field(gt=0)


StimulusBlock = Annotated[Union[ImageBlock, TextBlock, AudioBlock], Field(discriminator="type")]


class RunSettings(BaseModel):
    hrf_offset_ms: int = 5000
    target_sample_rate_hz: int = 2
    surface: Literal["fsaverage5"] = "fsaverage5"
    atlas: Literal["desikan-killiany"] = "desikan-killiany"


class RunExperimentRequest(BaseModel):
    blocks: list[StimulusBlock] = Field(min_length=1, max_length=50)
    settings: RunSettings = Field(default_factory=RunSettings)

    @model_validator(mode="after")
    def validate_timeline(self) -> "RunExperimentRequest":
        sorted_blocks = sorted(self.blocks, key=lambda block: block.start_ms)
        previous_end = 0
        for block in sorted_blocks:
            if block.start_ms < previous_end:
                raise ValueError("stimulus blocks cannot overlap")
            previous_end = block.start_ms + block.duration_ms

            if block.type == "image" and not 500 <= block.duration_ms <= 30000:
                raise ValueError("image block duration must be between 500ms and 30000ms")
            if block.type == "audio" and block.duration_ms > 60000:
                raise ValueError("audio block duration cannot exceed 60000ms")

        if previous_end > 300000:
            raise ValueError("experiment duration cannot exceed 300000ms")
        return self


class RunExperimentResponse(BaseModel):
    job_id: str
    experiment_id: str
    status: Literal["queued"]
    stream_url: str
    user_id: str | None = None

