import io

import pytest


_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image"


def test_room_photo_upload_download_and_delete(owner, room, app):
    response = owner.client.post(
        f"/api/homes/{owner.home_id}/rooms/{room['id']}/photos",
        data={"photo": (io.BytesIO(_PNG_BYTES), "room.png", "image/png")},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert response.status_code == 201, response.get_json()
    photo = response.get_json()["photo"]
    stored_path = app.config["PRIVATE_UPLOAD_FOLDER"]
    assert photo["content_type"] == "image/png"
    assert photo["size"] == len(_PNG_BYTES)
    assert len(photo["filename"]) == 36
    assert not str(stored_path).startswith(app.static_folder)

    downloaded = owner.client.get(photo["url"])
    assert downloaded.status_code == 200
    assert downloaded.data == _PNG_BYTES
    assert downloaded.mimetype == "image/png"
    assert downloaded.headers["Cache-Control"] == "private, no-store"
    assert downloaded.headers["X-Content-Type-Options"] == "nosniff"
    downloaded.close()

    removed = owner.client.delete(
        photo["url"],
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert removed.status_code == 200
    assert owner.client.get(photo["url"]).status_code == 404


@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("room.gif", "image/gif", b"GIF89a"),
        ("room.jpg", "image/png", _PNG_BYTES),
        ("room.png", "image/png", b"not an image"),
        ("room.webp", "image/webp", b"RIFFbad!"),
    ],
)
def test_room_photo_rejects_unsupported_or_mismatched_images(
    owner, room, filename, content_type, content
):
    response = owner.client.post(
        f"/api/homes/{owner.home_id}/rooms/{room['id']}/photos",
        data={"photo": (io.BytesIO(content), filename, content_type)},
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert response.status_code == 400


def test_room_photo_rejects_files_over_five_megabytes(owner, room):
    response = owner.client.post(
        f"/api/homes/{owner.home_id}/rooms/{room['id']}/photos",
        data={
            "photo": (
                io.BytesIO(b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024)),
                "room.jpg",
                "image/jpeg",
            )
        },
        headers={"X-CSRF-Token": owner.csrf_token},
    )
    assert response.status_code == 400
    assert "5 MB" in response.get_json()["error"]


def test_room_photos_require_login_and_home_membership(app, owner, room):
    anonymous = app.test_client()
    url = f"/api/homes/{owner.home_id}/rooms/{room['id']}/photos"
    assert anonymous.post(url).status_code == 401
    photo_url = f"{url}/{'0' * 32}.png"

    other = app.test_client()
    register = other.get("/register")
    import re

    token = re.search(rb'name="csrf_token" value="([^"]+)"', register.data).group(1).decode()
    other.post(
        "/api/auth/register",
        json={
            "email": "other-owner@example.test",
            "display_name": "Other Owner",
            "password": "secure-password-123",
        },
        headers={"X-CSRF-Token": token},
    )
    assert other.get(photo_url).status_code == 404
