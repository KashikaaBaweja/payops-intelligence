from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from payops_core.agents.planner import DEFAULT_WINDOW
from payops_core.models.schemas import TimeWindow

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_window(start: datetime | None, end: datetime | None) -> TimeWindow:
    if start is None and end is None:
        return DEFAULT_WINDOW
    if start is None or end is None:
        raise HTTPException(status_code=400, detail="start and end are required together")
    start = start.replace(tzinfo=None)
    end = end.replace(tzinfo=None)
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")
    return TimeWindow(start=start, end=end)


def require_id(value: str, field: str = "id") -> str:
    if not _ID.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {field}")
    return value
