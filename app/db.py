from pathlib import Path

from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.models import alert, home, metric, reading, room, threshold
from app.models.base import Base


def _engine() -> Engine:
    return current_app.extensions["airsense_engine"]


def get_session() -> Session:
    if "airsense_session" not in g:
        factory = sessionmaker(bind=_engine(), expire_on_commit=False)
        g.airsense_session = factory()
    return g.airsense_session


def close_db(_error: BaseException | None = None) -> None:
    session = g.pop("airsense_session", None)
    if session is not None:
        session.close()


def init_db(app) -> None:
    app.teardown_appcontext(close_db)
    url = make_url(app.config["DATABASE_URL"])
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={"check_same_thread": False}
        if url.get_backend_name() == "sqlite"
        else {},
    )
    app.extensions["airsense_engine"] = engine
    if app.config.get("AUTO_CREATE_SCHEMA"):
        with app.app_context():
            Base.metadata.create_all(engine)
