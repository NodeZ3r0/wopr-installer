<script>
	import { onMount, onDestroy } from 'svelte';

	export let currentStep = 0;
	export let progress = 0;

	let currentSlide = 0;
	let autoAdvance = true;
	let slideInterval;

	// Slides organized by provisioning phase
	// Each phase has multiple slides that cycle during that step
	const slideGroups = {
		0: [ // Payment received
			{
				title: "INITIALIZING BEACON",
				subtitle: "Payment Confirmed",
				content: `Your transaction has been verified and logged.

We're now preparing to deploy your personal
sovereign computing environment.

> "The only winning move is to play."
  - WOPR, 1983`,
				ascii: `
    .---.
   /     \\
   \\.@-@./
   /\`\\_/\`\\
  //  _  \\\\
 | \\     / |
  \\|  V  |/
   \`-----\``
			},
			{
				title: "DATA SOVEREIGNTY",
				subtitle: "Your Data. Your Rules.",
				content: `Unlike cloud services that mine your data,
WOPR Beacons run entirely on YOUR hardware.

No telemetry. No analytics. No backdoors.
Your applications answer only to you.

Every service is self-hosted, every key
is yours, every byte stays under your control.`,
				ascii: `
   [========]
   |  YOUR  |
   |  DATA  |
   |  ONLY  |
   [========]
      |  |
   ___/  \\___`
			}
		],
		1: [ // Creating server
			{
				title: "SPAWNING INSTANCE",
				subtitle: "Cloud Infrastructure",
				content: `Provisioning a dedicated virtual server
in a hardened datacenter environment.

Your beacon will have:
- Dedicated CPU cores
- Encrypted SSD storage
- Private networking
- Automatic backups`,
				ascii: `
   _______
  |       |
  | [===] |
  | [===] |
  | [===] |
  |_______|
   /     \\
  /_______\\`
			},
			{
				title: "HARDWARE SPECS",
				subtitle: "What You're Getting",
				content: `Depending on your tier, your beacon runs on:

TIER 1: 2 vCPU / 4GB RAM / 80GB NVMe
TIER 2: 4 vCPU / 8GB RAM / 160GB NVMe
TIER 3: 8 vCPU / 16GB RAM / 320GB NVMe

All tiers include 20TB monthly bandwidth
and automatic security updates.`,
				ascii: `
  .--------.
  |  CPU   |
  |########|
  |########|
  '--------'
   |  ||  |`
			},
			{
				title: "ZERO TRUST SECURITY",
				subtitle: "Defense in Depth",
				content: `Your beacon is hardened from boot:

- Firewall rules locked down
- SSH key-only authentication
- Automatic certificate provisioning
- Container isolation for all services
- Regular security scanning`,
				ascii: `
    _____
   /     \\
  | LOCK |
  |  []  |
   \\_____/
     | |
   __|_|__`
			}
		],
		2: [ // DNS configuration
			{
				title: "DNS PROPAGATION",
				subtitle: "Mapping Your Domain",
				content: `Setting up your beacon's identity on the
global DNS infrastructure.

Your beacon URL will be:
  [beaconname].wopr.systems

Custom domains can be added later from
your beacon's settings panel.`,
				ascii: `
  .---.     .---.
  | A |---->| B |
  '---'     '---'
    |         |
    v         v
  .---.     .---.
  | C |<----| D |
  '---'     '---'`
			},
			{
				title: "SSL CERTIFICATES",
				subtitle: "Automatic HTTPS",
				content: `Your beacon uses Let's Encrypt for
automatic TLS certificate management.

- Certificates auto-renew
- A+ SSL rating out of the box
- HTTP automatically redirects to HTTPS
- Modern cipher suites only`,
				ascii: `
   _________
  /  HTTPS  \\
 |   .--.    |
 |  ( OK )   |
 |   '--'    |
  \\_________/`
			}
		],
		3: [ // Installing WOPR
			{
				title: "DEPLOYING MODULES",
				subtitle: "Your Application Stack",
				content: `Installing the services you selected:

Each module runs in an isolated container
with its own resources and permissions.

Single Sign-On connects everything with
one secure login across all your apps.`,
				ascii: `
  [M1] [M2] [M3]
   |    |    |
  ----+----+----
       |
   [BEACON]`
			},
			{
				title: "AUTHENTIK SSO",
				subtitle: "Identity Management",
				content: `Authentik provides enterprise-grade
identity management for your beacon:

- Single Sign-On across all services
- Two-factor authentication
- LDAP/SAML/OAuth2 support
- User and group management
- Audit logging`,
				ascii: `
    .-----.
   /  SSO  \\
  |  =====  |
  | |     | |
  | | LOG | |
  | | IN  | |
  |  =====  |
   \\_______/`
			},
			{
				title: "CONTAINER RUNTIME",
				subtitle: "Podman Orchestration",
				content: `Your services run on Podman - a secure,
rootless container runtime.

Unlike Docker, Podman runs without a
daemon and supports rootless containers
for enhanced security isolation.`,
				ascii: `
  .---.  .---.  .---.
  |   |  |   |  |   |
  | P |  | O |  | D |
  |   |  |   |  |   |
  '---'  '---'  '---'
    \\_____|_____/`
			},
			{
				title: "AI REMEDIATION",
				subtitle: "Self-Healing Infrastructure",
				content: `Your beacon includes AI-powered
self-healing capabilities:

TIER 1: Auto-fix safe issues
TIER 2: Suggest fixes, await approval
TIER 3: Escalate to WOPR support

Problems are detected and resolved
before you even notice them.`,
				ascii: `
     .---.
    / A.I \\
   |  ___  |
   | |   | |
   | |FIX| |
   | |___| |
    \\_____/`
			}
		],
		4: [ // Final configuration
			{
				title: "CREATING ACCOUNTS",
				subtitle: "Your Credentials",
				content: `Setting up your administrator account
and generating secure credentials.

Your login details will be sent to the
email address you provided during
checkout.

Please check your inbox (and spam folder)
for the welcome email.`,
				ascii: `
   .-------.
  /  ADMIN  \\
 |  -------  |
 |  | USR |  |
 |  -------  |
 |  | *** |  |
 |  -------  |
  \\_________/`
			},
			{
				title: "OTHER WOPR PRODUCTS",
				subtitle: "Expand Your Sovereignty",
				content: `WOPR offers additional services:

SONICFORGE - AI music production suite
  Create, mix, master with AI assistance

WOPR SUPPORT - Priority assistance
  Direct access to infrastructure experts

CUSTOM MODULES - Bespoke applications
  We can containerize your software`,
				ascii: `
  +---------+
  | WOPR    |
  | SYSTEMS |
  +---------+
   / | | \\
  S  F S  C`
			}
		],
		5: [ // Ready
			{
				title: "BEACON ONLINE",
				subtitle: "Deployment Complete",
				content: `Your sovereign beacon is now operational.

All systems nominal. All services running.
Your dashboard awaits.

Welcome to the resistance against
corporate cloud hegemony.

> SHALL WE PLAY A GAME?`,
				ascii: `
      *
     /|\\
    / | \\
   /  |  \\
  /   *   \\
 /_________\\
    READY`
			}
		]
	};

	// Get slides for current provisioning step
	$: currentSlides = slideGroups[currentStep] || slideGroups[0];
	$: slide = currentSlides[currentSlide % currentSlides.length];

	// Auto-advance slides within current step
	onMount(() => {
		slideInterval = setInterval(() => {
			if (autoAdvance && currentSlides.length > 1) {
				currentSlide = (currentSlide + 1) % currentSlides.length;
			}
		}, 8000); // Change slide every 8 seconds
	});

	onDestroy(() => {
		if (slideInterval) clearInterval(slideInterval);
	});

	// Reset to first slide when step changes
	$: if (currentStep !== undefined) {
		currentSlide = 0;
	}

	function nextSlide() {
		currentSlide = (currentSlide + 1) % currentSlides.length;
	}

	function prevSlide() {
		currentSlide = (currentSlide - 1 + currentSlides.length) % currentSlides.length;
	}
