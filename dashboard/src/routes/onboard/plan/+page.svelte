<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		bundlePricing,
		tierDetails,
		regionOptions,
		formattedPrice,
		canProceed,
		nextStep,
		prevStep,
		setRegion,
		formatPrice
	} from '$lib/stores/onboarding.js';

	let showRegionPicker = false;
	let detectedRegion = null;

	onMount(() => {
		if (!$onboarding.bundle) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 2 }));

		// Auto-detect region from IP
		detectRegion();
	});

	async function detectRegion() {
		try {
			const resp = await fetch('https://ipapi.co/json/');
			if (resp.ok) {
				const data = await resp.json();
				// Map continent/country to our regions
				if (data.continent_code === 'EU' || data.continent_code === 'AF') {
					detectedRegion = 'eu-west';
				} else {
					detectedRegion = 'us-east';
				}
			}
		} catch {
			detectedRegion = 'us-east'; // Default fallback
		}
	}

	$: pricing = bundlePricing[$onboarding.bundle] || {};
	$: bundleMeta = bundleInfo[$onboarding.bundle] || {};

	function selectTier(tier) {
		onboarding.update(o => ({ ...o, tier }));
	}

	function selectRegion(regionId) {
		setRegion(regionId);
	}

	function handleBack() {
		prevStep();
		goto('/onboard');
	}

	function handleContinue() {
		if ($canProceed) {
			nextStep();
			goto('/onboard/account');
		}
	}

	$: autoRegionLabel = detectedRegion
		? regionOptions.find(r => r.id === detectedRegion)?.name || 'your area'
		: 'your area';
</script>

