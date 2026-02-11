# WOPR Glossary

**Version:** 1.5
**Audience:** Developers, Users, Marketing

## Core Concepts

### Beacon

Your personal WOPR installation - a lifeboat for digital freedom, running on infrastructure you own or control.

Beacons connect back to **WOPR Lighthouses** for updates, support, and optional services. But your data stays on your Beacon, not on our servers.

**Note:** In user-facing UI, keep it simple - "Your suite is ready" rather than flowery lighthouse prose. The beacon concept is background context, not action language.

### Sovereign Suite

The complete package of applications that runs on your Beacon. Different bundles (Personal, Creator, Developer, Professional) include different applications, but they're all part of the Sovereign Suite.

### Bundle

A pre-configured set of modules designed for a specific use case:

| Bundle | Use Case |
|--------|----------|
| Personal | Individuals and families |
| Creator | Artists, writers, sellers |
| Developer | Coders and developers |
| Professional | Freelancers, consultants, teams |

### Module

A single application that runs on a WOPR instance. Examples: Nextcloud (files), Vaultwarden (passwords), Reactor AI (coding assistant).

### Trial

A 90-day free period where users can try modules not included in their bundle.

### Lighthouse

WOPR's central infrastructure that Beacons connect to. Lighthouses provide:
- Software updates and security patches
- DNS management (yourname.wopr.systems)
- Billing and subscription management
- Optional support services

Your data stays on your Beacon - Lighthouses just guide the way.

## Technical Terms

### Control Plane

The WOPR backend that manages instances - provisioning, billing, DNS, monitoring. Users never interact with it directly.

### Provider

A VPS hosting company (Hetzner, Vultr, Linode, DigitalOcean) where WOPR instances can be hosted. Multi-provider support means no vendor lock-in.

### DEFCON ONE

The protected actions gateway. Ensures AI and automation can't make production changes without human approval. "AI doesn't get root. People do."

### Authentik

The identity provider that handles Single Sign-On across all Beacon apps. "One Key to Rule Them All."

## Language Guidelines

### Marketing/Landing Pages

The beacon concept can appear in high-level marketing context if desired, but keep it subtle. Focus on practical benefits: data ownership, privacy, escaping Big Tech.

### Technical Docs and User-Facing Text

Use clear, direct language:
- "Your WOPR instance"
- "Your suite is ready"
- "Installation complete"
- "Configure your dashboard at..."

Avoid forcing beacon metaphors into action language or UI copy.

## What NOT to Do

- Don't overuse the metaphor - it's a conceptual background idea, not literal action language
- Don't use "beacon" as a verb ("beacon your data", "light your beacon")
- Don't use lighthouse language in user-facing UI, confirmation dialogs, or PDF documents
- Don't use "beacon" in API parameter names or technical identifiers - use `instance_id`, not `beacon_id`
- Don't make users feel like they're "lighting a lighthouse" - they're setting up their personal cloud

## Examples

**Good**: "Your Sovereign Suite is ready. Access your dashboard at..."
**Bad**: "Your lighthouse has been lit! Navigate to your safe harbor at..."

**Good**: "Get Started" (button text)
**Bad**: "Light your Beacon" (too flowery for a CTA)

**Good**: Clear technical language in installation scripts and system output
**Bad**: "Lighting your beacon..." status messages
