import hashlib
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from flask import current_app


MAX_ROOM_PHOTO_BYTES = 5 * 1024 * 1024
_PHOTO_TYPES = {
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".webp": (
        "image/webp",
        lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    ),
}
_PHOTO_NAME = re.compile(r"[0-9a-f]{32}\.(?:jpg|jpeg|png|webp)\Z")


class RoomPhotoError(ValueError):
    pass


def _storage_root() -> Path:
    root = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]).resolve()
    static_root = Path(current_app.static_folder).resolve()
    if root == static_root or static_root in root.parents:
        raise RuntimeError("Private uploads must be stored outside the static directory.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _scope_directory(home_id: str, room_id: str) -> Path:
    home_key = hashlib.sha256(home_id.encode("utf-8")).hexdigest()
    room_key = hashlib.sha256(room_id.encode("utf-8")).hexdigest()
    return _storage_root() / home_key / room_key


def save_room_photo(
    *,
    home_id: str,
    room_id: str,
    filename: str | None,
    content_type: str | None,
    stream: BinaryIO,
) -> dict[str, str | int]:
    extension = Path(filename or "").suffix.lower()
    photo_type = _PHOTO_TYPES.get(extension)
    if photo_type is None:
        raise RoomPhotoError("Room photos must be JPEG, PNG, or WebP files.")
    expected_type, signature_check = photo_type
    supplied_type = (content_type or "").split(";", 1)[0].strip().lower()
    if supplied_type != expected_type:
        raise RoomPhotoError("The uploaded MIME type does not match the file extension.")

    content = stream.read(MAX_ROOM_PHOTO_BYTES + 1)
    if len(content) > MAX_ROOM_PHOTO_BYTES:
        raise RoomPhotoError("Room photos must be 5 MB or smaller.")
    if not content or not signature_check(content):
        raise RoomPhotoError("The uploaded file is not an image of the declared type.")

    directory = _scope_directory(home_id, room_id)
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = directory / stored_name
    with destination.open("xb") as output:
        output.write(content)
    return {
        "filename": stored_name,
        "content_type": expected_type,
        "size": len(content),
    }


def room_photo_path(*, home_id: str, room_id: str, filename: str) -> tuple[Path, str]:
    if not _PHOTO_NAME.fullmatch(filename):
        raise RoomPhotoError("Invalid room photo name.")
    path = _scope_directory(home_id, room_id) / filename
    if not path.is_file():
        raise FileNotFoundError("Room photo not found.")
    return path, _PHOTO_TYPES[path.suffix][0]


def delete_room_photo(*, home_id: str, room_id: str, filename: str) -> None:
    path, _content_type = room_photo_path(
        home_id=home_id,
        room_id=room_id,
        filename=filename,
    )
    path.unlink()