</script>

<div class="crt-container">
	<div class="scanlines"></div>
	<div class="crt-content">
		<header class="slide-header">
			<div class="terminal-prompt">WOPR://beacon/setup</div>
			<div class="slide-counter">[{currentSlide + 1}/{currentSlides.length}]</div>
		</header>

		<div class="slide-body">
			<div class="slide-text">
				<h2 class="slide-title">{slide.title}</h2>
				<h3 class="slide-subtitle">{slide.subtitle}</h3>
				<pre class="slide-content">{slide.content}</pre>
			</div>

			<div class="slide-ascii">
				<pre>{slide.ascii}</pre>
			</div>
		</div>

		<footer class="slide-footer">
			<div class="nav-controls">
				{#if currentSlides.length > 1}
					<button class="nav-btn" on:click={prevSlide}>[&lt;]</button>
					<div class="slide-dots">
						{#each currentSlides as _, i}
							<span class="dot" class:active={i === currentSlide % currentSlides.length}></span>
						{/each}
					</div>
					<button class="nav-btn" on:click={nextSlide}>[&gt;]</button>
				{/if}
			</div>
			<div class="progress-bar">
				<div class="progress-fill" style="width: {progress}%"></div>
			</div>
		</footer>
	</div>
	<div class="crt-flicker"></div>
</div>

<style>
	.crt-container {
		position: relative;
		background: #0a0a0a;
		border: 2px solid #00ff41;
		border-radius: 8px;
		padding: 1.5rem;
		margin: 2rem 0;
		overflow: hidden;
		font-family: 'Courier New', 'Consolas', monospace;
		box-shadow:
			0 0 20px rgba(0, 255, 65, 0.3),
			inset 0 0 60px rgba(0, 255, 65, 0.05);
	}

	/* CRT Scanlines */
	.scanlines {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: repeating-linear-gradient(
			0deg,
			rgba(0, 0, 0, 0.15),
			rgba(0, 0, 0, 0.15) 1px,
			transparent 1px,
			transparent 2px
		);
		pointer-events: none;
		z-index: 10;
	}

	/* Subtle flicker effect */
	.crt-flicker {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 255, 65, 0.02);
		pointer-events: none;
		z-index: 11;
		animation: flicker 0.15s infinite;
	}

	@keyframes flicker {
		0% { opacity: 0.97; }
		50% { opacity: 1; }
		100% { opacity: 0.98; }
	}

	.crt-content {
		position: relative;
		z-index: 5;
	}

	.slide-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid #00ff4140;
		margin-bottom: 1rem;
	}

	.terminal-prompt {
		color: #00ff41;
		font-size: 0.8rem;
		opacity: 0.7;
	}

	.slide-counter {
		color: #00ff41;
		font-size: 0.8rem;
		opacity: 0.5;
	}

	.slide-body {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 2rem;
		min-height: 280px;
		align-items: start;
	}

	@media (max-width: 768px) {
		.slide-body {
			grid-template-columns: 1fr;
		}
		.slide-ascii {
			display: none;
		}
	}

	.slide-text {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.slide-title {
		color: #00ff41;
		font-size: 1.5rem;
		font-weight: bold;
		margin: 0;
		text-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
		letter-spacing: 2px;
	}

	.slide-subtitle {
		color: #00cc33;
		font-size: 1rem;
		font-weight: normal;
		margin: 0 0 1rem 0;
		opacity: 0.8;
	}

	.slide-content {
		color: #00dd3a;
		font-size: 0.9rem;
		line-height: 1.6;
		margin: 0;
		white-space: pre-wrap;
		font-family: inherit;
	}

	.slide-ascii {
		color: #00ff41;
		font-size: 0.75rem;
		line-height: 1.2;
		opacity: 0.6;
		padding: 1rem;
		border-left: 1px solid #00ff4130;
	}

	.slide-ascii pre {
		margin: 0;
		font-family: inherit;
	}

	.slide-footer {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid #00ff4140;
	}

	.nav-controls {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.nav-btn {
		background: transparent;
		border: 1px solid #00ff4160;
		color: #00ff41;
		padding: 0.25rem 0.5rem;
		font-family: inherit;
		font-size: 0.9rem;
		cursor: pointer;
		transition: all 0.2s;
	}

	.nav-btn:hover {
		background: #00ff4120;
		border-color: #00ff41;
	}

	.slide-dots {
		display: flex;
		gap: 0.5rem;
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #00ff4130;
		transition: all 0.3s;
	}

	.dot.active {
		background: #00ff41;
		box-shadow: 0 0 8px #00ff41;
	}

	.progress-bar {
		height: 3px;
		background: #00ff4120;
		border-radius: 2px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: #00ff41;
		box-shadow: 0 0 10px #00ff41;
		transition: width 0.5s ease;
	}
</style>
