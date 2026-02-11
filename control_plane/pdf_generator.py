"""
WOPR PDF Document Generator
===========================

Generates user-friendly PDF documents for WOPR customers:
- Custom domain setup guide
- Welcome card (quick reference)
- Getting started guide

These are designed for less tech-savvy users with clear,
step-by-step instructions and visual aids.

Requires: pip install reportlab
Alternative: pip install weasyprint (for HTML to PDF)

Updated: January 2026
"""

import os
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, ListFlowable, ListItem
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


@dataclass
class CustomerInfo:
    """Customer information for document generation."""
    customer_id: str
    email: str
    bundle: str
    instance_ip: str
    wopr_subdomain: str
    wopr_domain: str = "wopr.systems"
    custom_domain: Optional[str] = None
    created_at: datetime = None

    @property
    def full_wopr_url(self) -> str:
        return f"https://{self.wopr_subdomain}.{self.wopr_domain}"

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class WOPRDocumentGenerator:
    """
    Generates user-friendly PDF documents for WOPR customers.

    Documents are designed with non-technical users in mind:
    - Clear, numbered steps
    - Visual examples
    - Plain language
    - QR codes for mobile access
    """

    # WOPR brand colors
    BRAND_GREEN = colors.HexColor("#00FF00")
    BRAND_DARK = colors.HexColor("#0a0a0a")
    BRAND_GRAY = colors.HexColor("#333333")

    def __init__(self, output_dir: str = "/var/lib/wopr/documents"):
        """
        Initialize document generator.

        Args:
            output_dir: Directory to save generated PDFs
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab not installed. Run: pip install reportlab"
            )

        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Setup styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='WOPRTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.BRAND_GREEN,
            spaceAfter=20,
            alignment=TA_CENTER,
        ))

        self.styles.add(ParagraphStyle(
            name='WOPRSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.BRAND_GRAY,
            spaceAfter=30,
            alignment=TA_CENTER,
        ))

        self.styles.add(ParagraphStyle(
            name='WOPRHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=self.BRAND_DARK,
            spaceBefore=20,
            spaceAfter=10,
        ))

        self.styles.add(ParagraphStyle(
            name='WOPRStep',
            parent=self.styles['Normal'],
            fontSize=12,
            leftIndent=20,
            spaceBefore=10,
            spaceAfter=10,
        ))

        self.styles.add(ParagraphStyle(
            name='WOPRCode',
            parent=self.styles['Normal'],
            fontName='Courier',
            fontSize=11,
            backColor=colors.HexColor("#f5f5f5"),
            leftIndent=30,
            rightIndent=30,
            spaceBefore=10,
            spaceAfter=10,
        ))

        self.styles.add(ParagraphStyle(
            name='WOPRNote',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            leftIndent=20,
            borderColor=colors.lightgrey,
            borderWidth=1,
            borderPadding=10,
        ))

    def generate_custom_domain_guide(self, info: CustomerInfo) -> str:
        """
        Generate custom domain setup PDF.

        This guide walks users through pointing their domain
        to their WOPR instance with clear, visual steps.

        Args:
            info: Customer information

        Returns:
            Path to generated PDF
        """
        filename = f"{info.customer_id}_custom_domain_guide.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        story = []

        # Header
        story.append(Paragraph("WOPR SOVEREIGN SUITE", self.styles['WOPRTitle']))
        story.append(Paragraph("Custom Domain Setup Guide", self.styles['WOPRSubtitle']))
        story.append(Spacer(1, 20))

        # Welcome
        story.append(Paragraph(
            f"Hello! This guide will help you connect your domain "
            f"<b>{info.custom_domain}</b> to your WOPR instance.",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 20))

        # Instance info box
        instance_data = [
            ['Your Instance Details', ''],
            ['IP Address:', info.instance_ip],
            ['WOPR URL:', info.full_wopr_url],
            ['Your Domain:', info.custom_domain or 'Not specified'],
            ['Bundle:', info.bundle.title()],
        ]
        instance_table = Table(instance_data, colWidths=[2*inch, 4*inch])
        instance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.BRAND_GREEN),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('SPAN', (0, 0), (-1, 0)),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor("#f0f0f0")),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(instance_table)
        story.append(Spacer(1, 30))

        # Step 1
        story.append(Paragraph("Step 1: Log Into Your Domain Registrar", self.styles['WOPRHeading']))
        story.append(Paragraph(
            "Go to the website where you purchased your domain. This is usually one of:",
            self.styles['WOPRStep']
        ))

        registrars = ListFlowable([
            ListItem(Paragraph("GoDaddy (godaddy.com)", self.styles['Normal'])),
            ListItem(Paragraph("Namecheap (namecheap.com)", self.styles['Normal'])),
            ListItem(Paragraph("Google Domains (domains.google)", self.styles['Normal'])),
            ListItem(Paragraph("Cloudflare (cloudflare.com)", self.styles['Normal'])),
            ListItem(Paragraph("Your web hosting provider", self.styles['Normal'])),
        ], bulletType='bullet')
        story.append(registrars)

        story.append(Paragraph(
            "Look for 'DNS Settings', 'DNS Management', or 'Name Servers' in your account.",
            self.styles['WOPRStep']
        ))
        story.append(Spacer(1, 20))

        # Step 2
        story.append(Paragraph("Step 2: Create a DNS Record", self.styles['WOPRHeading']))
        story.append(Paragraph(
            "Add a new DNS record with these exact settings:",
            self.styles['WOPRStep']
        ))

        dns_data = [
            ['Setting', 'What to Enter'],
            ['Type', 'A'],
            ['Name/Host', f'@ (or leave blank)'],
            ['Value/Points to', info.instance_ip],
            ['TTL', '3600 (or "1 hour")'],
        ]
        dns_table = Table(dns_data, colWidths=[2*inch, 4*inch])
        dns_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#333333")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor("#f0f0f0")),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Courier'),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(dns_table)
        story.append(Spacer(1, 10))

        # Subdomain option
        story.append(Paragraph(
            f"<b>Want to use a subdomain instead?</b> (like cloud.{info.custom_domain})",
            self.styles['WOPRStep']
        ))
        story.append(Paragraph(
            f"Enter 'cloud' (or your preferred subdomain) in the Name/Host field instead of '@'.",
            self.styles['WOPRStep']
        ))
        story.append(Spacer(1, 20))

        # Step 3
        story.append(Paragraph("Step 3: Wait for DNS to Update", self.styles['WOPRHeading']))
        story.append(Paragraph(
            "DNS changes can take anywhere from 5 minutes to 48 hours to take effect worldwide. "
            "This is normal and depends on your registrar.",
            self.styles['WOPRStep']
        ))
        story.append(Paragraph(
            "You can check if your DNS has updated at: <b>dnschecker.org</b>",
            self.styles['WOPRStep']
        ))
        story.append(Spacer(1, 20))

        # Step 4
        story.append(Paragraph("Step 4: Activate in WOPR", self.styles['WOPRHeading']))
        story.append(Paragraph(
            f"Once DNS has propagated:",
            self.styles['WOPRStep']
        ))

        steps = ListFlowable([
            ListItem(Paragraph(f"Go to <b>{info.full_wopr_url}</b>", self.styles['Normal'])),
            ListItem(Paragraph("Log in with your admin account", self.styles['Normal'])),
            ListItem(Paragraph("Click <b>Settings</b> in the menu", self.styles['Normal'])),
            ListItem(Paragraph("Click <b>Custom Domain</b>", self.styles['Normal'])),
            ListItem(Paragraph(f"Enter: <b>{info.custom_domain}</b>", self.styles['Normal'])),
            ListItem(Paragraph("Click <b>Activate</b>", self.styles['Normal'])),
        ], bulletType='1')
        story.append(steps)

        story.append(Paragraph(
            "WOPR will automatically get an SSL certificate for your domain!",
            self.styles['WOPRStep']
        ))
        story.append(Spacer(1, 30))

        # Troubleshooting
        story.append(Paragraph("Troubleshooting", self.styles['WOPRHeading']))

        trouble_data = [
            ['Problem', 'Solution'],
            ['"Site not found"', 'DNS hasn\'t propagated yet. Wait a few hours and try again.'],
            ['"SSL Error"', 'Wait 10 minutes after activating for the certificate to be issued.'],
            ['"Already in use"', 'Make sure no other service is using this domain.'],
        ]
        trouble_table = Table(trouble_data, colWidths=[2*inch, 4*inch])
        trouble_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ff6b6b")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(trouble_table)
        story.append(Spacer(1, 30))

        # Help section
        story.append(Paragraph("Need Help?", self.styles['WOPRHeading']))
        story.append(Paragraph(
            "We're here to help! Contact us at:",
            self.styles['WOPRStep']
        ))
        story.append(Paragraph("Email: support@wopr.systems", self.styles['WOPRStep']))
        story.append(Paragraph("Docs: docs.wopr.systems", self.styles['WOPRStep']))
        story.append(Paragraph("Community: community.wopr.systems", self.styles['WOPRStep']))

        # Footer
        story.append(Spacer(1, 40))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y')} | Customer ID: {info.customer_id}",
            self.styles['WOPRNote']
        ))

        # Build PDF
        doc.build(story)
        return filepath

    def generate_welcome_card(self, info: CustomerInfo) -> str:
        """
        Generate a welcome card with essential info.

        This is a single-page quick reference card.

        Args:
            info: Customer information

        Returns:
            Path to generated PDF
        """
        filename = f"{info.customer_id}_welcome_card.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        story = []

        # Header
        story.append(Paragraph("Welcome to WOPR", self.styles['WOPRTitle']))
        story.append(Paragraph(
            f"{info.bundle.title()} Sovereign Suite",
            self.styles['WOPRSubtitle']
        ))
        story.append(Spacer(1, 30))

        # Quick access
        story.append(Paragraph("Your Dashboard", self.styles['WOPRHeading']))

        access_data = [
            ['URL', info.full_wopr_url],
            ['IP Address', info.instance_ip],
        ]
        if info.custom_domain:
            access_data.append(['Custom Domain', f"https://{info.custom_domain} (after setup)"])

        access_table = Table(access_data, colWidths=[2*inch, 4*inch])
        access_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.BRAND_GREEN),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Courier'),
            ('FONTSIZE', (1, 0), (1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(access_table)
        story.append(Spacer(1, 30))

        # What's included
        story.append(Paragraph("What's Included", self.styles['WOPRHeading']))

        bundle_features = {
            'personal': [
                'Nextcloud - Files, Calendar, Contacts',
                'Vaultwarden - Password Manager',
                'Automated Daily Backups',
                'SSL Certificates',
            ],
            'creator': [
                'Everything in Personal, plus:',
                'Saleor - E-commerce Storefront',
                'Ghost - Blog Platform',
            ],
            'developer': [
                'Everything in Personal, plus:',
                'Forgejo - Git Repository',
                'Woodpecker - CI/CD Pipeline',
                'Reactor AI - Code Assistant',
            ],
            'professional': [
                'Everything in Creator + Developer, plus:',
                'Matrix - Team Chat',
                'Jitsi - Video Conferencing',
                'Collabora - Online Office',
                'Outline - Wiki & Docs',
            ],
        }

        features = bundle_features.get(info.bundle, bundle_features['personal'])
        features_list = ListFlowable([
            ListItem(Paragraph(f, self.styles['Normal']))
            for f in features
        ], bulletType='bullet')
        story.append(features_list)
        story.append(Spacer(1, 30))

        # Quick start
        story.append(Paragraph("Quick Start", self.styles['WOPRHeading']))
        quick_start = ListFlowable([
            ListItem(Paragraph(f"Visit <b>{info.full_wopr_url}</b>", self.styles['Normal'])),
            ListItem(Paragraph("Complete the setup wizard", self.styles['Normal'])),
            ListItem(Paragraph("Create your admin account", self.styles['Normal'])),
            ListItem(Paragraph("Start using your apps!", self.styles['Normal'])),
        ], bulletType='1')
        story.append(quick_start)
        story.append(Spacer(1, 30))

        # Support
        story.append(Paragraph("Get Help", self.styles['WOPRHeading']))
        support_data = [
            ['Documentation', 'docs.wopr.systems'],
            ['Email Support', 'support@wopr.systems'],
            ['Community Forum', 'community.wopr.systems'],
        ]
        support_table = Table(support_data, colWidths=[2*inch, 4*inch])
        support_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(support_table)

        # Footer
        story.append(Spacer(1, 40))
        story.append(Paragraph(
            f"Customer ID: {info.customer_id} | Created: {info.created_at.strftime('%B %d, %Y')}",
            self.styles['WOPRNote']
        ))
        story.append(Paragraph(
            "Thank you for choosing digital sovereignty!",
            self.styles['WOPRNote']
        ))

        # Build PDF
        doc.build(story)
        return filepath

    def generate_all_documents(self, info: CustomerInfo) -> Dict[str, str]:
        """
        Generate all documents for a customer.

        Args:
            info: Customer information

        Returns:
            Dict mapping document type to file path
        """
        docs = {
            'welcome_card': self.generate_welcome_card(info),
        }

        if info.custom_domain:
            docs['custom_domain_guide'] = self.generate_custom_domain_guide(info)

        return docs


# ============================================
# FALLBACK TEXT-BASED GENERATOR
# ============================================

def generate_custom_domain_text(info: CustomerInfo) -> str:
    """
    Generate plain text custom domain instructions.

    Fallback when reportlab is not available.
    """
    return f"""
