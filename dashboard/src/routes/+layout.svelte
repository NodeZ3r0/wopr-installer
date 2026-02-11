<script>
	import '../app.css';
	import { page } from '$app/stores';
	import { user } from '$lib/stores.js';
	import ThemeProvider from '$lib/components/ThemeProvider.svelte';

	const navItems = [
		{ href: '/', label: 'Home', icon: '⌂' },
		{ href: '/modules', label: 'Modules', icon: '◫' },
		{ href: '/trials', label: 'Trials', icon: '◐' },
		{ href: '/billing', label: 'Billing', icon: '$' },
		{ href: '/settings', label: 'Settings', icon: '⚙' }
	];
</script>

<ThemeProvider>
<div class="layout">
	<nav class="sidebar">
		<div class="logo">
			<h1>WOPR</h1>
			<span class="tagline">Sovereign Suite</span>
		</div>

		<ul class="nav-items">
			{#each navItems as item}
				<li>
					<a
						href={item.href}
						class:active={$page.url.pathname === item.href}
					>
						<span class="icon">{item.icon}</span>
						{item.label}
					</a>
				</li>
			{/each}
		</ul>

		<div class="user-info">
			{#if $user.username}
				<span class="username">{$user.username}</span>
				<span class="email text-muted">{$user.email}</span>
			{/if}
		</div>
	</nav>

	<main class="content">
		<slot />
	</main>
</div>
</ThemeProvider>

<style>
	.layout {
		display: flex;
		min-height: 100vh;
	}

	.sidebar {
		width: 240px;
		background: var(--color-surface);
		border-right: 1px solid var(--color-border);
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
	}

	.logo {
		margin-bottom: 2rem;
	}

	.logo h1 {
		font-size: 1.75rem;
		color: var(--color-primary);
		margin-bottom: 0.25rem;
	}

	.tagline {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.nav-items {
		list-style: none;
		flex-grow: 1;
	}

	.nav-items li {
		margin-bottom: 0.5rem;
	}

	.nav-items a {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		color: var(--color-text);
		transition: all 0.2s;
	}

	.nav-items a:hover {
		background: var(--color-surface-hover);
	}

	.nav-items a.active {
		background: var(--color-primary);
		color: #000;
	}

	.nav-items .icon {
		font-size: 1.1rem;
	}

	.user-info {
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.username {
		font-weight: 500;
	}

	.email {
		font-size: 0.8rem;
	}

	.content {
		flex-grow: 1;
		padding: 2rem;
		overflow-y: auto;
	}

	@media (max-width: 768px) {
		.layout {
			flex-direction: column;
		}

		.sidebar {
			width: 100%;
			padding: 1rem;
		}

		.nav-items {
			display: flex;
			gap: 0.5rem;
			overflow-x: auto;
		}

		.nav-items li {
			margin-bottom: 0;
		}
	}
</style>
