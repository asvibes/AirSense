import os
from pathlib import Path


class Config:
    DATABASE = os.environ.get(
        "AIRSENSE_DATABASE",
        str(Path(__file__).resolve().parent.parent / "instance" / "airsense.sqlite3"),
    )