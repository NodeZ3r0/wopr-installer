<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let beaconName = '';
	let bundleName = '';
	let apps = [];

	onMount(async () => {
		// Get beacon info from URL params or API
		beaconName = $page.url.searchParams.get('beacon') || '';

		// Fetch the user's beacon info
		try {
			const response = await fetch('/api/v1/instance');
			if (response.ok) {
				const data = await response.json();
				beaconName = data.instance?.domain?.replace('.wopr.systems', '') || beaconName;
				bundleName = data.instance?.bundle || '';

				// Get installed modules/apps
				apps = (data.modules || [])
					.filter(m => m.status === 'included' || m.status === 'installed')
					.slice(0, 8); // Show top 8 apps
			}
		} catch (e) {
			console.error('Failed to fetch instance info:', e);
		}
	});

	const quickLinks = [
		{ name: 'Nextcloud', icon: '☁️', description: 'Files, Calendar, Contacts', url: '/go/files' },
		{ name: 'Vaultwarden', icon: '🔐', description: 'Password Manager', url: '/go/passwords' },
		{ name: 'FreshRSS', icon: '📰', description: 'News & Feeds', url: '/go/rss' },
		{ name: 'Settings', icon: '⚙️', description: 'Configure your Beacon', url: '/settings' },
	];

	const gettingStarted = [
		{ done: true, task: 'Create your account' },
		{ done: true, task: 'Set up your Beacon' },
		{ done: false, task: 'Install browser extension for passwords' },
		{ done: false, task: 'Connect your mobile devices' },
		{ done: false, task: 'Set up custom domain (optional)' },
		{ done: false, task: 'Invite family/team members' },
	];
</script>

<svelte:head>
	<title>Welcome to WOPR - Your Beacon is Ready!</title>
</svelte:head>

