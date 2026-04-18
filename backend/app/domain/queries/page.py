"""Page — generic paginated result container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class Page[T]:
    items: list[T]
    total: int
    page: int
    page_size: int
