"""WOPR AI Engine Notification System.

Sends notifications for escalations and auto-fix failures to:
- Beacon owner
- WOPR support staff

Supports:
- Email via Mailgun HTTP API (preferred) or SMTP fallback
- Future: ntfy for SMS/push notifications
"""

import asyncio
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import httpx

from api.config import (
    MAILGUN_API_KEY, MAILGUN_DOMAIN, MAILGUN_FROM,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    BEACON_ID, BEACON_DOMAIN, BEACON_OWNER_EMAIL, WOPR_SUPPORT_EMAILS,
    NOTIFY_ON_TIER2, NOTIFY_ON_TIER3, NOTIFY_ON_AUTO_FIX_FAILURE,
    NTFY_URL, NTFY_TOPIC, SUPPORT_PLANE_URL,
)

logger = logging.getLogger("ai_engine.notifier")


def _get_recipients(include_owner: bool = True) -> list[str]:
    """Get list of notification recipients."""
    recipients = [e.strip() for e in WOPR_SUPPORT_EMAILS if e.strip()]
    if include_owner and BEACON_OWNER_EMAIL:
        recipients.append(BEACON_OWNER_EMAIL)
    return list(set(recipients))  # Dedupe


def _build_escalation_email(
    tier: str,
    service: str,
    error_summary: str,
    proposed_action: str,
    confidence: float,
    escalation_id: str,
) -> tuple[str, str, str]:
    """Build email subject, plain text, and HTML body for escalation."""

    tier_label = {
        "tier2_suggest": "Tier 2 - Suggested Action",
        "tier3_escalate": "Tier 3 - Human Required",
    }.get(tier, tier)

    subject = f"[WOPR] {tier_label}: {service} on {BEACON_ID}"

    beacon_url = f"https://{BEACON_DOMAIN}" if BEACON_DOMAIN else "N/A"

    plain = f"""WOPR AI Remediation Engine - Escalation Notice

Beacon: {BEACON_ID}
Domain: {beacon_url}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

---

Service: {service}
Tier: {tier_label}
Confidence: {confidence:.0%}

Error Summary:
{error_summary}

Proposed Action:
{proposed_action}

---

Escalation ID: {escalation_id}

TAKE ACTION:
  Approve: {SUPPORT_PLANE_URL}/api/v1/ai/escalations/{escalation_id}/approve
  Reject:  {SUPPORT_PLANE_URL}/api/v1/ai/escalations/{escalation_id}/reject
  Dashboard: {SUPPORT_PLANE_URL}/escalations

--
WOPR AI Remediation Engine
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 8px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #0f3460 0%, #533483 100%); padding: 20px; text-align: center; }}
        .header h1 {{ margin: 0; color: #00d9ff; font-size: 24px; }}
        .header .tier {{ color: #ff6b6b; font-size: 14px; margin-top: 8px; }}
        .content {{ padding: 20px; }}
        .meta {{ background: #0f3460; padding: 12px; border-radius: 4px; margin-bottom: 16px; }}
        .meta-row {{ display: flex; justify-content: space-between; margin: 4px 0; }}
        .meta-label {{ color: #888; }}
        .meta-value {{ color: #00d9ff; }}
        .section {{ margin: 16px 0; }}
        .section-title {{ color: #00d9ff; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }}
        .section-content {{ background: #0a0a1a; padding: 12px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; }}
        .confidence {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .confidence-high {{ background: #00d97e; color: #000; }}
        .confidence-medium {{ background: #f7b731; color: #000; }}
        .confidence-low {{ background: #ff6b6b; color: #000; }}
        .footer {{ background: #0f3460; padding: 16px; text-align: center; font-size: 12px; color: #666; }}
        .escalation-id {{ font-family: monospace; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WOPR AI Remediation</h1>
            <div class="tier">{tier_label}</div>
        </div>
        <div class="content">
            <div class="meta">
                <div class="meta-row">
                    <span class="meta-label">Beacon</span>
                    <span class="meta-value">{BEACON_ID}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">Service</span>
                    <span class="meta-value">{service}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">Confidence</span>
                    <span class="confidence {'confidence-high' if confidence >= 0.8 else 'confidence-medium' if confidence >= 0.6 else 'confidence-low'}">{confidence:.0%}</span>
                </div>
            </div>

            <div class="section">
                <div class="section-title">Error Summary</div>
                <div class="section-content">{error_summary}</div>
            </div>

            <div class="section">
                <div class="section-title">Proposed Action</div>
                <div class="section-content">{proposed_action}</div>
            </div>
            <div class="actions" style="margin-top: 20px; text-align: center;">
                <a href="{SUPPORT_PLANE_URL}/api/v1/ai/escalations/{escalation_id}/approve"
                   style="display: inline-block; padding: 12px 24px; margin: 8px; background: #00d97e; color: #000; text-decoration: none; border-radius: 4px; font-weight: bold;">
                   APPROVE ACTION
                </a>
                <a href="{SUPPORT_PLANE_URL}/api/v1/ai/escalations/{escalation_id}/reject"
                   style="display: inline-block; padding: 12px 24px; margin: 8px; background: #ff6b6b; color: #fff; text-decoration: none; border-radius: 4px; font-weight: bold;">
                   REJECT
                </a>
            </div>
        </div>
        <div class="footer">
            <div class="escalation-id">Escalation ID: {escalation_id}</div>
            <div style="margin-top: 8px;"><a href="{SUPPORT_PLANE_URL}/escalations" style="color: #00d9ff;">View All Escalations</a></div>
        </div>
    </div>
</body>
</html>"""

    return subject, plain, html


