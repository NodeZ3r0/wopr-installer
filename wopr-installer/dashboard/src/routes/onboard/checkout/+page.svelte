<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		tierInfo,
		providerOptions,
		selectedPrice,
		formattedPrice,
		yearlyPrice,
		formattedYearlyPrice,
		prevStep,
		goToStep
	} from '$lib/stores/onboarding.js';

	let billingPeriod = 'monthly'; // 'monthly' or 'yearly'
	let isSubmitting = false;
	let submitError = '';

	onMount(() => {
		// Redirect if no bundle selected
		if (!$onboarding.bundle || !$onboarding.beaconName) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 5 }));
	});

	$: bundleMeta = bundleInfo[$onboarding.bundle] || {};
	$: tierMeta = tierInfo[$onboarding.tier] || {};
	$: providerMeta = providerOptions.find(p => p.id === $onboarding.provider) || {};

	$: displayPrice = billingPeriod === 'yearly' ? $formattedYearlyPrice : $formattedPrice;
	$: displayPeriod = billingPeriod === 'yearly' ? '/year' : '/mo';
	$: monthlyEquivalent = billingPeriod === 'yearly'
		? `$${(($yearlyPrice / 100) / 12).toFixed(2)}/mo`
		: null;

	async function handleCheckout() {
		isSubmitting = true;
		submitError = '';

		try {
			// Build checkout request
			const checkoutData = {
				bundle: $onboarding.bundle,
				tier: $onboarding.tier,
				period: billingPeriod,
				email: $onboarding.email,
				name: $onboarding.name,
				beacon_name: $onboarding.beaconName,
				provider: $onboarding.provider,
				additional_users: $onboarding.additionalUsers,
			};

			// Call API to create Stripe checkout session
			const response = await fetch('/api/v1/onboard/create-checkout', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(checkoutData),
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Failed to create checkout session');
			}

			const { checkout_url } = await response.json();

			// Redirect to Stripe
			window.location.href = checkout_url;

		} catch (err) {
			submitError = err.message;
			isSubmitting = false;
		}
	}

	function handleBack() {
		prevStep();
		if (bundleMeta.maxUsers > 1) {
			goto('/onboard/users');
		} else {
			goto('/onboard/beacon');
		}
	}

	function editStep(step) {
		goToStep(step);
		switch (step) {
			case 1: goto('/onboard'); break;
			case 2: goto('/onboard/account'); break;
			case 3: goto('/onboard/beacon'); break;
			case 4: goto('/onboard/users'); break;
		}
	}
</script>

