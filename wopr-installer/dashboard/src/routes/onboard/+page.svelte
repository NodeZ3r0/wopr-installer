<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		bundlePricing,
		tierInfo,
		selectedPrice,
		formattedPrice,
		canProceed,
		setBundle,
		nextStep
	} from '$lib/stores/onboarding.js';

	// Get bundles from URL params if passed from join page
	import { page } from '$app/stores';

	onMount(() => {
		// Set step to 1 when arriving at this page
		onboarding.update(o => ({ ...o, currentStep: 1 }));

		// Check for URL params from join page
		const bundleParam = $page.url.searchParams.get('bundle');
		const tierParam = $page.url.searchParams.get('tier');

		if (bundleParam && bundleInfo[bundleParam]) {
			setBundle(bundleParam, tierParam || 't1');
		}
	});

	let selectedType = 'sovereign'; // 'sovereign' or 'micro'

	$: sovereignSuites = Object.entries(bundleInfo)
		.filter(([_, info]) => info.type === 'sovereign')
		.map(([id, info]) => ({ id, ...info, pricing: bundlePricing[id] }));

	$: microBundles = Object.entries(bundleInfo)
		.filter(([_, info]) => info.type === 'micro')
		.map(([id, info]) => ({ id, ...info, pricing: bundlePricing[id] }));

	$: displayedBundles = selectedType === 'sovereign' ? sovereignSuites : microBundles;

	function selectBundle(bundleId) {
		setBundle(bundleId, $onboarding.tier);
	}

	function selectTier(tier) {
		onboarding.update(o => ({ ...o, tier }));
	}

	function formatPrice(cents) {
		if (cents === 0) return 'Custom';
		return `$${(cents / 100).toFixed(2)}`;
	}

	function handleContinue() {
		if ($canProceed) {
			nextStep();
			goto('/onboard/account');
		}
	}
</script>