def _build_auto_fix_failure_email(
    service: str,
    action: str,
    output: str,
) -> tuple[str, str, str]:
    """Build email for auto-fix failure notification."""

    subject = f"[WOPR] Auto-Fix Failed: {service} on {BEACON_ID}"

    beacon_url = f"https://{BEACON_DOMAIN}" if BEACON_DOMAIN else "N/A"

    plain = f"""WOPR AI Remediation Engine - Auto-Fix Failure

Beacon: {BEACON_ID}
Domain: {beacon_url}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

---

Service: {service}
Attempted Action: {action}

Output:
{output}

---

The AI engine attempted to automatically fix this issue but failed.
Manual intervention may be required.

--
WOPR AI Remediation Engine
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 8px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%); padding: 20px; text-align: center; }}
        .header h1 {{ margin: 0; color: #fff; font-size: 24px; }}
        .header .subtitle {{ color: #ffcccc; font-size: 14px; margin-top: 8px; }}
        .content {{ padding: 20px; }}
        .meta {{ background: #0f3460; padding: 12px; border-radius: 4px; margin-bottom: 16px; }}
        .meta-row {{ display: flex; justify-content: space-between; margin: 4px 0; }}
        .meta-label {{ color: #888; }}
        .meta-value {{ color: #00d9ff; }}
        .section {{ margin: 16px 0; }}
        .section-title {{ color: #ff6b6b; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }}
        .section-content {{ background: #0a0a1a; padding: 12px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; color: #ff6b6b; }}
        .footer {{ background: #0f3460; padding: 16px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Auto-Fix Failed</h1>
            <div class="subtitle">Manual intervention required</div>
        </div>
        <div class="content">
            <div class="meta">
                <div class="meta-row">
                    <span class="meta-label">Beacon</span>
                    <span class="meta-value">{BEACON_ID}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">Service</span>
                    <span class="meta-value">{service}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">Action</span>
                    <span class="meta-value">{action}</span>
                </div>
            </div>

            <div class="section">
                <div class="section-title">Error Output</div>
                <div class="section-content">{output}</div>
            </div>
        </div>
        <div class="footer">
            WOPR AI Remediation Engine
        </div>
    </div>
</body>
</html>"""

    return subject, plain, html