<svelte:head>
	<title>Review Your Order - WOPR Onboarding</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<h1>Review Your Order</h1>
		<p class="subtitle">Everything look good? Let's set up your Beacon!</p>
	</div>

	<div class="checkout-grid">
		<!-- Order summary -->
		<div class="order-summary">
			<h2>Order Summary</h2>

			<!-- Bundle -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Bundle</h3>
					<button class="edit-btn" on:click={() => editStep(1)}>Edit</button>
				</div>
				<div class="section-content">
					<div class="bundle-line">
						<span class="bundle-name">{bundleMeta.name}</span>
						<span class="bundle-tier">{tierMeta.storage}</span>
					</div>
					<p class="bundle-desc">{bundleMeta.description}</p>
				</div>
			</div>

			<!-- Account -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Account</h3>
					<button class="edit-btn" on:click={() => editStep(2)}>Edit</button>
				</div>
				<div class="section-content">
					<p><strong>{$onboarding.name}</strong></p>
					<p class="muted">{$onboarding.email}</p>
				</div>
			</div>

			<!-- Beacon -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Beacon</h3>
					<button class="edit-btn" on:click={() => editStep(3)}>Edit</button>
				</div>
				<div class="section-content">
					<p class="beacon-url">https://<strong>{$onboarding.beaconName}</strong>.wopr.systems</p>
					<p class="muted">Hosted on {providerMeta.name}</p>
				</div>
			</div>

			<!-- Users (if applicable) -->
			{#if $onboarding.additionalUsers.length > 0}
				<div class="summary-section">
					<div class="section-header">
						<h3>Team Members</h3>
						<button class="edit-btn" on:click={() => editStep(4)}>Edit</button>
					</div>
					<div class="section-content">
						<p>{1 + $onboarding.additionalUsers.length} total users</p>
						<ul class="user-list">
							<li>{$onboarding.name} (Admin)</li>
							{#each $onboarding.additionalUsers as user}
								<li>{user.name}</li>
							{/each}
						</ul>
					</div>
				</div>
			{/if}
		</div>

		<!-- Payment card -->
		<div class="payment-card">
			<h2>Payment</h2>

			<!-- Billing period toggle -->
			<div class="billing-toggle">
				<button
					class="toggle-btn {billingPeriod === 'monthly' ? 'active' : ''}"
					on:click={() => (billingPeriod = 'monthly')}
				>
					Monthly
				</button>
				<button
					class="toggle-btn {billingPeriod === 'yearly' ? 'active' : ''}"
					on:click={() => (billingPeriod = 'yearly')}
				>
					Yearly
					<span class="save-badge">Save 17%</span>
				</button>
			</div>

			<!-- Price display -->
			<div class="price-display">
				<span class="price">{displayPrice}</span>
				<span class="period">{displayPeriod}</span>
			</div>

			{#if monthlyEquivalent}
				<p class="monthly-equivalent">
					That's just {monthlyEquivalent} - 2 months free!
				</p>
			{/if}

			<!-- What's included -->
			<div class="included">
				<h4>What's included:</h4>
				<ul>
					<li>Full access to all {bundleMeta.name} apps</li>
					<li>{tierMeta.storage} cloud storage</li>
					<li>Automatic backups</li>
					<li>SSL certificate included</li>
					<li>24/7 uptime monitoring</li>
				</ul>
			</div>

			<!-- Server cost note -->
			<div class="server-note">
				<strong>Note:</strong> VPS hosting ({providerMeta.priceRange}) is billed separately
				by {providerMeta.name}. We'll help you set it up after checkout.
			</div>

			<!-- Submit button -->
			{#if submitError}
				<div class="error-message">{submitError}</div>
			{/if}

			<button
				class="btn btn-checkout"
				on:click={handleCheckout}
				disabled={isSubmitting}
			>
				{#if isSubmitting}
					Processing...
				{:else}
					Proceed to Payment
				{/if}
			</button>

			<p class="secure-note">
				Secure checkout powered by Stripe
			</p>
		</div>
	</div>

	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">←</span>
			Back
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

	.step-header h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.subtitle {
		color: var(--theme-text-muted);
		font-size: 1.1rem;
	}

	.checkout-grid {
		display: grid;
		grid-template-columns: 1fr 400px;
		gap: 2rem;
		align-items: start;
	}

	/* Order summary */
	.order-summary {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
	}

	.order-summary h2 {
		font-size: 1.25rem;
		margin-bottom: 1.25rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--theme-border);
	}

	.summary-section {
		padding: 1rem 0;
		border-bottom: 1px solid var(--theme-border);
	}

	.summary-section:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}

	.section-header h3 {
		font-size: 0.9rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
	}

	.edit-btn {
		background: none;
		border: none;
		color: var(--theme-primary);
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
	}

	.edit-btn:hover {
		text-decoration: underline;
	}

	.bundle-line {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.bundle-name {
		font-weight: 600;
	}

	.bundle-tier {
		font-size: 0.8rem;
		padding: 0.2rem 0.5rem;
		background: var(--theme-border);
		border-radius: var(--theme-radius);
	}

	.bundle-desc {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
		margin-top: 0.5rem;
	}

	.muted {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.beacon-url {
		font-family: monospace;
		background: var(--theme-bg);
		padding: 0.5rem 0.75rem;
		border-radius: var(--theme-radius);
		display: inline-block;
	}

	.user-list {
		margin-top: 0.5rem;
		padding-left: 1.25rem;
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	/* Payment card */
	.payment-card {
		background: var(--theme-surface);
		border: 2px solid var(--theme-primary);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
		position: sticky;
		top: 2rem;
	}

	.payment-card h2 {
		font-size: 1.25rem;
		margin-bottom: 1.25rem;
	}

	.billing-toggle {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1.5rem;
	}

	.toggle-btn {
		flex: 1;
		padding: 0.75rem;
		background: var(--theme-bg);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius);
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}

	.toggle-btn:hover {
		border-color: var(--theme-primary);
	}

	.toggle-btn.active {
		background: var(--theme-primary-subtle);
		border-color: var(--theme-primary);
		color: var(--theme-primary);
	}

	.save-badge {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.15rem 0.4rem;
		background: var(--theme-success);
		color: #fff;
		border-radius: var(--theme-radius);
	}

	.price-display {
		text-align: center;
		margin-bottom: 0.5rem;
	}

	.price {
		font-size: 2.5rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.period {
		font-size: 1.25rem;
		color: var(--theme-text-muted);
	}

	.monthly-equivalent {
		text-align: center;
		color: var(--theme-success);
		font-weight: 500;
		margin-bottom: 1.5rem;
	}

	.included {
		margin-bottom: 1.5rem;
	}

	.included h4 {
		font-size: 0.9rem;
		margin-bottom: 0.5rem;
	}

	.included ul {
		list-style: none;
		padding: 0;
	}

	.included li {
		padding: 0.35rem 0;
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.included li::before {
		content: "✓ ";
		color: var(--theme-success);
		font-weight: bold;
	}

	.server-note {
		background: var(--theme-bg);
		padding: 0.75rem 1rem;
		border-radius: var(--theme-radius);
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin-bottom: 1.5rem;
	}

	.error-message {
		background: var(--theme-error-subtle);
		color: var(--theme-error);
		padding: 0.75rem 1rem;
		border-radius: var(--theme-radius);
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}

	.btn-checkout {
		width: 100%;
		padding: 1rem;
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
		border: none;
		border-radius: var(--theme-radius);
		font-size: 1.1rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.2s;
	}

	.btn-checkout:hover:not(:disabled) {
		background: var(--theme-primary-hover);
	}

	.btn-checkout:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.secure-note {
		text-align: center;
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		margin-top: 0.75rem;
	}

	/* Actions */
	.step-actions {
		margin-top: 2rem;
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

	@media (max-width: 800px) {
		.checkout-grid {
			grid-template-columns: 1fr;
		}

		.payment-card {
			position: static;
		}
	}
</style>
