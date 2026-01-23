# WOPR One-Click Installer: User Onboarding Flow

**Version:** 1.5
**Target Market:** USA
**Audience:** Implementation Reference

## Overview

This document describes the complete user journey from landing on wopr.systems to having a running WOPR instance. The flow is designed for non-technical users who want to escape Big Tech without needing to understand servers.

**The Beacon Concept:** Each WOPR installation is called a Beacon - your lifeboat for digital freedom. Your Beacon runs on a server you control, and connects back to WOPR Lighthouses for updates and support. Your data stays with you.

## User Journey Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER ONBOARDING FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   [1. LANDING PAGE]                                                          │
│         │                                                                    │
│         ▼                                                                    │
│   [2. BUNDLE SELECTION]  ──────────────────────────────────────────┐        │
│         │                                                          │        │
│         │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐ │        │
│         │   │Personal │  │Creator  │  │Developer│  │Professional│ │        │
│         │   │ $9.99   │  │ $19.99  │  │ $29.99  │  │  $49.99    │ │        │
│         │   └─────────┘  └─────────┘  └─────────┘  └────────────┘ │        │
│         │                                                          │        │
│         ▼                                                                    │
│   [3. REGION SELECTION]                                                      │
│         │                                                                    │
│         │   ┌──────────────────────────────────────────────────┐            │
│         │   │  US West    │   US Central   │    US East        │            │
│         │   │  CA, OR, WA │   TX, IL       │    NY, NJ, VA...  │            │
│         │   └──────────────────────────────────────────────────┘            │
│         │                                                                    │
│         ▼                                                                    │
│   [4. PROVIDER SELECTION]                                                    │
│         │                                                                    │
│         │   ┌────────────┬─────────────┬──────────────┬─────────┐           │
│         │   │ Hetzner    │ Vultr       │ Linode       │ DO      │           │
│         │   │ $4.49/mo   │ $10.00/mo   │ $5.00/mo     │ $12/mo  │           │
│         │   │ ★ Cheapest │ Most DCs    │ Akamai Net   │ Best UX │           │
│         │   └────────────┴─────────────┴──────────────┴─────────┘           │
│         │                                                                    │
│         ▼                                                                    │
│   [5. CUSTOMIZATION]                                                         │
│         │                                                                    │
│         │   • Custom domain (optional): mycloud.example.com                 │
│         │   • Admin email                                                    │
│         │                                                                    │
│         ▼                                                                    │
│   [6. CHECKOUT SUMMARY]                                                      │
│         │                                                                    │
│         │   Bundle: Personal Sovereign Suite                                │
│         │   Hosting: Hetzner (Ashburn, VA)           $4.49/mo               │
│         │   WOPR Service Fee:                        $9.99/mo               │
│         │   ─────────────────────────────────────────────────               │
│         │   Total:                                  $14.48/mo               │
│         │                                                                    │
│         ▼                                                                    │
│   [7. STRIPE CHECKOUT]                                                       │
│         │                                                                    │
│         │   ┌──────────────────────────────────────┐                        │
│         │   │         Stripe Payment Page          │                        │
│         │   │   Card: **** **** **** 4242          │                        │
│         │   │   [Pay $14.48/month]                 │                        │
│         │   └──────────────────────────────────────┘                        │
│         │                                                                    │
│         ▼                                                                    │
│   [8. PROVISIONING]  ←── Webhook triggers this                              │
│         │                                                                    │
│         │   ┌──────────────────────────────────────────────┐                │
│         │   │  "Setting up your Sovereign Suite..."        │                │
│         │   │                                              │                │
│         │   │  ✓ Creating your server          [DONE]     │                │
│         │   │  ✓ Configuring network           [DONE]     │                │
│         │   │  ◐ Installing WOPR apps          [2 min]    │                │
│         │   │  ○ Setting up security                      │                │
│         │   │  ○ Generating credentials                   │                │
│         │   │                                              │                │
│         │   │  Your suite will be ready in ~5 minutes     │                │
│         │   └──────────────────────────────────────────────┘                │
│         │                                                                    │
│         ▼                                                                    │
│   [9. WELCOME]                                                               │
│         │                                                                    │
│         │   ┌──────────────────────────────────────────────┐                │
│         │   │  🎉 Your Sovereign Suite is Ready!           │                │
│         │   │                                              │                │
│         │   │  Access your dashboard:                     │                │
│         │   │  https://personal-abc12345.wopr.systems     │                │
│         │   │                                              │                │
│         │   │  [Go to Dashboard]  [Download Setup Guide]  │                │
│         │   └──────────────────────────────────────────────┘                │
│         │                                                                    │
│         ▼                                                                    │
│   [10. EMAIL SENT]                                                           │
│                                                                              │
│         • Welcome email with dashboard link                                 │
│         • PDF: Custom domain setup guide (if requested)                     │
│         • PDF: Getting started guide                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Step Details

