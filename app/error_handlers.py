"""Register friendly, animated Flask HTTP and server-error pages."""

from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException


_HTTP_TITLES = {
    400: "Bad request",
    401: "Sign in required",
    403: "Access denied",
    404: "Not found",
    405: "Method not allowed",
    408: "Request timed out",
    409: "Request conflict",
    413: "Request too large",
    429: "Too many requests",
}

_HTTP_MESSAGES = {
    400: "The request could not be understood. Check the address or try again.",
    401: "Please sign in to continue to this part of AirSense.",
    403: "You do not have permission to view this page.",
    404: "We could not find that page. It may have moved or the address may be incorrect.",
    405: "That action is not available at this address.",
    408: "The request took too long. Please try again.",
    409: "The request conflicts with the current state. Please refresh and try again.",
    413: "The submitted request is too large. Please try a smaller request.",
    429: "There have been too many requests. Wait a moment and try again.",
}


def register_error_handlers(app):
    """Attach safe, themed handlers to a Flask app or app factory instance."""

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        status_code = int(error.code or 500)
        error_name = getattr(error, "name", None)
        if status_code >= 500:
            title = _HTTP_TITLES.get(status_code, error_name or "Server error")
            message = "We could not complete that request. Please try again in a little while."
        else:
            title = _HTTP_TITLES.get(status_code, error_name or "Request error")
            message = _HTTP_MESSAGES.get(
                status_code,
                "We could not complete that request. Check the address or try again.",
            )
        return (
            render_template(
                "error.html",
                status_code=status_code,
                error_title=title,
                error_message=message,
            ),
            status_code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled exception while serving an AirSense request")
        return (
            render_template(
                "error.html",
                status_code=500,
                error_title="Server error",
                error_message="We could not complete that request. Please try again in a little while.",
            ),
            500,
        )
