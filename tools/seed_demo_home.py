import argparse
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_session
from app.main import create_app
from app.models.home import Home
from app.models.room import Room
from app.models.user import HomeMembership, User


_DEMO_ROOMS = (
    ("Living room", ["Window"]),
    ("Bedroom", ["Window"]),
    ("Kitchen", ["Exhaust fan"]),
)


def seed_demo_home(
    session: Session,
    *,
    email: str,
    home_name: str = "AirSense Demo Home",
) -> tuple[Home, list[Room]]:
    normalized_email = email.strip().lower()
    if not normalized_email or len(normalized_email) > 254:
        raise ValueError("Provide a valid email address for an existing AirSense user.")
    if not home_name.strip() or len(home_name.strip()) > 120:
        raise ValueError("Home name must contain 1 to 120 characters.")

    user = session.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise ValueError(f"No AirSense account exists for {normalized_email}.")

    home_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"airsense-demo-home:{normalized_email}:{home_name.strip().casefold()}",
        )
    )
    home = session.get(Home, home_id)
    if home is None:
        home = Home(id=home_id, name=home_name.strip())
        session.add(home)
        session.flush()

    membership = session.get(HomeMembership, (home.id, user.id))
    if membership is None:
        session.add(HomeMembership(home_id=home.id, user_id=user.id, role="owner"))
    elif membership.role != "owner":
        raise ValueError("The demo home account must have the owner role.")

    rooms = []
    for room_name, ventilation_sources in _DEMO_ROOMS:
        room = session.scalar(
            select(Room).where(
                Room.home_id == home.id,
                Room.name == room_name,
            )
        )
        if room is None:
            room_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"airsense-demo-room:{home.id}:{room_name.casefold()}",
                )
            )
            room = Room(
                id=room_id,
                home_id=home.id,
                name=room_name,
                ventilation=ventilation_sources[0],
                ventilation_sources=ventilation_sources,
            )
            session.add(room)
        rooms.append(room)

    session.commit()
    return home, rooms


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create an idempotent demo home for an existing AirSense account."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address of an existing AirSense account that will own the demo home.",
    )
    parser.add_argument(
        "--home-name",
        default="AirSense Demo Home",
        help="Name of the demo home.",
    )
    args = parser.parse_args()

    if os.environ.get("APP_ENV", "development").strip().lower() == "production":
        parser.error("The demo seed tool cannot run when APP_ENV is production.")

    app = create_app({"AUTO_CREATE_SCHEMA": False})
    try:
        with app.app_context():
            home, rooms = seed_demo_home(
                get_session(),
                email=args.email,
                home_name=args.home_name,
            )
    except ValueError as error:
        parser.error(str(error))
    finally:
        app.extensions["airsense_engine"].dispose()

    print(f"Seeded demo home {home.name!r} ({home.id}) with {len(rooms)} rooms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())