<div class="welcome-container">
	<!-- Hero Section -->
	<div class="hero">
		<div class="hero-icon">
			<svg viewBox="0 0 24 24" fill="currentColor">
				<path d="M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97 0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.31-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66z"/>
			</svg>
		</div>
		<h1>Welcome to Your Beacon!</h1>
		<p class="subtitle">
			{#if beaconName}
				<strong>{beaconName}.wopr.systems</strong> is online and ready to use.
			{:else}
				Your personal cloud is online and ready to use.
			{/if}
		</p>
	</div>

	<!-- Quick Links -->
	<section class="quick-links">
		<h2>Quick Access</h2>
		<div class="links-grid">
			{#each quickLinks as link}
				<a href={link.url} class="quick-link-card">
					<span class="link-icon">{link.icon}</span>
					<span class="link-name">{link.name}</span>
					<span class="link-desc">{link.description}</span>
				</a>
			{/each}
		</div>
	</section>

	<!-- Getting Started Checklist -->
	<section class="getting-started">
		<h2>Getting Started</h2>
		<div class="checklist">
			{#each gettingStarted as item}
				<div class="checklist-item" class:done={item.done}>
					<span class="check-icon">
						{#if item.done}
							✓
						{:else}
							○
						{/if}
					</span>
					<span class="check-text">{item.task}</span>
				</div>
			{/each}
		</div>
	</section>

	<!-- Resources -->
	<section class="resources">
		<h2>Helpful Resources</h2>
		<div class="resources-grid">
			<a href="https://docs.wopr.systems" target="_blank" class="resource-card">
				<span class="resource-icon">📚</span>
				<span class="resource-title">Documentation</span>
				<span class="resource-desc">Guides and tutorials</span>
			</a>
			<a href="/settings" class="resource-card">
				<span class="resource-icon">🎨</span>
				<span class="resource-title">Customize Theme</span>
				<span class="resource-desc">Make it yours</span>
			</a>
			<a href="/billing" class="resource-card">
				<span class="resource-icon">💳</span>
				<span class="resource-title">Billing</span>
				<span class="resource-desc">Manage subscription</span>
			</a>
			<a href="https://wopr.systems/support" target="_blank" class="resource-card">
				<span class="resource-icon">💬</span>
				<span class="resource-title">Get Help</span>
				<span class="resource-desc">Contact support</span>
			</a>
		</div>
	</section>

	<!-- Custom Domain CTA -->
	<section class="custom-domain-cta">
		<div class="cta-content">
			<h3>Want your own domain?</h3>
			<p>Connect a custom domain like <strong>cloud.yourname.com</strong> to your Beacon.</p>
			<a href="/settings/domain" class="btn btn-secondary">Set Up Custom Domain</a>
		</div>
	</section>
</div>

<style>
	.welcome-container {
		max-width: 900px;
		margin: 0 auto;
		padding: 2rem 1rem;
	}

	/* Hero */
	.hero {
		text-align: center;
		padding: 3rem 0;
		margin-bottom: 2rem;
		background: linear-gradient(180deg, var(--theme-surface) 0%, transparent 100%);
		border-radius: var(--theme-radius);
	}

	.hero-icon {
		width: 80px;
		height: 80px;
		margin: 0 auto 1.5rem;
		color: var(--theme-primary);
		filter: drop-shadow(0 0 20px var(--theme-primary));
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { transform: scale(1); opacity: 1; }
		50% { transform: scale(1.05); opacity: 0.9; }
	}

	.hero-icon svg {
		width: 100%;
		height: 100%;
	}

	.hero h1 {
		font-size: 2.5rem;
		margin-bottom: 0.75rem;
		color: var(--theme-text);
	}

	.subtitle {
		font-size: 1.2rem;
		color: var(--theme-text-muted);
	}

	.subtitle strong {
		color: var(--theme-primary);
	}

	/* Sections */
	section {
		margin-bottom: 2.5rem;
	}

	section h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
		color: var(--theme-text);
	}

	/* Quick Links */
	.links-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 1rem;
	}

	.quick-link-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1.5rem;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		text-decoration: none;
		transition: all 0.2s;
	}

	.quick-link-card:hover {
		border-color: var(--theme-primary);
		transform: translateY(-2px);
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
	}

	.link-icon {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.link-name {
		font-weight: 600;
		color: var(--theme-text);
		margin-bottom: 0.25rem;
	}

	.link-desc {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		text-align: center;
	}

	/* Getting Started */
	.checklist {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1rem;
	}

	.checklist-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem;
		border-bottom: 1px solid var(--theme-border);
	}

	.checklist-item:last-child {
		border-bottom: none;
	}

	.check-icon {
		width: 24px;
		height: 24px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		font-size: 0.8rem;
		flex-shrink: 0;
	}

	.checklist-item.done .check-icon {
		background: var(--theme-success);
		color: #fff;
	}

	.checklist-item:not(.done) .check-icon {
		border: 2px solid var(--theme-border);
		color: var(--theme-text-muted);
	}

	.check-text {
		color: var(--theme-text);
	}

	.checklist-item.done .check-text {
		text-decoration: line-through;
		opacity: 0.6;
	}

	/* Resources */
	.resources-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 1rem;
	}

	.resource-card {
		display: flex;
		flex-direction: column;
		padding: 1.25rem;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		text-decoration: none;
		transition: all 0.2s;
	}

	.resource-card:hover {
		border-color: var(--theme-primary);
		background: var(--theme-surface-hover);
	}

	.resource-icon {
		font-size: 1.5rem;
		margin-bottom: 0.5rem;
	}

	.resource-title {
		font-weight: 600;
		color: var(--theme-text);
		margin-bottom: 0.25rem;
	}

	.resource-desc {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	/* Custom Domain CTA */
	.custom-domain-cta {
		background: linear-gradient(135deg, var(--theme-surface) 0%, var(--theme-surface-hover) 100%);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 2rem;
		text-align: center;
	}

	.cta-content h3 {
		font-size: 1.25rem;
		margin-bottom: 0.5rem;
		color: var(--theme-text);
	}

	.cta-content p {
		color: var(--theme-text-muted);
		margin-bottom: 1.25rem;
	}

	.cta-content strong {
		color: var(--theme-primary);
	}

	/* Buttons */
	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		border-radius: var(--theme-radius);
		font-weight: 600;
		font-size: 0.95rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
		text-decoration: none;
	}

	.btn-secondary {
		background: var(--theme-bg);
		color: var(--theme-text);
		border: 1px solid var(--theme-primary);
	}

	.btn-secondary:hover {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	@media (max-width: 480px) {
		.hero h1 {
			font-size: 1.75rem;
		}

		.links-grid,
		.resources-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
</style>
