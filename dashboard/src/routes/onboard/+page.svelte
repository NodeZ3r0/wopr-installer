<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		bundlePricing,
		canProceed,
		setBundle,
		nextStep,
		formatPrice
	} from '$lib/stores/onboarding.js';

	import { page } from '$app/stores';

	onMount(() => {
		onboarding.update(o => ({ ...o, currentStep: 1 }));

		const bundleParam = $page.url.searchParams.get('bundle');
		if (bundleParam && bundleInfo[bundleParam]) {
			setBundle(bundleParam);
		}
	});

	let selectedType = 'sovereign';

	$: completePackages = Object.entries(bundleInfo)
		.filter(([_, info]) => info.type === 'sovereign')
		.map(([id, info]) => ({ id, ...info, pricing: bundlePricing[id] }));

	$: builtForYou = Object.entries(bundleInfo)
		.filter(([_, info]) => info.type === 'micro')
		.map(([id, info]) => ({ id, ...info, pricing: bundlePricing[id] }));

	$: displayedBundles = selectedType === 'sovereign' ? completePackages : builtForYou;

	function selectBundle(bundleId) {
		setBundle(bundleId, $onboarding.tier);
	}

	function handleContinue() {
		if ($canProceed) {
			nextStep();
			goto('/onboard/plan');
		}
	}
</script>

<svelte:head>
	<title>What Do You Need? - WOPR</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<span class="step-badge">Step 1 of 4</span>
		<h1>What do you need?</h1>
		<p class="subtitle">Pick the apps that fit your life. You can always change later.</p>
	</div>

	<!-- Category tabs -->
	<div class="type-tabs">
		<button
			class="type-tab {selectedType === 'sovereign' ? 'active' : ''}"
			on:click={() => (selectedType = 'sovereign')}
		>
			Complete Packages
			<span class="tab-hint">Everything in one place</span>
		</button>
		<button
			class="type-tab {selectedType === 'micro' ? 'active' : ''}"
			on:click={() => (selectedType = 'micro')}
		>
			Built for You
			<span class="tab-hint">Tools for what you do</span>
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
						Starting at {formatPrice(bundle.pricing.t1)}<span class="period">/mo</span>
					</div>
				</div>
				<p class="bundle-description">{bundle.description}</p>
				{#if bundle.maxUsers > 1}
					<span class="user-badge">
						{bundle.maxUsers === -1 ? 'Unlimited' : `Up to ${bundle.maxUsers}`} users
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

	<!-- Bottom bar -->
	{#if $onboarding.bundle}
		<div class="summary-bar">
			<div class="summary-info">
				<strong>{bundleInfo[$onboarding.bundle].name}</strong>
				<span class="summary-price">Starting at {formatPrice(bundlePricing[$onboarding.bundle].t1)}/mo</span>
			</div>
			<button class="btn btn-primary" on:click={handleContinue} disabled={!$canProceed}>
				Pick Your Plan Size
				<span class="arrow">&rarr;</span>
			</button>
		</div>
	{/if}
</div>

<style>
	.step-container {
		animation: fadeIn 0.3s ease;
		padding-bottom: 6rem;
	}

	@keyframes fadeIn {
		from { opacity: 0; transform: translateY(10px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.step-header {
		text-align: center;
		margin-bottom: 2rem;
	}

	.step-badge {
		display: inline-block;
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--theme-primary);
		background: var(--theme-primary-subtle);
		padding: 0.3rem 0.75rem;
		border-radius: var(--theme-radius);
		margin-bottom: 0.75rem;
	}

	.step-header h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.subtitle {
		color: var(--theme-text-muted);
		font-size: 1.1rem;
	}

	/* Category tabs */
	.type-tabs {
		display: flex;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.type-tab {
		flex: 1;
		padding: 1rem 1.5rem;
		border: 2px solid var(--theme-border);
		background: var(--theme-surface);
		color: var(--theme-text-muted);
		font-size: 1.1rem;
		font-weight: 600;
		cursor: pointer;
		border-radius: var(--theme-radius);
		transition: all 0.2s;
		text-align: center;
	}

	.type-tab:hover {
		border-color: var(--theme-primary);
		color: var(--theme-text);
	}

	.type-tab.active {
		border-color: var(--theme-primary);
		background: var(--theme-primary-subtle);
		color: var(--theme-primary);
	}

	.tab-hint {
		display: block;
		font-size: 0.8rem;
		font-weight: 400;
		margin-top: 0.25rem;
		opacity: 0.7;
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
		font-size: 1.1rem;
		font-weight: 600;
		margin: 0;
	}

	.bundle-price {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--theme-primary);
		white-space: nowrap;
	}

	.period {
		font-size: 0.75rem;
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

	.summary-price {
		font-size: 1rem;
		font-weight: 600;
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
		.type-tabs {
			flex-direction: column;
		}

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