<svelte:head>
	<title>Choose Your Bundle - WOPR Onboarding</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<h1>Choose Your Bundle</h1>
		<p class="subtitle">Select the perfect combination of apps for your needs</p>
	</div>

	<!-- Tier selector -->
	<div class="tier-selector">
		<span class="tier-label">Storage Tier:</span>
		<div class="tier-buttons">
			{#each Object.entries(tierInfo) as [tierId, tier]}
				<button
					class="tier-btn {$onboarding.tier === tierId ? 'active' : ''}"
					on:click={() => selectTier(tierId)}
				>
					<span class="tier-name">{tier.storage}</span>
				</button>
			{/each}
		</div>
	</div>

	<!-- Type tabs -->
	<div class="type-tabs">
		<button
			class="type-tab {selectedType === 'sovereign' ? 'active' : ''}"
			on:click={() => (selectedType = 'sovereign')}
		>
			Sovereign Suites
			<span class="tab-count">{sovereignSuites.length}</span>
		</button>
		<button
			class="type-tab {selectedType === 'micro' ? 'active' : ''}"
			on:click={() => (selectedType = 'micro')}
		>
			Micro-Bundles
			<span class="tab-count">{microBundles.length}</span>
		</button>
	</div>

	<!-- Bundle grid -->
	<div class="bundle-grid">
		{#each displayedBundles as bundle}
			<button
				class="bundle-card {$onboarding.bundle === bundle.id ? 'selected' : ''}"
				on:click={() => selectBundle(bundle.id)}
			>
				<div class="bundle-header">
					<h3>{bundle.name}</h3>
					<div class="bundle-price">
						{formatPrice(bundle.pricing[$onboarding.tier])}<span class="period">/mo</span>
					</div>
				</div>
				<p class="bundle-description">{bundle.description}</p>
				{#if bundle.maxUsers > 1}
					<span class="user-badge">
						{bundle.maxUsers === -1 ? 'Unlimited' : bundle.maxUsers} users
					</span>
				{/if}
				{#if $onboarding.bundle === bundle.id}
					<div class="selected-indicator">
						<span>&#10003;</span> Selected
					</div>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Summary bar -->
	{#if $onboarding.bundle}
		<div class="summary-bar">
			<div class="summary-info">
				<strong>{bundleInfo[$onboarding.bundle].name}</strong>
				<span class="summary-tier">{tierInfo[$onboarding.tier].storage}</span>
				<span class="summary-price">{$formattedPrice}/mo</span>
			</div>
			<button class="btn btn-primary" on:click={handleContinue} disabled={!$canProceed}>
				Continue
				<span class="arrow">→</span>
			</button>
		</div>
	{/if}
</div>

<style>
	.step-container {
		animation: fadeIn 0.3s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; transform: translateY(10px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.step-header {
		text-align: center;
		margin-bottom: 2rem;
	}

	.step-header h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.subtitle {
		color: var(--theme-text-muted);
		font-size: 1.1rem;
	}

	/* Tier selector */
	.tier-selector {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
	}

	.tier-label {
		color: var(--theme-text-muted);
		font-weight: 500;
	}

	.tier-buttons {
		display: flex;
		gap: 0.5rem;
		background: var(--theme-surface);
		padding: 0.25rem;
		border-radius: var(--theme-radius);
		border: 1px solid var(--theme-border);
	}

	.tier-btn {
		padding: 0.5rem 1.25rem;
		border: none;
		background: transparent;
		color: var(--theme-text-muted);
		border-radius: calc(var(--theme-radius) - 2px);
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.tier-btn:hover {
		color: var(--theme-text);
	}

	.tier-btn.active {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	/* Type tabs */
	.type-tabs {
		display: flex;
		gap: 1rem;
		margin-bottom: 1.5rem;
		border-bottom: 1px solid var(--theme-border);
	}

	.type-tab {
		padding: 0.75rem 1.5rem;
		border: none;
		background: transparent;
		color: var(--theme-text-muted);
		font-size: 1rem;
		font-weight: 500;
		cursor: pointer;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		transition: all 0.2s;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.type-tab:hover {
		color: var(--theme-text);
	}

	.type-tab.active {
		color: var(--theme-primary);
		border-bottom-color: var(--theme-primary);
	}

	.tab-count {
		background: var(--theme-surface);
		padding: 0.15rem 0.5rem;
		border-radius: var(--theme-radius);
		font-size: 0.8rem;
	}

	.type-tab.active .tab-count {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	/* Bundle grid */
	.bundle-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
		margin-bottom: 2rem;
	}

	.bundle-card {
		background: var(--theme-surface);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.25rem;
		text-align: left;
		cursor: pointer;
		transition: all 0.2s;
		position: relative;
	}

	.bundle-card:hover {
		border-color: var(--theme-primary);
		transform: translateY(-2px);
	}

	.bundle-card.selected {
		border-color: var(--theme-primary);
		background: var(--theme-surface-hover);
	}

	.bundle-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.bundle-header h3 {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}

	.bundle-price {
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--theme-primary);
		white-space: nowrap;
	}

	.period {
		font-size: 0.8rem;
		font-weight: 400;
		color: var(--theme-text-muted);
	}

	.bundle-description {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.4;
	}

	.user-badge {
		display: inline-block;
		margin-top: 0.75rem;
		padding: 0.25rem 0.75rem;
		background: var(--theme-primary-subtle);
		color: var(--theme-primary);
		font-size: 0.75rem;
		font-weight: 600;
		border-radius: var(--theme-radius);
	}

	.selected-indicator {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		background: var(--theme-success);
		color: #fff;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.25rem 0.5rem;
		border-radius: var(--theme-radius);
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	/* Summary bar */
	.summary-bar {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: var(--theme-surface);
		border-top: 1px solid var(--theme-border);
		padding: 1rem 2rem;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
		z-index: 100;
	}

	.summary-info {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.summary-tier {
		color: var(--theme-text-muted);
		padding: 0.25rem 0.75rem;
		background: var(--theme-border);
		border-radius: var(--theme-radius);
		font-size: 0.85rem;
	}

	.summary-price {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		border-radius: var(--theme-radius);
		font-weight: 600;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.btn-primary {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	.btn-primary:hover:not(:disabled) {
		background: var(--theme-primary-hover);
	}

	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.arrow {
		font-size: 1.1rem;
	}

	@media (max-width: 640px) {
		.bundle-grid {
			grid-template-columns: 1fr;
		}

		.summary-bar {
			flex-direction: column;
			text-align: center;
		}

		.summary-info {
			justify-content: center;
		}
	}
</style>
