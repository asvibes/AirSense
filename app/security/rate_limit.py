from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.user import RateLimitBucket


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            if len(self._events) > 10_000:
                expired = [
                    item
                    for item, timestamps in self._events.items()
                    if not timestamps or timestamps[-1] <= now - window_seconds
                ]
                for item in expired:
                    self._events.pop(item, None)
            return True


def allow_persistent(
    db,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    values = {
        "key": key,
        "window_started_at": now,
        "count": 1,
    }
    dialect = db.get_bind().dialect.name
    insert = sqlite_insert if dialect == "sqlite" else postgresql_insert
    statement = insert(RateLimitBucket).values(**values)
    excluded = statement.excluded
    expired = (
        func.datetime(RateLimitBucket.window_started_at)
        < func.datetime(cutoff.isoformat())
        if dialect == "sqlite"
        else RateLimitBucket.window_started_at < cutoff
    )
    statement = statement.on_conflict_do_update(
        index_elements=[RateLimitBucket.key],
        set_={
            "window_started_at": case(
                (expired, excluded.window_started_at),
                else_=RateLimitBucket.window_started_at,
            ),
            "count": case(
                (expired, 1),
                else_=RateLimitBucket.count + 1,
            ),
        },
    )
    db.execute(statement)
    db.expire_all()
    count = db.get(RateLimitBucket, key).count
    db.commit()
    return count <= limit