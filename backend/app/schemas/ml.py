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
