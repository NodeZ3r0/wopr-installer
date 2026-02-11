<script>
	import '../../app.css';
	import { page } from '$app/stores';
	import { onboarding, canProceed, goToStep } from '$lib/stores/onboarding.js';
	import ThemeProvider from '$lib/components/ThemeProvider.svelte';

	const steps = [
		{ num: 1, label: 'Bundle', path: '/onboard' },
		{ num: 2, label: 'Account', path: '/onboard/account' },
		{ num: 3, label: 'Beacon', path: '/onboard/beacon' },
		{ num: 4, label: 'Users', path: '/onboard/users' },
		{ num: 5, label: 'Checkout', path: '/onboard/checkout' }
	];

	function getStepClass(stepNum) {
		if ($onboarding.currentStep === stepNum) return 'active';
		if ($onboarding.currentStep > stepNum) return 'completed';
		return '';
	}
</script>

<ThemeProvider>
<div class="onboard-layout">
	<header class="onboard-header">
		<div class="logo">
			<h1>WOPR</h1>
			<span class="tagline">Create Your Beacon</span>
		</div>

		<nav class="step-nav">
			{#each steps as step}
				<div class="step {getStepClass(step.num)}">
					<div class="step-number">
						{#if $onboarding.currentStep > step.num}
							<span class="check">&#10003;</span>
						{:else}
							{step.num}
						{/if}
					</div>
					<span class="step-label">{step.label}</span>
				</div>
				{#if step.num < steps.length}
					<div class="step-connector {$onboarding.currentStep > step.num ? 'completed' : ''}"></div>
				{/if}
			{/each}
		</nav>
	</header>

	<main class="onboard-content">
		<slot />
	</main>

	<footer class="onboard-footer">
		<p>Already have a Beacon? <a href="/login">Sign in</a></p>
	</footer>
</div>
</ThemeProvider>

<style>
	.onboard-layout {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		background: var(--theme-bg);
	}

	.onboard-header {
		background: var(--theme-surface);
		border-bottom: 1px solid var(--theme-border);
		padding: 1.5rem 2rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.logo {
		display: flex;
		align-items: baseline;
		gap: 1rem;
	}

	.logo h1 {
		font-size: 1.75rem;
		color: var(--theme-primary);
		margin: 0;
	}

	.tagline {
		font-size: 1rem;
		color: var(--theme-text-muted);
	}

	.step-nav {
		display: flex;
		align-items: center;
		gap: 0;
	}

	.step {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		opacity: 0.5;
		transition: opacity 0.2s;
	}

	.step.active,
	.step.completed {
		opacity: 1;
	}

	.step-number {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--theme-border);
		color: var(--theme-text-muted);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.85rem;
		font-weight: 600;
		transition: all 0.2s;
	}

	.step.active .step-number {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	.step.completed .step-number {
		background: var(--theme-success);
		color: #fff;
	}

	.check {
		font-size: 0.9rem;
	}

	.step-label {
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--theme-text-muted);
	}

	.step.active .step-label {
		color: var(--theme-text);
	}

	.step.completed .step-label {
		color: var(--theme-text);
	}

	.step-connector {
		width: 40px;
		height: 2px;
		background: var(--theme-border);
		transition: background 0.2s;
	}

	.step-connector.completed {
		background: var(--theme-success);
	}

	.onboard-content {
		flex-grow: 1;
		padding: 2rem;
		max-width: 900px;
		margin: 0 auto;
		width: 100%;
	}

	.onboard-footer {
		padding: 1.5rem;
		text-align: center;
		border-top: 1px solid var(--theme-border);
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.onboard-footer a {
		color: var(--theme-primary);
		font-weight: 500;
	}

	@media (max-width: 768px) {
		.onboard-header {
			flex-direction: column;
			align-items: flex-start;
		}

		.step-nav {
			width: 100%;
			overflow-x: auto;
			padding-bottom: 0.5rem;
		}

		.step-label {
			display: none;
		}

		.step-connector {
			width: 24px;
		}

		.onboard-content {
			padding: 1rem;
		}
	}
</style>