================================================================================
                        WOPR SOVEREIGN SUITE
                    Custom Domain Setup Guide
================================================================================

Hello! This guide will help you connect your domain to your WOPR instance.

YOUR INSTANCE DETAILS
---------------------
IP Address:    {info.instance_ip}
WOPR URL:      {info.full_wopr_url}
Your Domain:   {info.custom_domain}
Bundle:        {info.bundle.title()}

================================================================================

STEP 1: LOG INTO YOUR DOMAIN REGISTRAR
--------------------------------------
Go to where you purchased your domain (GoDaddy, Namecheap, Cloudflare, etc.)
and find the DNS settings or DNS management page.

STEP 2: CREATE A DNS RECORD
---------------------------
Add a new DNS record with these settings:

    Type:           A
    Name/Host:      @  (or leave blank for root domain)
    Value/Points to: {info.instance_ip}
    TTL:            3600  (or "1 hour")

For a subdomain like cloud.{info.custom_domain}:
    Name/Host:      cloud
    (keep other settings the same)

STEP 3: WAIT FOR DNS TO UPDATE
------------------------------
DNS changes can take 5 minutes to 48 hours to take effect.
Check progress at: https://dnschecker.org

STEP 4: ACTIVATE IN WOPR
------------------------
1. Go to {info.full_wopr_url}
2. Log in with your admin account
3. Click Settings > Custom Domain
4. Enter: {info.custom_domain}
5. Click Activate

