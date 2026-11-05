import logging
from datetime import datetime

from flask import current_app


_logger = logging.getLogger(__name__)


def send_invitation_email(
    *,
    recipient: str,
    invitation_url: str,
    expires_at: datetime,
) -> bool:
    """Log invitation details in development; never sends or logs them elsewhere."""
    if current_app.config.get("APP_ENV") != "development":
        return False
    _logger.info(
        "Development-only invitation email: recipient=%s invitation_url=%s expires_at=%s",
        recipient,
        invitation_url,
        expires_at.isoformat(),
    )
    return True