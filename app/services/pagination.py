from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session


T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    items: Sequence[T]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        if self.total == 0:
            return 1
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_page(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_page(self) -> int:
        return min(self.pages, self.page + 1)

    @property
    def start_index(self) -> int:
        if self.total == 0:
            return 0
        return (self.page - 1) * self.per_page + 1

    @property
    def end_index(self) -> int:
        return min(self.page * self.per_page, self.total)

    def page_window(self, width: int = 5) -> list[int]:
        """Return a sliding window of page numbers around the current page."""
        if self.pages <= 1:
            return [1]
        half = width // 2
        start = max(1, self.page - half)
        end = min(self.pages, start + width - 1)
        start = max(1, end - width + 1)
        return list(range(start, end + 1))


def paginate(db: Session, stmt, page: int, per_page: int) -> Page:
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (
        db.execute(stmt.limit(per_page).offset((page - 1) * per_page))
        .scalars()
        .all()
    )
    return Page(items=items, page=page, per_page=per_page, total=total)
