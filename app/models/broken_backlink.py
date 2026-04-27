from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BrokenBacklink(Base):
    __tablename__ = "broken_backlinks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )

    referring_page_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    referring_page_url: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(128), nullable=True)
    referring_page_http_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_traffic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referring_domains: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linked_domains: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_links: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_traffic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keywords: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_page_http_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    left_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor: Mapped[str | None] = mapped_column(Text, nullable=True)
    right_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_chain_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_chain_status_codes: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_spam: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    content: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    nofollow: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ugc: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sponsored: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rendered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    target_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ref_page_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_category: Mapped[str | None] = mapped_column(String(128), nullable=True)

    import_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_bb_sort", "domain_traffic"),
        Index("ix_bb_url", "referring_page_url"),
        Index("ix_bb_dedup", "project_id", "referring_page_url", "target_url"),
    )