WOPR will automatically get an SSL certificate for your domain!

================================================================================

NEED HELP?
----------
Email:     support@wopr.systems
Docs:      https://docs.wopr.systems
Community: https://community.wopr.systems

================================================================================
Customer ID: {info.customer_id}
Generated: {datetime.now().strftime('%B %d, %Y')}

Thank you for choosing digital sovereignty!
================================================================================
"""


# ============================================
# NEW: Welcome Card Generator for Onboarding
# ============================================

def generate_welcome_pdf_for_email(
    name: str,
    email: str,
    beacon_name: str,
    bundle_name: str,
    tier_name: str,
    temp_password: str,
    apps: list,
) -> bytes:
    """
    Generate a welcome card PDF for email attachment.

    This is designed to be attached to the welcome email and provides
    a printable quick-reference card with credentials and app URLs.

    Args:
        name: Customer name
        email: Customer email
        beacon_name: Beacon subdomain
        bundle_name: Bundle display name
        tier_name: Tier display name
        temp_password: Temporary password
        apps: List of app dicts with name, icon, subdomain

    Returns:
        PDF as bytes
    """
    import io

    if not REPORTLAB_AVAILABLE:
        # Return a simple text-based fallback
        text = generate_welcome_text_fallback(
            name, email, beacon_name, bundle_name, tier_name, temp_password, apps
        )
        return text.encode('utf-8')

    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    # Brand colors
    WOPR_GREEN = colors.HexColor("#00ff41")
    WOPR_DARK = colors.HexColor("#0a0a0a")
    WOPR_SURFACE = colors.HexColor("#1a1a1a")
    WOPR_BORDER = colors.HexColor("#333333")
    WOPR_TEXT = colors.HexColor("#333333")  # Dark for print
    WOPR_TEXT_MUTED = colors.HexColor("#666666")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles for welcome card
    title_style = ParagraphStyle(
        name='WelcomeTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=WOPR_GREEN,
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )

    subtitle_style = ParagraphStyle(
        name='WelcomeSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=WOPR_TEXT_MUTED,
        spaceAfter=20,
        alignment=TA_CENTER,
    )

    section_style = ParagraphStyle(
        name='WelcomeSection',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=WOPR_GREEN,
        spaceBefore=20,
        spaceAfter=10,
        fontName='Helvetica-Bold',
    )

    body_style = ParagraphStyle(
        name='WelcomeBody',
        parent=styles['Normal'],
        fontSize=11,
        textColor=WOPR_TEXT,
        spaceAfter=8,
        leading=16,
    )

    label_style = ParagraphStyle(
        name='WelcomeLabel',
        parent=styles['Normal'],
        fontSize=10,
        textColor=WOPR_TEXT_MUTED,
        spaceAfter=2,
    )

    url_style = ParagraphStyle(
        name='WelcomeURL',
        parent=styles['Normal'],
        fontSize=14,
        textColor=WOPR_GREEN,
        fontName='Helvetica-Bold',
        spaceAfter=8,
        alignment=TA_CENTER,
    )

    story = []

    # Header
    story.append(Paragraph("WOPR", title_style))
    story.append(Paragraph("Your Personal Cloud Quick Reference", subtitle_style))
    story.append(Spacer(1, 20))

    # Welcome message
    story.append(Paragraph(f"Welcome, {name}!", section_style))
    story.append(Paragraph(
        "Keep this card somewhere safe. It contains your login credentials "
        "and quick access information for your WOPR Beacon.",
        body_style
    ))
    story.append(Spacer(1, 20))

    # Beacon URL Box
    story.append(HRFlowable(width="100%", thickness=2, color=WOPR_GREEN, spaceBefore=10, spaceAfter=10))
    story.append(Paragraph("Your Beacon URL", label_style))
    story.append(Paragraph(f"https://{beacon_name}.wopr.systems", url_style))
    story.append(HRFlowable(width="100%", thickness=2, color=WOPR_GREEN, spaceBefore=10, spaceAfter=10))
    story.append(Spacer(1, 20))

    # Account Details
    story.append(Paragraph("Account Details", section_style))

    account_data = [
        ["Bundle:", bundle_name],
        ["Tier:", tier_name],
        ["Email:", email],
    ]

    account_table = Table(account_data, colWidths=[1.5*inch, 4.5*inch])
    account_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (0, -1), WOPR_TEXT_MUTED),
        ('TEXTCOLOR', (1, 0), (1, -1), WOPR_TEXT),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ]))
    story.append(account_table)
    story.append(Spacer(1, 20))

    # Credentials Box
    story.append(Paragraph("Login Credentials", section_style))
    story.append(Paragraph(
        "Use these credentials to sign in to all your apps:",
        body_style
    ))
    story.append(Spacer(1, 10))

    cred_data = [
        ["Email:", email],
        ["Temporary Password:", temp_password],
    ]

    cred_table = Table(cred_data, colWidths=[2*inch, 4*inch])
    cred_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
        ('TEXTCOLOR', (0, 0), (0, -1), WOPR_TEXT_MUTED),
        ('TEXTCOLOR', (1, 0), (1, -1), WOPR_GREEN),
        ('FONTNAME', (1, 0), (1, -1), 'Courier'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 1, WOPR_BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 1, WOPR_BORDER),
    ]))
    story.append(cred_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<font color='#dc2626'>Important: Please change your password after your first login.</font>",
        body_style
    ))
    story.append(Spacer(1, 20))

    # Apps Section
    story.append(Paragraph("Your Apps", section_style))

    if apps:
        app_rows = []
        for i in range(0, len(apps), 2):
            row = []
            for j in range(2):
                if i + j < len(apps):
                    app = apps[i + j]
                    app_text = f"{app.get('icon', '')} {app['name']}\n{app.get('subdomain', '')}.{beacon_name}.wopr.systems"
                    row.append(app_text)
                else:
                    row.append("")
            app_rows.append(row)

        app_table = Table(app_rows, colWidths=[3*inch, 3*inch])
        app_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
            ('TEXTCOLOR', (0, 0), (-1, -1), WOPR_TEXT),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, WOPR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 1, WOPR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(app_table)

    story.append(Spacer(1, 30))

    # Getting Started Checklist
    story.append(Paragraph("Getting Started", section_style))

    checklist = [
        "1. Log in to your dashboard at your Beacon URL",
        "2. Change your temporary password immediately",
        "3. Enable two-factor authentication (2FA)",
        "4. Download mobile apps for Nextcloud, Vaultwarden, etc.",
        "5. Explore your apps and enjoy your personal cloud!",
    ]

    for item in checklist:
        story.append(Paragraph(f"<font color='#00ff41'>&#10003;</font> {item}", body_style))

    story.append(Spacer(1, 30))

    # Support
    story.append(HRFlowable(width="100%", thickness=1, color=WOPR_BORDER, spaceBefore=10, spaceAfter=10))
    story.append(Paragraph("Need Help?", section_style))
    story.append(Paragraph("Documentation: https://docs.wopr.systems", body_style))
    story.append(Paragraph("Support: support@wopr.systems", body_style))
    story.append(Spacer(1, 20))

    # Footer
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y')}",
        label_style
    ))
    story.append(Paragraph(
        "WOPR Systems - Your Personal Cloud Infrastructure",
        label_style
    ))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_welcome_text_fallback(
    name: str,
    email: str,
    beacon_name: str,
    bundle_name: str,
    tier_name: str,
    temp_password: str,
    apps: list,
) -> str:
    """Generate plain text welcome card as fallback."""
    apps_text = "\n".join([
        f"  - {app.get('name')}: {app.get('subdomain')}.{beacon_name}.wopr.systems"
        for app in apps
    ]) if apps else "  No apps configured"

    return f"""
