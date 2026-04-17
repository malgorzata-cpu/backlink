from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LinkOpportunity(Base):
    __tablename__ = "link_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    referring_page_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    referring_page_url: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_traffic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referring_domains: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_traffic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intersect: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_rafa: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_winnicalidla: Mapped[str | None] = mapped_column(Text, nullable=True)

    import_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_lo_sort",
            "domain_traffic",
            "domain_rating",
            "page_traffic",
        ),
        Index("ix_lo_url", "referring_page_url"),
    )
