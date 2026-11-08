from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from sqlalchemy import case, func, or_, update
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


def is_persistent_rate_limited(
    db,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> bool:
    bucket = db.get(RateLimitBucket, key)
    if bucket is None:
        return False
    db.expire(bucket)
    started_at = bucket.window_started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if started_at + timedelta(seconds=window_seconds) <= datetime.now(timezone.utc):
        return False
    return bucket.count >= limit


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


def record_persistent_failure(
    db,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    dialect = db.get_bind().dialect.name
    expired = (
        func.datetime(RateLimitBucket.window_started_at)
        < func.datetime(cutoff.isoformat())
        if dialect == "sqlite"
        else RateLimitBucket.window_started_at < cutoff
    )
    statement = (
        update(RateLimitBucket)
        .where(
            RateLimitBucket.key == key,
            or_(expired, RateLimitBucket.count < limit),
        )
        .values(
            window_started_at=case(
                (expired, now),
                else_=RateLimitBucket.window_started_at,
            ),
            count=case(
                (expired, 1),
                else_=RateLimitBucket.count + 1,
            ),
        )
    )
    result = db.execute(statement)
    if result.rowcount == 0:
        insert = sqlite_insert if dialect == "sqlite" else postgresql_insert
        statement = insert(RateLimitBucket).values(
            key=key,
            window_started_at=now,
            count=1,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=[RateLimitBucket.key]
        )
        result = db.execute(statement)
        if result.rowcount == 1:
            db.commit()
            return True
        db.expire_all()
        result = db.execute(
            update(RateLimitBucket)
            .where(RateLimitBucket.key == key, RateLimitBucket.count < limit)
            .values(count=RateLimitBucket.count + 1)
        )
        if result.rowcount == 0:
            db.rollback()
            return False
    db.commit()
    return True