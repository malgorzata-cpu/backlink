from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActiveBacklink(Base):
    __tablename__ = "active_backlinks"

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
    lost_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    drop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lost: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    links_in_group: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Monitoring fields — populated by app/services/link_checker.py.
    # These are NEVER overwritten when re-importing CSV (smart upsert).
    check_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link_found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    exact_target_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    found_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    found_anchor: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_hrefs: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    import_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_ab_sort", "domain_traffic"),
        Index("ix_ab_url", "referring_page_url"),
        Index("ix_ab_status", "check_status"),
        Index("ix_ab_dedup", "project_id", "referring_page_url", "target_url"),
    )
