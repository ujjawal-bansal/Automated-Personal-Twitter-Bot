"""Typed contracts shared by Gemini structured output and local validation."""
from typing import Literal

from pydantic import BaseModel, Field


class Idea(BaseModel):
    topic: str
    argument: str
    kind: Literal['evergreen', 'timely']
    format: Literal['observation', 'humour', 'question', 'reflection', 'argument']
    fit: int
    insight: int
    freshness: int
    source_ids: list[int]
    evidence: list[str]


class Plan(BaseModel):
    ideas: list[Idea] = Field(min_length=1, max_length=4)


class Drafts(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=3)


class Assessment(BaseModel):
    index: int
    voice: int
    insight: int
    originality: int
    verified: bool
    personal_supported: bool
    distinct: bool
    policy_ok: bool
    reason: str


class Review(BaseModel):
    reviews: list[Assessment] = Field(min_length=1, max_length=3)
