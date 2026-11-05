from sqlalchemy import func, select

from app.db import get_session
from app.models.home import Home
from app.models.room import Room
from tools.seed_demo_home import seed_demo_home


def test_demo_seed_is_idempotent_and_does_not_create_schema(owner, app):
    with app.app_context():
        session = get_session()
        home, rooms = seed_demo_home(
            session,
            email=" PYTEST-OWNER@example.test ",
        )
        second_home, second_rooms = seed_demo_home(
            session,
            email="pytest-owner@example.test",
        )
        assert second_home.id == home.id
        assert [room.id for room in second_rooms] == [room.id for room in rooms]
        assert session.scalar(
            select(func.count()).select_from(Home).where(Home.id == home.id)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(Room).where(Room.home_id == home.id)
        ) == 3