def _send_email_smtp_sync(
    subject: str,
    plain_body: str,
    html_body: str,
    recipients: list[str],
) -> bool:
    """Send email via SMTP (synchronous, runs in thread)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = MAILGUN_FROM
        msg["To"] = ", ".join(recipients)

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            # Only use STARTTLS and auth if credentials provided
            if SMTP_USER and SMTP_PASSWORD:
                smtp.starttls()
                smtp.ehlo()
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.sendmail(MAILGUN_FROM, recipients, msg.as_string())

        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


async def send_email(
    subject: str,
    plain_body: str,
    html_body: str,
    recipients: list[str],
) -> bool:
    """Send email via Mailgun HTTP API or SMTP fallback."""
    if not recipients:
        logger.warning("No recipients configured, skipping email notification")
        return False

    # Try HTTP API first if configured
    if MAILGUN_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
                    auth=("api", MAILGUN_API_KEY),
                    data={
                        "from": MAILGUN_FROM,
                        "to": recipients,
                        "subject": subject,
                        "text": plain_body,
                        "html": html_body,
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
            logger.info(f"Email sent via Mailgun API to {recipients}: {subject}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Mailgun API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Mailgun API failed: {e}")

    # Fall back to SMTP (works with or without auth for local relay)
    if SMTP_HOST:
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    _send_email_smtp_sync,
                    subject, plain_body, html_body, recipients
                )
            if result:
                logger.info(f"Email sent via SMTP to {recipients}: {subject}")
                return True
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")

    logger.warning("No email method available (no API key or SMTP host)")
    return False


async def send_ntfy(
    title: str,
    message: str,
    priority: int = 3,
    tags: Optional[list[str]] = None,
) -> bool:
    """Send push notification via ntfy (for future SMS/push support)."""
    if not NTFY_URL or not NTFY_TOPIC:
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{NTFY_URL}/{NTFY_TOPIC}",
                headers={
                    "Title": title,
                    "Priority": str(priority),
                    "Tags": ",".join(tags or []),
                },
                content=message,
                timeout=10.0,
            )
            resp.raise_for_status()
            logger.info(f"ntfy notification sent: {title}")
            return True
    except Exception as e:
        logger.error(f"Failed to send ntfy notification: {e}")
        return False


async def notify_escalation(
    tier: str,
    service: str,
    error_summary: str,
    proposed_action: str,
    confidence: float,
    escalation_id: str,
) -> None:
    """Send notifications for an escalation."""

    # Check if we should notify for this tier
    if tier == "tier2_suggest" and not NOTIFY_ON_TIER2:
        return
    if tier == "tier3_escalate" and not NOTIFY_ON_TIER3:
        return

    recipients = _get_recipients(include_owner=True)

    subject, plain, html = _build_escalation_email(
        tier, service, error_summary, proposed_action, confidence, escalation_id
    )

    # Send email
    await send_email(subject, plain, html, recipients)

    # Send ntfy (if configured)
    priority = 4 if tier == "tier3_escalate" else 3
    tags = ["warning", "robot"]
    await send_ntfy(
        title=f"WOPR: {service} needs attention",
        message=f"{error_summary}\nProposed: {proposed_action}",
        priority=priority,
        tags=tags,
    )


async def notify_auto_fix_failure(
    service: str,
    action: str,
    output: str,
) -> None:
    """Send notifications for auto-fix failure."""

    if not NOTIFY_ON_AUTO_FIX_FAILURE:
        return

    recipients = _get_recipients(include_owner=True)

    subject, plain, html = _build_auto_fix_failure_email(service, action, output)

    # Send email
    await send_email(subject, plain, html, recipients)

    # Send ntfy (if configured)
    await send_ntfy(
        title=f"WOPR: Auto-fix failed for {service}",
        message=f"Action: {action}\nOutput: {output}",
        priority=4,
        tags=["x", "robot"],
    )