### Step 1: Landing Page

**URL:** `https://wopr.systems`

**Content:**
- Hero: "Your Data. Your Cloud. Your Rules."
- Subhead: "Escape Big Tech. Own your infrastructure."
- Brief explanation of data sovereignty
- Bundle comparison cards
- CTA: "Get Started"

### Step 2: Bundle Selection

**URL:** `https://wopr.systems/get-started`

**UI Elements:**
- Four bundle cards side by side
- Each card shows:
  - Bundle name
  - Monthly price
  - 4-5 key features with icons
  - "Select" button
- Comparison table below (expandable)

**Bundle Cards:**

| Personal $9.99/mo | Creator $19.99/mo | Developer $29.99/mo | Professional $49.99/mo |
|-------------------|-------------------|---------------------|------------------------|
| File Storage | Everything in Personal | Everything in Personal | Everything in Creator + Developer |
| Calendar & Contacts | + Online Store | + Code Repository | + Team Chat |
| Password Manager | + Blog Platform | + CI/CD Pipeline | + Video Calls |
| News Reader | + Portfolio Site | + AI Code Assistant | + Online Office |
| Daily Backups | | | + Wiki/Docs |

### Step 3: Region Selection

**URL:** `https://wopr.systems/get-started?bundle=personal`

**UI Elements:**
- Map of USA with three highlighted regions
- Region cards:
  - US West (California, Oregon, Washington)
  - US Central (Texas, Illinois)
  - US East (New York, Virginia, Georgia, Florida)
- "Best for you" recommendation based on user's IP geolocation
- Explanation: "Choose a region close to you for the best performance."

### Step 4: Provider Selection

**URL:** `https://wopr.systems/get-started?bundle=personal&region=us-east`

**UI Elements:**
- Provider cards showing:
  - Provider logo
  - Monthly hosting cost
  - Available cities in selected region
  - Badges: "Cheapest", "Most Locations", "Best Network"
  - Pros/cons expandable

**Example for US East + Personal Bundle:**

| Provider | Hosting Cost | Cities | Notes |
|----------|--------------|--------|-------|
| Hetzner ⭐ | $4.49/mo | Ashburn, VA | Best value, 20TB traffic |
| Linode | $5.00/mo | Newark, Atlanta, Miami | Akamai network |
| Vultr | $10.00/mo | Newark, Atlanta, Miami | Fast provisioning |
| DigitalOcean | $12.00/mo | New York | Best docs |

### Step 5: Customization

**URL:** `https://wopr.systems/get-started?bundle=personal&region=us-east&provider=hetzner`

**Form Fields:**
- Email address (required)
- Custom domain (optional)
  - "Want to use your own domain? (e.g., mycloud.example.com)"
  - "We'll email you setup instructions"
- Promo code (optional)

**Validation:**
- Email: Valid format
- Domain: Valid domain format, no http/https

### Step 6: Checkout Summary

**URL:** `https://wopr.systems/checkout`

**UI Elements:**
- Order summary box:
  ```
  Personal Sovereign Suite

  Hosting: Hetzner Cloud (Ashburn, VA)
  - 2 vCPU, 2GB RAM, 40GB SSD
  - 20TB monthly traffic
  - Hosting cost: $4.49/mo

  WOPR Service:
  - Software & updates
  - Automated backups
  - SSL certificates
  - Support access
  - Service fee: $9.99/mo

  ─────────────────────────
  Monthly Total: $14.48/mo

  ☑ I agree to the Terms of Service

  [Proceed to Payment]
  ```

### Step 7: Stripe Checkout

**Integration:** Stripe Checkout (hosted page)