<svelte:head>
	<title>Pick Your Plan Size - WOPR</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<span class="step-badge">Step 2 of 4</span>
		<h1>Pick your plan size</h1>
		<p class="subtitle">
			How much space do you need for <strong>{bundleMeta.name}</strong>?
			You can upgrade anytime.
		</p>
	</div>

	<!-- Plan size cards -->
	<div class="plan-grid">
		{#each Object.entries(tierDetails) as [tierId, tier]}
			{@const price = pricing[tierId] || 0}
			<button
				class="plan-card {$onboarding.tier === tierId ? 'selected' : ''} {tier.popular ? 'popular' : ''}"
				on:click={() => selectTier(tierId)}
			>
				{#if tier.popular}
					<div class="popular-badge">Most Popular</div>
				{/if}

				<h3 class="plan-name">{tier.name}</h3>
				<p class="plan-tagline">{tier.description}</p>

				<div class="plan-price">
					<span class="price-amount">{formatPrice(price)}</span>
					<span class="price-period">/mo</span>
				</div>

				<ul class="plan-features">
					<li>{tier.storage} storage</li>
					<li class="feature-context">{tier.storageContext}</li>
					<li>{tier.users}</li>
					<li>{tier.backups}</li>
				</ul>

				{#if $onboarding.tier === tierId}
					<div class="selected-check">&#10003;</div>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Region selector -->
	<div class="region-section">
		<h2>Server location</h2>

		{#if !showRegionPicker}
			<div class="region-auto">
				<div class="region-auto-info">
					<span class="region-flag">🌐</span>
					<div>
						<strong>Automatic</strong>
						<p>We'll set up your server closest to {autoRegionLabel}</p>
					</div>
				</div>
				<button class="region-toggle" on:click={() => (showRegionPicker = true)}>
					Choose a different location
				</button>
			</div>
		{:else}
			<div class="region-grid">
				{#each regionOptions as region}
					<button
						class="region-card {$onboarding.region === region.id ? 'selected' : ''}"
						on:click={() => selectRegion(region.id)}
					>
						<span class="region-flag">{region.flag}</span>
						<div>
							<strong>{region.name}</strong>
							<p>{region.description}</p>
						</div>
						{#if $onboarding.region === region.id}
							<span class="region-check">&#10003;</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Summary + nav -->
	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">&larr;</span>
			Back
		</button>

		<div class="action-summary">
			<span class="action-bundle">{bundleMeta.name}</span>
			<span class="action-tier">{tierDetails[$onboarding.tier]?.name}</span>
			<span class="action-price">{$formattedPrice}/mo</span>
		</div>

		<button class="btn btn-primary" on:click={handleContinue} disabled={!$canProceed}>
			Create Your Account
			<span class="arrow">&rarr;</span>
		</button>
	</div>
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

	/* Plan grid */
	.plan-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1.25rem;
		margin-bottom: 2.5rem;
	}

	.plan-card {
		background: var(--theme-surface);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
		text-align: center;
		cursor: pointer;
		transition: all 0.2s;
		position: relative;
	}

	.plan-card:hover {
		border-color: var(--theme-primary);
		transform: translateY(-3px);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	}

	.plan-card.selected {
		border-color: var(--theme-primary);
		background: var(--theme-surface-hover);
	}

	.plan-card.popular {
		border-color: var(--theme-primary);
	}

	.popular-badge {
		position: absolute;
		top: -0.75rem;
		left: 50%;
		transform: translateX(-50%);
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 0.25rem 0.75rem;
		border-radius: var(--theme-radius);
		white-space: nowrap;
	}

	.plan-name {
		font-size: 1.5rem;
		font-weight: 700;
		margin: 0.5rem 0 0.25rem;
	}

	.plan-tagline {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin-bottom: 1rem;
	}

	.plan-price {
		margin-bottom: 1.25rem;
	}

	.price-amount {
		font-size: 2rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.price-period {
		font-size: 1rem;
		color: var(--theme-text-muted);
	}

	.plan-features {
		list-style: none;
		padding: 0;
		margin: 0;
		text-align: left;
	}

	.plan-features li {
		padding: 0.4rem 0;
		font-size: 0.9rem;
		border-bottom: 1px solid var(--theme-border);
	}

	.plan-features li:last-child {
		border-bottom: none;
	}

	.plan-features li::before {
		content: "✓ ";
		color: var(--theme-success);
		font-weight: bold;
	}

	.plan-features .feature-context {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		border-bottom: none;
		padding-top: 0;
		padding-left: 1rem;
	}

	.plan-features .feature-context::before {
		content: "";
	}

	.selected-check {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		width: 28px;
		height: 28px;
		background: var(--theme-success);
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.9rem;
		font-weight: bold;
	}

	/* Region section */
	.region-section {
		margin-bottom: 2rem;
	}

	.region-section h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
	}

	.region-auto {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.25rem;
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.region-auto-info {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.region-auto-info p {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0.15rem 0 0;
	}

	.region-flag {
		font-size: 1.5rem;
	}

	.region-toggle {
		background: none;
		border: none;
		color: var(--theme-primary);
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		text-decoration: underline;
	}

	.region-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.75rem;
	}

	.region-card {
		background: var(--theme-surface);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		cursor: pointer;
		transition: all 0.2s;
		text-align: left;
		position: relative;
	}

	.region-card:hover {
		border-color: var(--theme-primary);
	}

	.region-card.selected {
		border-color: var(--theme-primary);
		background: var(--theme-surface-hover);
	}

	.region-card p {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		margin: 0.1rem 0 0;
	}

	.region-check {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		color: var(--theme-success);
		font-weight: bold;
	}

	/* Actions */
	.step-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 2rem;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.action-summary {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		justify-content: center;
	}

	.action-bundle {
		font-weight: 600;
	}

	.action-tier {
		font-size: 0.85rem;
		padding: 0.2rem 0.6rem;
		background: var(--theme-border);
		border-radius: var(--theme-radius);
	}

	.action-price {
		font-weight: 700;
		color: var(--theme-primary);
		font-size: 1.1rem;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.875rem 1.5rem;
		border-radius: var(--theme-radius);
		font-weight: 600;
		font-size: 1rem;
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

	.btn-secondary {
		background: var(--theme-surface);
		color: var(--theme-text);
		border: 1px solid var(--theme-border);
	}

	.btn-secondary:hover {
		background: var(--theme-surface-hover);
	}

	.arrow {
		font-size: 1rem;
	}

	@media (max-width: 768px) {
		.plan-grid {
			grid-template-columns: 1fr;
		}

		.step-actions {
			flex-direction: column;
		}

		.btn {
			width: 100%;
			justify-content: center;
		}
	}
</style>
