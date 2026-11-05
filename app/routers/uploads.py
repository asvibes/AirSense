from flask import Blueprint, abort, jsonify, request, send_file, url_for
from sqlalchemy import select

from app.db import get_session
from app.models.room import Room
from app.security.sessions import require_home_role, require_user
from app.services.blob_storage import (
    RoomPhotoError,
    delete_room_photo,
    room_photo_path,
    save_room_photo,
)


uploads = Blueprint("uploads", __name__)


def _authorized_room(home_id: str, room_id: str) -> Room:
    require_home_role(home_id, "owner", "member")
    room = get_session().scalar(
        select(Room).where(Room.id == room_id, Room.home_id == home_id)
    )
    if room is None:
        abort(404)
    return room


@uploads.post("/api/homes/<home_id>/rooms/<room_id>/photos")
@require_user()
def upload_room_photo(home_id: str, room_id: str):
    _authorized_room(home_id, room_id)
    uploaded = request.files.get("photo")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="Choose a room photo to upload."), 400
    try:
        photo = save_room_photo(
            home_id=home_id,
            room_id=room_id,
            filename=uploaded.filename,
            content_type=uploaded.mimetype,
            stream=uploaded.stream,
        )
    except RoomPhotoError as error:
        return jsonify(error=str(error)), 400
    photo["url"] = url_for(
        "uploads.get_room_photo",
        home_id=home_id,
        room_id=room_id,
        filename=photo["filename"],
    )
    return jsonify(photo=photo), 201


@uploads.get("/api/homes/<home_id>/rooms/<room_id>/photos/<filename>")
@require_user()
def get_room_photo(home_id: str, room_id: str, filename: str):
    _authorized_room(home_id, room_id)
    try:
        path, content_type = room_photo_path(
            home_id=home_id,
            room_id=room_id,
            filename=filename,
        )
    except (RoomPhotoError, FileNotFoundError):
        abort(404)
    response = send_file(path, mimetype=content_type, conditional=False, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@uploads.delete("/api/homes/<home_id>/rooms/<room_id>/photos/<filename>")
@require_user()
def remove_room_photo(home_id: str, room_id: str, filename: str):
    _authorized_room(home_id, room_id)
    try:
        delete_room_photo(
            home_id=home_id,
            room_id=room_id,
            filename=filename,
        )
    except (RoomPhotoError, FileNotFoundError):
        abort(404)
    return jsonify(status="removed")