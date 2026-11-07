import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from html import escape

from flask import current_app


_logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the configured transactional provider rejects a message."""


def send_transactional_email(
    *,
    recipient: str,
    subject: str,
    html_content: str,
) -> None:
    api_key = current_app.config.get("BREVO_API_KEY", "")
    if not api_key:
        if current_app.testing:
            return
        raise EmailDeliveryError("Email delivery is not configured.")
    payload = json.dumps(
        {
            "sender": {
                "name": current_app.config["MAIL_DEFAULT_SENDER_NAME"],
                "email": current_app.config["MAIL_DEFAULT_SENDER"],
            },
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_content,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={"accept": "application/json", "api-key": api_key, "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise EmailDeliveryError("Email provider rejected the message.")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        _logger.warning("Transactional email delivery failed: %s", type(error).__name__)
        raise EmailDeliveryError("Email delivery failed. Please try again later.") from error


def send_otp_email(
    *,
    recipient: str,
    otp: str,
    purpose: str,
    user_name: str = "there",
) -> None:
    verification = purpose == "email_verification"
    subject = "Verify your AirSense email" if verification else "Reset your AirSense password"
    heading = "Verify your email address" if verification else "Reset your AirSense password"
    body = (
        "Welcome to AirSense! Please use the verification code below to confirm your email address."
        if verification
        else "We received a request to reset your AirSense account password. Use the verification code below to continue."
    )
    notice = (
        "If you didn't create an AirSense account, you can safely ignore this email."
        if verification
        else "If you didn't request this, you can safely ignore this email. Your password will remain unchanged."
    )
    send_transactional_email(
        recipient=recipient,
        subject=subject,
        html_content=_render_email(
            heading=heading,
            greeting=f"Hi {user_name},",
            body=body,
            code=otp,
            expiry="This code expires in 10 minutes and can only be used once.",
            notice=notice,
            signoff="Team AirSense",
        ),
    )


def send_invitation_email(
    *,
    recipient: str,
    invitation_url: str,
    expires_at: datetime,
    owner_name: str = "A household owner",
) -> None:
    send_transactional_email(
        recipient=recipient,
        subject="You've been invited to join a home on AirSense!",
        html_content=_render_email(
            heading="You've been invited to join a home on AirSense!",
            greeting="Hi,",
            body=f"{owner_name} has invited you to join their home on AirSense. Accept the invitation to access shared room readings, ventilation trends, and advisory alerts.",
            link=invitation_url,
            link_label="Accept invitation",
            expiry="This invitation expires in 24 hours.",
            notice="If you weren't expecting this invitation, you can safely ignore this email.",
            signoff="Team AirSense",
        ),
    )


def _render_email(
    *,
    heading: str,
    body: str,
    greeting: str | None = None,
    code: str | None = None,
    link: str | None = None,
    link_label: str | None = None,
    expiry: str | None = None,
    notice: str | None = None,
    signoff: str | None = None,
) -> str:
    action = (
        f'<p style="margin:24px 0"><a href="{escape(link, quote=True)}" '
        f'style="display:inline-block;padding:12px 18px;background:#183b3a;color:#fff;text-decoration:none;border-radius:8px">'
        f"{escape(link_label or '')}</a></p>"
        if link
        else ""
    )
    code_block = (
        f'<p style="font-size:32px;letter-spacing:8px;font-weight:700;color:#183b3a">{escape(code)}</p>'
        if code
        else ""
    )
    expiry_block = f"<p>{escape(expiry)}</p>" if expiry else ""
    greeting_block = f"<p>{escape(greeting)}</p>" if greeting else ""
    notice_block = f"<p>{escape(notice)}</p>" if notice else ""
    signoff_block = f"<p>&#8212; {escape(signoff)}</p>" if signoff else ""
    return f"""<!doctype html><html><body style="margin:0;background:#f4faf7;color:#183b3a;font:16px/1.5 Arial,sans-serif"><main style="max-width:560px;margin:32px auto;padding:32px;background:#fff;border:1px solid #d8ebe3;border-radius:12px"><p style="color:#438f79;font-weight:700;letter-spacing:.08em">AIRSENSE</p><h1>{escape(heading)}</h1>{greeting_block}<p>{escape(body)}</p>{code_block}{action}{expiry_block}{notice_block}{signoff_block}</main></body></html>"""