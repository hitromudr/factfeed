from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, Computed, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    feed_url = Column(Text, nullable=False, unique=True)

    articles = relationship("Article", back_populates="source")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, unique=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    author = Column(Text, nullable=True)
    lead_image_url = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    is_partial = Column(Boolean, nullable=False, server_default="false")
    published_at = Column(DateTime(timezone=True), nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))",
            persisted=True,
        ),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_articles_search_vector", "search_vector", postgresql_using="gin"),
    )

    source = relationship("Source", back_populates="articles")
    sentences = relationship(
        "Sentence",
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="Sentence.position",
    )


class Sentence(Base):
    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    position = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    label = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)

    article = relationship("Article", back_populates="sentences")
