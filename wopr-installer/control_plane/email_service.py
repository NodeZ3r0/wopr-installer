"""
WOPR Email Service
==================

Handles all email communications for WOPR including welcome emails,
trial reminders, payment notifications, and more.

Uses SMTP for delivery with Jinja2 for template rendering.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    print("WARNING: jinja2 not installed. Run: pip install jinja2")
    Environment = None

logger = logging.getLogger(__name__)

# Email configuration defaults
DEFAULT_SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.mailgun.org")
DEFAULT_SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
DEFAULT_SMTP_USER = os.environ.get("SMTP_USER", "")
DEFAULT_SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("FROM_EMAIL", "WOPR <noreply@wopr.systems>")
DEFAULT_REPLY_TO = os.environ.get("REPLY_TO_EMAIL", "support@wopr.systems")

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "emails"


@dataclass
class EmailConfig:
    """SMTP configuration for email service."""
    smtp_host: str = DEFAULT_SMTP_HOST
    smtp_port: int = DEFAULT_SMTP_PORT
    smtp_user: str = DEFAULT_SMTP_USER
    smtp_password: str = DEFAULT_SMTP_PASSWORD
    from_email: str = DEFAULT_FROM_EMAIL
    reply_to: str = DEFAULT_REPLY_TO
    use_tls: bool = True


class EmailService:
    """Service for sending templated emails."""

    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()
        self.smtp_configured = self._check_smtp_config()

        # Initialize Jinja2 environment
        if Environment:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(TEMPLATE_DIR)),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            self.jinja_env = None
            logger.warning("Jinja2 not available - email templates won't work")

    def _check_smtp_config(self) -> bool:
        """Check if SMTP is properly configured."""
        if not self.config.smtp_user or not self.config.smtp_password:
            logger.warning(
                "SMTP not configured! Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD "
                "environment variables to enable email delivery."
            )
            return False
        logger.info(f"SMTP configured: {self.config.smtp_host}:{self.config.smtp_port}")
        return True

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render an email template with the given context."""
        if not self.jinja_env:
            raise RuntimeError("Jinja2 not available")

        template = self.jinja_env.get_template(template_name)
        return template.render(**context)

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        attachments: Optional[List[tuple]] = None,
    ) -> bool:
        """Send an email via SMTP."""
        if not self.smtp_configured:
            logger.error(
                f"Cannot send email to {to_email} - SMTP not configured! "
                f"Subject: {subject}"
            )
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.from_email
            msg["To"] = to_email
            msg["Reply-To"] = self.config.reply_to

            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Attach any files
            if attachments:
                for filename, content, mime_type in attachments:
                    part = MIMEApplication(content, Name=filename)
                    part["Content-Disposition"] = f'attachment; filename="{filename}"'
                    msg.attach(part)

            # Send email
            context = ssl.create_default_context()

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls(context=context)

                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)

                server.sendmail(
                    self.config.from_email,
                    to_email,
                    msg.as_string()
                )

            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    # ==========================================
    # WELCOME EMAIL
    # ==========================================

    def send_welcome_email(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        bundle_name: str,
        tier_name: str,
        billing_cycle: str,
        temp_password: str,
        apps: List[Dict[str, str]],
        pdf_attachment: Optional[bytes] = None,
    ) -> bool:
        """Send welcome email after successful provisioning."""
        context = {
            "name": name,
            "email": to_email,
            "beacon_name": beacon_name,
            "bundle_name": bundle_name,
            "tier_name": tier_name,
            "billing_cycle": billing_cycle,
            "temp_password": temp_password,
            "apps": apps,
        }

        html_content = self._render_template("welcome.html", context)

        attachments = None
        if pdf_attachment:
            attachments = [
                (f"{beacon_name}_welcome.pdf", pdf_attachment, "application/pdf")
            ]

        return self._send_email(
            to_email=to_email,
            subject=f"Welcome to WOPR - Your Beacon {beacon_name} is Ready!",
            html_content=html_content,
            attachments=attachments,
        )

    # ==========================================
    # PROVISIONING EMAIL
    # ==========================================

    def send_provisioning_started(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        bundle_name: str,
        job_id: str,
        provisioning_url: str,
    ) -> bool:
        """
        Send email immediately after payment with link to watch provisioning.

        This email goes out BEFORE the beacon is ready, giving the user
        a link they can use to watch progress or return to later.
        """
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="background: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background: #111; border-radius: 12px; overflow: hidden; border: 1px solid #222;">
                <div style="padding: 40px 30px; text-align: center; border-bottom: 2px solid #00ff41; background: linear-gradient(180deg, #0a0a0a 0%, #111 100%);">
                    <div style="font-size: 36px; font-weight: 700; color: #00ff41; letter-spacing: 6px; text-shadow: 0 0 20px rgba(0,255,65,0.3);">WOPR</div>
                    <div style="color: #666; font-size: 12px; margin-top: 8px; letter-spacing: 2px;">SOVEREIGN SUITE</div>
                </div>

                <div style="padding: 40px 30px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <span style="display: inline-block; background: rgba(0, 255, 65, 0.1); border: 1px solid #00ff41; color: #00ff41; padding: 8px 20px; border-radius: 20px; font-size: 14px; font-weight: 500;">
                            🚀 Payment Confirmed
                        </span>
                    </div>

                    <h1 style="color: #fff; font-size: 28px; text-align: center; margin: 0 0 20px; font-weight: 600;">
                        Your Beacon is Being Built
                    </h1>

                    <p style="color: #aaa; text-align: center; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                        Hi {name}, thanks for joining WOPR! We're now provisioning your personal server.
                        This typically takes 3-5 minutes.
                    </p>

                    <div style="background: #0a0a0a; border: 1px solid #333; border-radius: 12px; padding: 25px; margin: 0 0 30px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="color: #666; padding: 8px 0; font-size: 14px;">Beacon Name</td>
                                <td style="color: #fff; padding: 8px 0; font-size: 14px; text-align: right; font-weight: 600;">{beacon_name}.wopr.systems</td>
                            </tr>
                            <tr>
                                <td style="color: #666; padding: 8px 0; font-size: 14px;">Bundle</td>
                                <td style="color: #00ff41; padding: 8px 0; font-size: 14px; text-align: right; font-weight: 600;">{bundle_name}</td>
                            </tr>
                            <tr>
                                <td style="color: #666; padding: 8px 0; font-size: 14px;">Job ID</td>
                                <td style="color: #888; padding: 8px 0; font-size: 12px; text-align: right; font-family: monospace;">{job_id[:16]}...</td>
                            </tr>
                        </table>
                    </div>

                    <div style="text-align: center; margin: 35px 0;">
                        <a href="{provisioning_url}" style="display: inline-block; background: linear-gradient(135deg, #00ff41 0%, #00cc33 100%); color: #000; text-decoration: none; padding: 18px 40px; border-radius: 8px; font-weight: 700; font-size: 16px; box-shadow: 0 4px 15px rgba(0,255,65,0.3);">
                            Watch Your Beacon Deploy →
                        </a>
                    </div>

                    <p style="color: #666; font-size: 13px; text-align: center; margin: 30px 0 0;">
                        Bookmark this link! You can return to it anytime to check your beacon's status.
                    </p>
                </div>

                <div style="padding: 20px 30px; background: #0a0a0a; border-top: 1px solid #222; text-align: center;">
                    <p style="color: #444; font-size: 12px; margin: 0;">
                        Questions? Reply to this email or visit <a href="https://wopr.systems/support" style="color: #00ff41;">support</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(
            to_email=to_email,
            subject=f"🚀 Your WOPR Beacon is Being Built - {beacon_name}",
            html_content=html_content,
        )

    # ==========================================
    # TRIAL REMINDER EMAILS
    # ==========================================

    def send_trial_reminder(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        bundle_name: str,
        tier_name: str,
        monthly_price: str,
        days_remaining: int,
        trial_days_used: int,
        storage_used: str = "0 GB",
        apps_used: int = 0,
    ) -> bool:
        """Send trial expiration reminder email."""
        context = {
            "name": name,
            "email": to_email,
            "beacon_name": beacon_name,
            "bundle_name": bundle_name,
            "tier_name": tier_name,
            "monthly_price": monthly_price,
            "days_remaining": days_remaining,
            "trial_days_used": trial_days_used,
            "storage_used": storage_used,
            "apps_used": apps_used,
        }

        html_content = self._render_template("trial_reminder.html", context)

        # Different subjects based on urgency
        if days_remaining <= 1:
            subject = f"FINAL NOTICE: Your WOPR trial ends tomorrow!"
        elif days_remaining <= 7:
            subject = f"Your WOPR trial ends in {days_remaining} days"
        else:
            subject = f"Trial reminder: {days_remaining} days remaining"

        return self._send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
        )

    # ==========================================
    # PAYMENT EMAILS
    # ==========================================

    def send_payment_failed(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        amount: str,
        billing_period: str,
        card_brand: str,
        card_last4: str,
        failure_reason: str,
        grace_days_remaining: int = 7,
    ) -> bool:
        """Send payment failure notification email."""
        context = {
            "name": name,
            "email": to_email,
            "beacon_name": beacon_name,
            "amount": amount,
            "billing_period": billing_period,
            "card_brand": card_brand,
            "card_last4": card_last4,
            "failure_reason": failure_reason,
            "grace_days_remaining": grace_days_remaining,
        }

        html_content = self._render_template("payment_failed.html", context)

        return self._send_email(
            to_email=to_email,
            subject="Action Required: Your WOPR payment failed",
            html_content=html_content,
        )

    def send_payment_success(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        amount: str,
        billing_period: str,
        next_billing_date: str,
    ) -> bool:
        """Send payment success confirmation email."""
        # Simple payment confirmation - no template needed
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="background: #0a0a0a; font-family: -apple-system, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #111; border-radius: 12px; overflow: hidden;">
                <div style="padding: 40px 30px; text-align: center; border-bottom: 2px solid #00ff41;">
                    <div style="font-size: 32px; font-weight: 700; color: #00ff41; letter-spacing: 4px;">WOPR</div>
                </div>
                <div style="padding: 40px 30px;">
                    <h1 style="color: #fff; font-size: 24px; text-align: center;">Payment Received</h1>
                    <p style="color: #ccc; text-align: center;">Hi {name}, we've received your payment of <strong style="color: #00ff41;">${amount}</strong> for {billing_period}.</p>
                    <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; margin: 25px 0;">
                        <p style="color: #888; margin: 0;">Beacon: <strong style="color: #fff;">{beacon_name}.wopr.systems</strong></p>
                        <p style="color: #888; margin: 10px 0 0;">Next billing: <strong style="color: #fff;">{next_billing_date}</strong></p>
                    </div>
                    <p style="color: #888; font-size: 13px; text-align: center;">Thank you for using WOPR!</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(
            to_email=to_email,
            subject=f"Payment received - ${amount}",
            html_content=html_content,
        )

    # ==========================================
    # SUBSCRIPTION EMAILS
    # ==========================================

    def send_subscription_upgraded(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        old_bundle: str,
        new_bundle: str,
        new_apps: List[str],
    ) -> bool:
        """Send notification when subscription is upgraded."""
        apps_list = ", ".join(new_apps) if new_apps else "None"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="background: #0a0a0a; font-family: -apple-system, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #111; border-radius: 12px; overflow: hidden;">
                <div style="padding: 40px 30px; text-align: center; border-bottom: 2px solid #00ff41;">
                    <div style="font-size: 32px; font-weight: 700; color: #00ff41; letter-spacing: 4px;">WOPR</div>
                </div>
                <div style="padding: 40px 30px;">
                    <span style="display: inline-block; background: rgba(0, 255, 65, 0.1); border: 1px solid #00ff41; color: #00ff41; padding: 8px 20px; border-radius: 20px; font-size: 14px;">Upgrade Complete</span>
                    <h1 style="color: #fff; font-size: 24px; margin: 20px 0;">Your plan has been upgraded!</h1>
                    <p style="color: #ccc;">Hi {name}, your WOPR subscription has been successfully upgraded from <strong>{old_bundle}</strong> to <strong style="color: #00ff41;">{new_bundle}</strong>.</p>

                    <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; margin: 25px 0;">
                        <h3 style="color: #00ff41; font-size: 14px; margin: 0 0 10px;">New Apps Now Available:</h3>
                        <p style="color: #fff; margin: 0;">{apps_list}</p>
                    </div>

                    <a href="https://{beacon_name}.wopr.systems/dashboard" style="display: inline-block; background: #00ff41; color: #000; text-decoration: none; padding: 16px 32px; border-radius: 8px; font-weight: 600; margin: 20px 0;">Explore Your New Apps</a>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(
            to_email=to_email,
            subject=f"Upgrade complete - Welcome to {new_bundle}!",
            html_content=html_content,
        )

    def send_subscription_cancelled(
        self,
        to_email: str,
        name: str,
        beacon_name: str,
        end_date: str,
    ) -> bool:
        """Send notification when subscription is cancelled."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="background: #0a0a0a; font-family: -apple-system, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #111; border-radius: 12px; overflow: hidden;">
                <div style="padding: 40px 30px; text-align: center; border-bottom: 2px solid #ffc107;">
                    <div style="font-size: 32px; font-weight: 700; color: #00ff41; letter-spacing: 4px;">WOPR</div>
                </div>
                <div style="padding: 40px 30px;">
                    <h1 style="color: #fff; font-size: 24px; text-align: center;">We're sorry to see you go</h1>
                    <p style="color: #ccc; text-align: center;">Hi {name}, your WOPR subscription has been cancelled.</p>

                    <div style="background: rgba(255, 193, 7, 0.1); border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin: 25px 0; text-align: center;">
                        <p style="color: #ffc107; margin: 0 0 10px; font-weight: 600;">Your service will remain active until:</p>
                        <p style="color: #fff; font-size: 24px; font-weight: 700; margin: 0;">{end_date}</p>
                    </div>

                    <p style="color: #888; font-size: 14px; text-align: center;">After this date, your apps will be inaccessible and your data will be deleted within 7 days.</p>

                    <div style="text-align: center; margin: 30px 0;">
                        <p style="color: #ccc; margin: 0 0 15px;">Changed your mind?</p>
                        <a href="https://{beacon_name}.wopr.systems/billing/resubscribe" style="display: inline-block; background: #00ff41; color: #000; text-decoration: none; padding: 16px 32px; border-radius: 8px; font-weight: 600;">Reactivate Subscription</a>
                    </div>

                    <p style="color: #666; font-size: 12px; text-align: center; margin-top: 30px;">We'd love to hear your feedback. Reply to this email to let us know how we can improve.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self._send_email(
            to_email=to_email,
            subject="Your WOPR subscription has been cancelled",
            html_content=html_content,
        )


# ==========================================
# SCHEDULED EMAIL TASKS
# ==========================================

def get_trial_users_for_reminders(days_list: List[int] = [15, 7, 3, 1]) -> List[Dict]:
    """
    Get users whose trials expire in the specified number of days.
    This should query the database for trial users.
    """
    # TODO: Implement database query
    # SELECT * FROM users
    # WHERE subscription_status = 'trial'
    # AND trial_end_date = NOW() + INTERVAL X DAY
    return []


def send_trial_reminder_batch():
    """Send trial reminder emails to all users whose trials are ending soon."""
    email_service = EmailService()

    # Send reminders at 15, 7, 3, and 1 day marks
    reminder_days = [15, 7, 3, 1]

    for days in reminder_days:
        users = get_trial_users_for_reminders([days])

        for user in users:
            email_service.send_trial_reminder(
                to_email=user["email"],
                name=user["name"],
                beacon_name=user["beacon_name"],
                bundle_name=user["bundle_name"],
                tier_name=user["tier_name"],
                monthly_price=user["monthly_price"],
                days_remaining=days,
                trial_days_used=user.get("trial_days_used", 0),
                storage_used=user.get("storage_used", "0 GB"),
                apps_used=user.get("apps_used", 0),
            )


# ==========================================
# CLI FOR TESTING
# ==========================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WOPR Email Service CLI")
    parser.add_argument("--test", action="store_true", help="Send test emails")
    parser.add_argument("--email", help="Recipient email for test")
    parser.add_argument("--type", choices=["welcome", "trial", "payment_failed"], default="welcome")

    args = parser.parse_args()

    if args.test:
        if not args.email:
            print("ERROR: --email required for test mode")
            exit(1)

        service = EmailService()

        if args.type == "welcome":
            service.send_welcome_email(
                to_email=args.email,
                name="Test User",
                beacon_name="testbeacon",
                bundle_name="Starter Suite",
                tier_name="Tier 1 (50GB)",
                billing_cycle="Monthly",
                temp_password="TempPass123!",
                apps=[
                    {"name": "Nextcloud", "icon": "📁", "subdomain": "files"},
                    {"name": "Vaultwarden", "icon": "🔐", "subdomain": "vault"},
                    {"name": "FreshRSS", "icon": "📰", "subdomain": "rss"},
                ],
            )
            print(f"Sent welcome email to {args.email}")

        elif args.type == "trial":
            service.send_trial_reminder(
                to_email=args.email,
                name="Test User",
                beacon_name="testbeacon",
                bundle_name="Starter Suite",
                tier_name="Tier 1",
                monthly_price="15.99",
                days_remaining=7,
                trial_days_used=7,
                storage_used="2.5 GB",
                apps_used=3,
            )
            print(f"Sent trial reminder to {args.email}")

        elif args.type == "payment_failed":
            service.send_payment_failed(
                to_email=args.email,
                name="Test User",
                beacon_name="testbeacon",
                amount="15.99",
                billing_period="January 2026",
                card_brand="Visa",
                card_last4="4242",
                failure_reason="Card declined",
                grace_days_remaining=7,
            )
            print(f"Sent payment failed email to {args.email}")
