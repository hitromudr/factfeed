"""Pydantic schemas for API responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceOut(BaseModel):
    """News source schema."""

    id: int
    name: str
    feed_url: str

    model_config = ConfigDict(from_attributes=True)


class SentenceOut(BaseModel):
    """Classified sentence schema."""

    text: str
    label: str = Field(
        ..., description="Classification label: fact, opinion, mixed, unclear"
    )
    confidence: float = Field(..., description="Confidence score of the classification")
    position: int

    model_config = ConfigDict(from_attributes=True)


class ArticleBase(BaseModel):
    """Base article fields with flattened statistics."""

    id: int
    title: str
    url: str
    published_at: Optional[datetime]
    source: SourceOut

    # Dynamic fields (calculated via _attach_fact_scores or property)
    fact_count: int = Field(0, description="Number of factual sentences")
    opinion_count: int = Field(0, description="Number of opinionated sentences")
    mixed_count: int = Field(0, description="Number of mixed sentences")
    total_count: int = Field(0, description="Total number of sentences")
    fact_pct: Optional[int] = Field(
        None, description="Percentage of factual sentences (0-100)"
    )

    model_config = ConfigDict(from_attributes=True)


class ArticleOut(ArticleBase):
    """Article summary for search results."""

    pass


class ArticleDetailOut(ArticleBase):
    """Full article with sentences."""

    sentences: List[SentenceOut]
