<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		tierLabels,
		tierDetails,
		regionOptions,
		formattedPrice,
		yearlyPrice,
		formattedYearlyPrice,
		prevStep,
		goToStep
	} from '$lib/stores/onboarding.js';

	let billingPeriod = 'monthly';
	let isSubmitting = false;
	let submitError = '';

	onMount(() => {
		if (!$onboarding.bundle || !$onboarding.beaconName) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 4 }));
	});

	$: bundleMeta = bundleInfo[$onboarding.bundle] || {};
	$: tierMeta = tierDetails[$onboarding.tier] || {};
	$: tierLabel = tierLabels[$onboarding.tier] || '';
	$: regionMeta = regionOptions.find(r => r.id === $onboarding.region) || regionOptions[0];

	$: displayPrice = billingPeriod === 'yearly' ? $formattedYearlyPrice : $formattedPrice;
	$: displayPeriod = billingPeriod === 'yearly' ? '/year' : '/mo';
	$: monthlyEquivalent = billingPeriod === 'yearly'
		? `$${(($yearlyPrice / 100) / 12).toFixed(2)}/mo`
		: null;

	async function handleCheckout() {
		isSubmitting = true;
		submitError = '';

		try {
			const checkoutData = {
				bundle: $onboarding.bundle,
				tier: $onboarding.tier,
				period: billingPeriod,
				email: $onboarding.email,
				name: $onboarding.name,
				beacon_name: $onboarding.beaconName,
				region: $onboarding.region,
				additional_users: $onboarding.additionalUsers,
			};

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
			window.location.href = checkout_url;
		} catch (err) {
			submitError = err.message;
			isSubmitting = false;
		}
	}

	function handleBack() {
		prevStep();
		goto('/onboard/account');
	}

	function editStep(step) {
		goToStep(step);
		switch (step) {
			case 1: goto('/onboard'); break;
			case 2: goto('/onboard/plan'); break;
			case 3: goto('/onboard/account'); break;
		}
	}
</script>

<svelte:head>
	<title>Review Your Order - WOPR</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<span class="step-badge">Step 4 of 4</span>
		<h1>Review your order</h1>
		<p class="subtitle">Everything look good? Let's get your server set up!</p>
	</div>

	<div class="checkout-grid">
		<!-- Order summary -->
		<div class="order-summary">
			<h2>Your Setup</h2>

			<!-- Bundle -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Package</h3>
					<button class="edit-btn" on:click={() => editStep(1)}>Change</button>
				</div>
				<div class="section-content">
					<strong>{bundleMeta.name}</strong>
					<p class="muted">{bundleMeta.description}</p>
				</div>
			</div>

			<!-- Plan size -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Plan Size</h3>
					<button class="edit-btn" on:click={() => editStep(2)}>Change</button>
				</div>
				<div class="section-content">
					<div class="plan-line">
						<strong>{tierLabel}</strong>
						<span class="plan-detail">{tierMeta.storage} storage</span>
					</div>
					<p class="muted">{tierMeta.users} &middot; {tierMeta.backups}</p>
				</div>
			</div>

			<!-- Server location -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Server Location</h3>
					<button class="edit-btn" on:click={() => editStep(2)}>Change</button>
				</div>
				<div class="section-content">
					<span class="region-display">
						{regionMeta.flag} {regionMeta.name}
						{#if regionMeta.id !== 'auto'}
							<span class="muted">({regionMeta.description})</span>
						{/if}
					</span>
				</div>
			</div>

			<!-- Account -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Account</h3>
					<button class="edit-btn" on:click={() => editStep(3)}>Change</button>
				</div>
				<div class="section-content">
					<p><strong>{$onboarding.name}</strong></p>
					<p class="muted">{$onboarding.email}</p>
				</div>
			</div>

			<!-- Beacon -->
			<div class="summary-section">
				<div class="section-header">
					<h3>Your Address</h3>
					<button class="edit-btn" on:click={() => editStep(3)}>Change</button>
				</div>
				<div class="section-content">
					<p class="beacon-url">https://<strong>{$onboarding.beaconName}</strong>.wopr.systems</p>
				</div>
			</div>

			<!-- Users -->
			{#if $onboarding.additionalUsers.length > 0}
				<div class="summary-section">
					<div class="section-header">
						<h3>Team</h3>
						<button class="edit-btn" on:click={() => editStep(3)}>Change</button>
					</div>
					<div class="section-content">
						<p>{1 + $onboarding.additionalUsers.length} users total</p>
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
					That's just {monthlyEquivalent} &mdash; 2 months free!
				</p>
			{/if}

			<!-- What's included -->
			<div class="included">
				<h4>Everything included:</h4>
				<ul>
					<li>All your {bundleMeta.name} apps</li>
					<li>{tierMeta.storage} cloud storage</li>
					<li>Your own private server</li>
					<li>Automatic backups</li>
					<li>SSL security certificate</li>
					<li>24/7 uptime monitoring</li>
				</ul>
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
				Secure checkout powered by Stripe. Cancel anytime.
			</p>
		</div>
	</div>

	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">&larr;</span>
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
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
		margin: 0;
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

	.plan-line {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.plan-detail {
		font-size: 0.85rem;
		padding: 0.15rem 0.5rem;
		background: var(--theme-border);
		border-radius: var(--theme-radius);
	}

	.muted {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		margin-top: 0.25rem;
	}

	.region-display {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.beacon-url {
		font-family: monospace;
		background: var(--theme-bg);
		padding: 0.5rem 0.75rem;
		border-radius: var(--theme-radius);
		display: inline-block;
		font-size: 0.95rem;
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
		content: "\2713 ";
		color: var(--theme-success);
		font-weight: bold;
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
