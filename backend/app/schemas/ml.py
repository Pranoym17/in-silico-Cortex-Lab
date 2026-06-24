from uuid import UUID

from pydantic import BaseModel, Field


class RsaRequest(BaseModel):
    job_id_a: UUID
    job_id_b: UUID


class MdsPoint(BaseModel):
    x: float
    y: float
    label: str
    index: int


class RsaResponse(BaseModel):
    job_id_a: UUID
    job_id_b: UUID
    rsa_score: float = Field(ge=-1.0, le=1.0)
    rdm_a: list[list[float]]
    rdm_b: list[list[float]]
    labels_a: list[str]
    labels_b: list[str]
    mds_a: list[MdsPoint]
    mds_b: list[MdsPoint]
    block_count: int
    vertex_count: int


class CognitiveStatePoint(BaseModel):
    timestep: int
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    scores: dict[str, float]


class CognitiveStatesResponse(BaseModel):
    job_id: UUID
    classifier_version: str
    states: list[CognitiveStatePoint]


class OptimizerRequest(BaseModel):
    target_region: str = Field(min_length=1)
    direction: str = Field(pattern="^(maximize|minimize)$")
    generations: int = Field(default=5, ge=1, le=20)
    candidates_per_generation: int = Field(default=10, ge=1, le=50)
    seed_prompt: str | None = Field(default=None, max_length=1000)


class OptimizerStartResponse(BaseModel):
    optimizer_job_id: UUID
    status: str
    stream_url: str


class OptimizerCandidate(BaseModel):
    text: str
    score: float


class OptimizerGenerationEvent(BaseModel):
    optimizer_job_id: UUID
    generation: int
    best_score: float
    best_stimulus: str
    candidates: list[OptimizerCandidate]


class OptimizerResult(BaseModel):
    optimizer_job_id: UUID
    status: str
    target_region: str
    direction: str
    best_score: float
    best_stimulus: str
    generations: list[OptimizerGenerationEvent]