================================================================================
                              WOPR
                    Your Personal Cloud Quick Reference
================================================================================

Welcome, {name}!

Keep this card somewhere safe. It contains your login credentials
and quick access information for your WOPR Beacon.

--------------------------------------------------------------------------------
                            YOUR BEACON URL
                   https://{beacon_name}.wopr.systems
--------------------------------------------------------------------------------

ACCOUNT DETAILS
---------------
Bundle:     {bundle_name}
Tier:       {tier_name}
Email:      {email}

LOGIN CREDENTIALS
-----------------
Email:              {email}
Temporary Password: {temp_password}

*** IMPORTANT: Please change your password after your first login. ***

YOUR APPS
---------
{apps_text}

GETTING STARTED
---------------
[X] 1. Log in to your dashboard at your Beacon URL
[ ] 2. Change your temporary password immediately
[ ] 3. Enable two-factor authentication (2FA)
[ ] 4. Download mobile apps for Nextcloud, Vaultwarden, etc.
[ ] 5. Explore your apps and enjoy your personal cloud!

NEED HELP?
----------
Documentation: https://docs.wopr.systems
Support:       support@wopr.systems

================================================================================
Generated on {datetime.now().strftime('%B %d, %Y')}
WOPR Systems - Your Personal Cloud Infrastructure
================================================================================
"""