**Session Creation:**
```python
session = stripe.checkout.Session.create(
    mode="subscription",
    customer_email=user_email,
    line_items=[
        {"price": "price_personal_monthly", "quantity": 1}
    ],
    success_url="https://wopr.systems/setup?session_id={CHECKOUT_SESSION_ID}",
    cancel_url="https://wopr.systems/checkout?cancelled=true",
    metadata={
        "wopr_bundle": "personal",
        "wopr_provider": "hetzner",
        "wopr_region": "us-east",
        "wopr_datacenter": "ash",
        "wopr_custom_domain": "mycloud.example.com"
    }
)
```

### Step 8: Provisioning (Post-Payment)

**URL:** `https://wopr.systems/setup?session_id=...`

**Triggered by:** `checkout.session.completed` webhook

**Provisioning Steps:**
1. Create VPS instance (30-60 seconds)
2. Wait for boot and IP assignment (30-60 seconds)
3. Configure DNS subdomain (instant)
4. Cloud-init runs WOPR installer (2-4 minutes)
5. Generate PDF documents
6. Send welcome email

**UI:** Real-time progress page with:
- Animated progress indicator
- Step checklist with status icons
- Estimated time remaining
- "We'll email you when your instance is ready" message

### Step 9: Welcome Page

**URL:** `https://wopr.systems/welcome?job_id=...`

**UI Elements:**
```
┌────────────────────────────────────────────────────┐
│                                                     │
│        🎉 Your Sovereign Suite is Ready!            │
│                                                     │
│   Access your dashboard at:                        │
│   ┌─────────────────────────────────────────────┐  │
│   │ https://personal-abc12345.wopr.systems      │  │
│   └─────────────────────────────────────────────┘  │
│                                                     │
│   [Go to Dashboard]                                │
│                                                     │
│   ─────────────────────────────────────────────    │
│                                                     │
│   📧 We've emailed you:                            │
│   • Login instructions                             │
│   • Getting started guide                          │
│   • Custom domain setup guide (PDF)                │
│                                                     │
│   ─────────────────────────────────────────────    │
│                                                     │
│   📋 Quick Links:                                  │
│   [Download Setup Guide]  [View Documentation]     │
│   [Contact Support]       [Community Forum]        │
│                                                     │
└────────────────────────────────────────────────────┘
```

### Step 10: Welcome Email

**Subject:** "Welcome to WOPR - Your Sovereign Suite is Ready"

**Content:**
```
Hello!

Your WOPR Sovereign Suite is now online and ready to use.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR DASHBOARD
--------------
https://personal-abc12345.wopr.systems

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GETTING STARTED
---------------
1. Click the link above
2. Complete the setup wizard (2 minutes)
3. Create your admin password
4. Start using your apps!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ATTACHED GUIDES
---------------
📎 WOPR_Welcome_Card.pdf - Quick reference
📎 Custom_Domain_Setup.pdf - Connect your domain

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEED HELP?
----------
Docs: https://docs.wopr.systems
Support: support@wopr.systems
Community: https://community.wopr.systems

The WOPR Team
```

## Error Handling

### Payment Failed
- Show clear error message
- Offer retry option
- Link to support

### Provisioning Failed
- Show error status on progress page
- Automatic retry (up to 3 times)
- Email notification with support contact
- Full refund if unrecoverable

### DNS Propagation Delayed
- Not blocking - user can always access via IP
- Custom domain guide explains wait time
- Check again later instructions

## Technical Implementation Files

| Component | File |
|-----------|------|
| Stripe Integration | `control_plane/billing.py` |
| Orchestrator | `control_plane/orchestrator.py` |
| Provider APIs | `control_plane/providers/` |
| PDF Generation | `control_plane/pdf_generator.py` |
| Plan Registry | `control_plane/providers/plan_registry.py` |
| Install Scripts | `scripts/wopr_install.sh` |

## Pricing Summary (v1.0 USA)

| Bundle | WOPR Fee | Cheapest Hosting | Total/mo |
|--------|----------|------------------|----------|
| Personal | $9.99 | Hetzner $4.49 | $14.48 |
| Creator | $19.99 | Hetzner $8.49 | $28.48 |
| Developer | $29.99 | Hetzner $8.49 | $38.48 |
| Professional | $49.99 | Hetzner $15.99 | $65.98 |

Note: Hosting costs paid directly to VPS provider. WOPR fee covers software, updates, backups, support.
