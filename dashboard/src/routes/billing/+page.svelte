<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let subscription = null;
	let plans = [];
	let invoices = [];
	let usage = null;
	let loading = true;
	let error = null;

	// Modal states
	let showUpgradeModal = false;
	let showCancelModal = false;
	let selectedPlan = null;
	let cancelReason = '';
	let cancelFeedback = '';
	let processingAction = false;

	onMount(async () => {
		// Check for query params (after upgrade/payment update)
		const upgradeStatus = $page.url.searchParams.get('upgrade');
		const paymentStatus = $page.url.searchParams.get('payment_updated');

		if (upgradeStatus === 'success') {
			// Show success toast
		}

		await loadBillingData();
	});

	async function loadBillingData() {
		loading = true;
		error = null;

		try {
			const [subRes, plansRes, invoicesRes, usageRes] = await Promise.all([
				fetch('/api/v1/subscription'),
				fetch('/api/v1/subscription/plans'),
				fetch('/api/v1/subscription/invoices?limit=5'),
				fetch('/api/v1/subscription/usage'),
			]);

			if (subRes.ok) subscription = await subRes.json();
			if (plansRes.ok) {
				const data = await plansRes.json();
				plans = data.plans || [];
			}
			if (invoicesRes.ok) {
				const data = await invoicesRes.json();
				invoices = data.invoices || [];
			}
			if (usageRes.ok) usage = await usageRes.json();

		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	function formatCurrency(cents) {
		return (cents / 100).toFixed(2);
	}

	function formatDate(dateString) {
		if (!dateString) return 'N/A';
		const date = new Date(dateString);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		});
	}

	function formatDateShort(timestamp) {
		if (!timestamp) return 'N/A';
		const date = new Date(timestamp * 1000);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	async function openStripePortal() {
		processingAction = true;
		try {
			const res = await fetch('/api/v1/subscription/portal', { method: 'POST' });
			if (res.ok) {
				const data = await res.json();
				window.location.href = data.portal_url;
			}
		} catch (e) {
			error = e.message;
		} finally {
			processingAction = false;
		}
	}

	async function updatePaymentMethod() {
		processingAction = true;
		try {
			const res = await fetch('/api/v1/subscription/update-payment', { method: 'POST' });
			if (res.ok) {
				const data = await res.json();
				window.location.href = data.session_url;
			}
		} catch (e) {
			error = e.message;
		} finally {
			processingAction = false;
		}
	}

	function openUpgradeModal(plan) {
		selectedPlan = plan;
		showUpgradeModal = true;
	}

	async function confirmUpgrade() {
		if (!selectedPlan) return;
		processingAction = true;

		try {
			const res = await fetch('/api/v1/subscription/upgrade', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					bundle: selectedPlan.bundle,
					tier: selectedPlan.tier,
					billing_cycle: 'monthly',
				}),
			});

			if (res.ok) {
				const data = await res.json();
				window.location.href = data.checkout_url;
			} else {
				const errData = await res.json();
				error = errData.detail || 'Failed to process upgrade';
			}
		} catch (e) {
			error = e.message;
		} finally {
			processingAction = false;
		}
	}

	async function confirmCancel() {
		processingAction = true;

		try {
			const res = await fetch('/api/v1/subscription/cancel', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					reason: cancelReason,
					feedback: cancelFeedback,
				}),
			});

			if (res.ok) {
				showCancelModal = false;
				await loadBillingData();
			} else {
				const errData = await res.json();
				error = errData.detail || 'Failed to cancel subscription';
			}
		} catch (e) {
			error = e.message;
		} finally {
			processingAction = false;
		}
	}

	async function reactivateSubscription() {
		processingAction = true;

		try {
			const res = await fetch('/api/v1/subscription/reactivate', { method: 'POST' });
			if (res.ok) {
				await loadBillingData();
			}
		} catch (e) {
			error = e.message;
		} finally {
			processingAction = false;
		}
	}

	$: upgradeOptions = plans.filter(p => p.change_type === 'upgrade');
	$: downgradeOptions = plans.filter(p => p.change_type === 'downgrade');
	$: storagePercent = usage?.storage?.percent || 0;
</script>

<svelte:head>
	<title>Billing & Subscription | WOPR</title>
</svelte:head>

<div class="billing-page">
	<header>
		<h1>Billing & Subscription</h1>
		<p class="subtitle">Manage your WOPR subscription, payment methods, and invoices</p>
	</header>

	{#if loading}
		<div class="loading-state">
			<div class="spinner"></div>
			<p>Loading billing information...</p>
		</div>
	{:else if error}
		<div class="error-banner">
			<span class="error-icon">!</span>
			<p>{error}</p>
			<button on:click={() => error = null}>Dismiss</button>
		</div>
	{/if}

	{#if subscription}
		<!-- Current Plan Card -->
		<section class="current-plan-section">
			<div class="plan-card">
				<div class="plan-header">
					<div class="plan-info">
						<div class="plan-badge" class:trial={subscription.status === 'trial'} class:cancelled={subscription.cancel_at_period_end}>
							{#if subscription.cancel_at_period_end}
								Cancelling
							{:else if subscription.status === 'trial'}
								Trial
							{:else}
								Active
							{/if}
						</div>
						<h2>{subscription.bundle_name}</h2>
						<p class="tier-info">{subscription.tier_name}</p>
					</div>
					<div class="plan-price">
						<span class="amount">${formatCurrency(subscription.amount)}</span>
						<span class="period">/{subscription.billing_cycle === 'yearly' ? 'year' : 'month'}</span>
					</div>
				</div>

				{#if subscription.cancel_at_period_end}
					<div class="cancel-notice">
						<p>Your subscription will end on <strong>{formatDate(subscription.current_period_end)}</strong></p>
						<button class="btn btn-primary btn-sm" on:click={reactivateSubscription} disabled={processingAction}>
							Reactivate Subscription
						</button>
					</div>
				{/if}

				<div class="plan-details">
					<div class="detail-item">
						<span class="label">Billing Period</span>
						<span class="value">{formatDate(subscription.current_period_start)} - {formatDate(subscription.current_period_end)}</span>
					</div>
					<div class="detail-item">
						<span class="label">Next Payment</span>
						<span class="value">{subscription.cancel_at_period_end ? 'N/A' : formatDate(subscription.current_period_end)}</span>
					</div>
					<div class="detail-item">
						<span class="label">Payment Method</span>
						<span class="value">
							{#if subscription.payment_method}
								<span class="card-icon">{subscription.payment_method.brand}</span>
								**** {subscription.payment_method.last4}
								<span class="exp">exp {subscription.payment_method.exp_month}/{subscription.payment_method.exp_year}</span>
							{:else}
								No payment method
							{/if}
						</span>
					</div>
				</div>

				<div class="plan-actions">
					<button class="btn btn-secondary" on:click={updatePaymentMethod} disabled={processingAction}>
						Update Payment Method
					</button>
					<button class="btn btn-secondary" on:click={openStripePortal} disabled={processingAction}>
						Manage in Stripe
					</button>
				</div>
			</div>
		</section>

		<!-- Usage Section -->
		{#if usage}
			<section class="usage-section">
				<h2>Usage</h2>
				<div class="usage-grid">
					<div class="usage-card">
						<div class="usage-header">
							<span class="usage-label">Storage</span>
							<span class="usage-value">{usage.storage?.used_gb?.toFixed(1)} / {usage.storage?.limit_gb} GB</span>
						</div>
						<div class="progress-bar">
							<div class="progress-fill" style="width: {storagePercent}%"></div>
						</div>
						<span class="usage-percent">{storagePercent}% used</span>
					</div>

					<div class="usage-card">
						<div class="usage-header">
							<span class="usage-label">Users</span>
							<span class="usage-value">{usage.users?.count} / {usage.users?.limit}</span>
						</div>
						<div class="progress-bar">
							<div class="progress-fill" style="width: {(usage.users?.count / usage.users?.limit) * 100}%"></div>
						</div>
					</div>

					<div class="usage-card">
						<div class="usage-header">
							<span class="usage-label">Apps Enabled</span>
							<span class="usage-value">{usage.apps?.enabled?.length || 0}</span>
						</div>
						<div class="apps-list">
							{#each (usage.apps?.enabled || []).slice(0, 5) as app}
								<span class="app-tag">{app}</span>
							{/each}
							{#if (usage.apps?.enabled?.length || 0) > 5}
								<span class="app-tag more">+{usage.apps.enabled.length - 5} more</span>
							{/if}
						</div>
					</div>
				</div>
			</section>
		{/if}

		<!-- Upgrade Options -->
		{#if upgradeOptions.length > 0 && !subscription.cancel_at_period_end}
			<section class="upgrade-section">
				<h2>Upgrade Your Plan</h2>
				<p class="section-subtitle">Get more storage, users, and access to additional apps</p>

				<div class="plans-grid">
					{#each upgradeOptions.slice(0, 3) as plan}
						<div class="upgrade-card" class:recommended={plan.bundle === 'professional'}>
							{#if plan.bundle === 'professional'}
								<div class="recommended-badge">Recommended</div>
							{/if}
							<div class="upgrade-header">
								<h3>{plan.bundle_name}</h3>
								<p class="tier">{plan.tier_name}</p>
							</div>
							<div class="upgrade-price">
								<span class="amount">${formatCurrency(plan.monthly_price)}</span>
								<span class="period">/month</span>
							</div>
							<ul class="feature-list">
								<li>{plan.storage_gb} GB Storage</li>
								{#each (plan.features || []).slice(0, 3) as feature}
									<li>{feature}</li>
								{/each}
							</ul>
							<button class="btn btn-primary" on:click={() => openUpgradeModal(plan)}>
								Upgrade
							</button>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Invoice History -->
		<section class="invoices-section">
			<div class="section-header">
				<h2>Invoice History</h2>
				<button class="btn btn-text" on:click={openStripePortal}>View All</button>
			</div>

			{#if invoices.length > 0}
				<div class="invoices-table">
					<div class="invoice-header">
						<span>Date</span>
						<span>Description</span>
						<span>Amount</span>
						<span>Status</span>
						<span></span>
					</div>
					{#each invoices as invoice}
						<div class="invoice-row">
							<span class="date">{formatDateShort(invoice.date)}</span>
							<span class="description">{invoice.description}</span>
							<span class="amount">${formatCurrency(invoice.amount)}</span>
							<span class="status" class:paid={invoice.status === 'paid'}>
								{invoice.status}
							</span>
							<a href={invoice.pdf_url} target="_blank" class="download-link">PDF</a>
						</div>
					{/each}
				</div>
			{:else}
				<p class="no-invoices">No invoices yet</p>
			{/if}
		</section>

		<!-- Danger Zone -->
		<section class="danger-zone">
			<h2>Cancel Subscription</h2>
			<div class="cancel-card">
				<p>
					If you cancel, your subscription will remain active until the end of your current billing period.
					After that, your apps will be disabled and data will be retained for 14 days before permanent deletion.
				</p>
				{#if !subscription.cancel_at_period_end}
					<button class="btn btn-danger" on:click={() => showCancelModal = true}>
						Cancel Subscription
					</button>
				{:else}
					<p class="already-cancelled">Your subscription is scheduled to cancel on {formatDate(subscription.current_period_end)}</p>
				{/if}
			</div>
		</section>
	{/if}
</div>

<!-- Upgrade Modal -->
{#if showUpgradeModal && selectedPlan}
	<div class="modal-overlay" on:click={() => showUpgradeModal = false}>
		<div class="modal" on:click|stopPropagation>
			<div class="modal-header">
				<h2>Upgrade to {selectedPlan.bundle_name}</h2>
				<button class="close-btn" on:click={() => showUpgradeModal = false}>&times;</button>
			</div>
			<div class="modal-body">
				<div class="upgrade-summary">
					<div class="summary-row">
						<span>New Plan</span>
						<strong>{selectedPlan.bundle_name} - {selectedPlan.tier_name}</strong>
					</div>
					<div class="summary-row">
						<span>Storage</span>
						<strong>{selectedPlan.storage_gb} GB</strong>
					</div>
					<div class="summary-row total">
						<span>New Monthly Price</span>
						<strong>${formatCurrency(selectedPlan.monthly_price)}/month</strong>
					</div>
				</div>
				<p class="prorate-note">
					You'll be charged a prorated amount for the remainder of your current billing period.
				</p>
			</div>
			<div class="modal-footer">
				<button class="btn btn-secondary" on:click={() => showUpgradeModal = false}>Cancel</button>
				<button class="btn btn-primary" on:click={confirmUpgrade} disabled={processingAction}>
					{processingAction ? 'Processing...' : 'Confirm Upgrade'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Cancel Modal -->
{#if showCancelModal}
	<div class="modal-overlay" on:click={() => showCancelModal = false}>
		<div class="modal cancel-modal" on:click|stopPropagation>
			<div class="modal-header">
				<h2>Cancel Subscription</h2>
				<button class="close-btn" on:click={() => showCancelModal = false}>&times;</button>
			</div>
			<div class="modal-body">
				<p class="cancel-warning">
					We're sorry to see you go. Your subscription will remain active until
					<strong>{formatDate(subscription?.current_period_end)}</strong>.
				</p>

				<div class="form-group">
					<label for="cancel-reason">Why are you cancelling?</label>
					<select id="cancel-reason" bind:value={cancelReason}>
						<option value="">Select a reason...</option>
						<option value="too_expensive">Too expensive</option>
						<option value="not_using">Not using it enough</option>
						<option value="missing_features">Missing features I need</option>
						<option value="switching">Switching to another service</option>
						<option value="temporary">Just temporary - will be back</option>
						<option value="other">Other</option>
					</select>
				</div>

				<div class="form-group">
					<label for="cancel-feedback">Any additional feedback? (optional)</label>
					<textarea
						id="cancel-feedback"
						bind:value={cancelFeedback}
						placeholder="Help us improve..."
						rows="3"
					></textarea>
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn btn-secondary" on:click={() => showCancelModal = false}>Keep Subscription</button>
				<button class="btn btn-danger" on:click={confirmCancel} disabled={processingAction || !cancelReason}>
					{processingAction ? 'Processing...' : 'Confirm Cancellation'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.billing-page {
		max-width: 900px;
		margin: 0 auto;
		padding: 2rem;
	}

	header {
		margin-bottom: 2rem;
	}

	header h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.subtitle {
		color: var(--theme-text-muted, #888);
	}

	/* Loading State */
	.loading-state {
		text-align: center;
		padding: 4rem 0;
	}

	.spinner {
		width: 40px;
		height: 40px;
		border: 3px solid var(--theme-border, #333);
		border-top-color: var(--theme-primary, #00ff41);
		border-radius: 50%;
		margin: 0 auto 1rem;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* Error Banner */
	.error-banner {
		display: flex;
		align-items: center;
		gap: 1rem;
		background: var(--theme-error-subtle, rgba(239, 68, 68, 0.1));
		border: 1px solid var(--theme-error, #ef4444);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
	}

	.error-icon {
		width: 24px;
		height: 24px;
		background: var(--theme-error, #ef4444);
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: bold;
		flex-shrink: 0;
	}

	.error-banner p {
		flex: 1;
		margin: 0;
		color: var(--theme-error, #ef4444);
	}

	/* Sections */
	section {
		margin-bottom: 2.5rem;
	}

	section h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
	}

	.section-subtitle {
		color: var(--theme-text-muted, #888);
		margin-bottom: 1.5rem;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}

	/* Plan Card */
	.plan-card {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 12px;
		padding: 1.5rem;
	}

	.plan-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1.5rem;
	}

	.plan-info h2 {
		margin: 0.5rem 0 0.25rem;
		font-size: 1.5rem;
	}

	.tier-info {
		color: var(--theme-text-muted, #888);
		margin: 0;
	}

	.plan-badge {
		display: inline-block;
		padding: 0.25rem 0.75rem;
		border-radius: 20px;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		background: var(--theme-success, #22c55e);
		color: #fff;
	}

	.plan-badge.trial {
		background: var(--theme-warning, #f59e0b);
	}

	.plan-badge.cancelled {
		background: var(--theme-error, #ef4444);
	}

	.plan-price .amount {
		font-size: 2.5rem;
		font-weight: 700;
		color: var(--theme-primary, #00ff41);
	}

	.plan-price .period {
		color: var(--theme-text-muted, #888);
	}

	.cancel-notice {
		background: var(--theme-warning-subtle, rgba(245, 158, 11, 0.1));
		border: 1px solid var(--theme-warning, #f59e0b);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.cancel-notice p {
		margin: 0;
		color: var(--theme-warning, #f59e0b);
	}

	.plan-details {
		background: var(--theme-bg, #0a0a0a);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
	}

	.detail-item {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem 0;
	}

	.detail-item:not(:last-child) {
		border-bottom: 1px solid var(--theme-border, #333);
	}

	.detail-item .label {
		color: var(--theme-text-muted, #888);
	}

	.detail-item .exp {
		color: var(--theme-text-muted, #888);
		font-size: 0.85rem;
		margin-left: 0.5rem;
	}

	.plan-actions {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}

	/* Usage Section */
	.usage-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 1rem;
	}

	.usage-card {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 8px;
		padding: 1rem;
	}

	.usage-header {
		display: flex;
		justify-content: space-between;
		margin-bottom: 0.75rem;
	}

	.usage-label {
		color: var(--theme-text-muted, #888);
		font-size: 0.9rem;
	}

	.usage-value {
		font-weight: 600;
	}

	.progress-bar {
		height: 8px;
		background: var(--theme-bg, #0a0a0a);
		border-radius: 4px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: var(--theme-primary, #00ff41);
		border-radius: 4px;
		transition: width 0.3s ease;
	}

	.usage-percent {
		font-size: 0.8rem;
		color: var(--theme-text-muted, #888);
		margin-top: 0.5rem;
		display: block;
	}

	.apps-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}

	.app-tag {
		background: var(--theme-bg, #0a0a0a);
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.75rem;
	}

	.app-tag.more {
		color: var(--theme-text-muted, #888);
	}

	/* Upgrade Section */
	.plans-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 1.5rem;
	}

	.upgrade-card {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 12px;
		padding: 1.5rem;
		position: relative;
		display: flex;
		flex-direction: column;
	}

	.upgrade-card.recommended {
		border-color: var(--theme-primary, #00ff41);
	}

	.recommended-badge {
		position: absolute;
		top: -10px;
		left: 50%;
		transform: translateX(-50%);
		background: var(--theme-primary, #00ff41);
		color: var(--theme-text-on-primary, #000);
		padding: 0.25rem 1rem;
		border-radius: 20px;
		font-size: 0.75rem;
		font-weight: 600;
	}

	.upgrade-header h3 {
		margin: 0 0 0.25rem;
	}

	.upgrade-header .tier {
		color: var(--theme-text-muted, #888);
		margin: 0;
		font-size: 0.9rem;
	}

	.upgrade-price {
		margin: 1rem 0;
	}

	.upgrade-price .amount {
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--theme-primary, #00ff41);
	}

	.upgrade-price .period {
		color: var(--theme-text-muted, #888);
	}

	.feature-list {
		list-style: none;
		padding: 0;
		margin: 0 0 1.5rem;
		flex: 1;
	}

	.feature-list li {
		padding: 0.5rem 0;
		padding-left: 1.5rem;
		position: relative;
	}

	.feature-list li::before {
		content: '✓';
		position: absolute;
		left: 0;
		color: var(--theme-primary, #00ff41);
	}

	/* Invoices */
	.invoices-table {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 8px;
		overflow: hidden;
	}

	.invoice-header,
	.invoice-row {
		display: grid;
		grid-template-columns: 100px 1fr 100px 80px 60px;
		gap: 1rem;
		padding: 1rem;
		align-items: center;
	}

	.invoice-header {
		background: var(--theme-bg, #0a0a0a);
		font-size: 0.85rem;
		color: var(--theme-text-muted, #888);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.invoice-row {
		border-top: 1px solid var(--theme-border, #333);
	}

	.invoice-row .status {
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.8rem;
		text-transform: capitalize;
		background: var(--theme-bg, #0a0a0a);
	}

	.invoice-row .status.paid {
		background: var(--theme-success-subtle, rgba(34, 197, 94, 0.1));
		color: var(--theme-success, #22c55e);
	}

	.download-link {
		color: var(--theme-primary, #00ff41);
		text-decoration: none;
		font-size: 0.9rem;
	}

	.no-invoices {
		color: var(--theme-text-muted, #888);
		text-align: center;
		padding: 2rem;
	}

	/* Danger Zone */
	.danger-zone {
		margin-top: 3rem;
		padding-top: 2rem;
		border-top: 1px solid var(--theme-border, #333);
	}

	.danger-zone h2 {
		color: var(--theme-error, #ef4444);
	}

	.cancel-card {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 8px;
		padding: 1.5rem;
	}

	.cancel-card p {
		color: var(--theme-text-muted, #888);
		margin: 0 0 1rem;
		max-width: 600px;
	}

	.already-cancelled {
		color: var(--theme-warning, #f59e0b);
		font-weight: 500;
	}

	/* Buttons */
	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.25rem;
		border-radius: 8px;
		font-weight: 600;
		font-size: 0.9rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
		text-decoration: none;
	}

	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-primary {
		background: var(--theme-primary, #00ff41);
		color: var(--theme-text-on-primary, #000);
	}

	.btn-primary:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	.btn-secondary {
		background: var(--theme-surface, #1a1a1a);
		color: var(--theme-text, #e0e0e0);
		border: 1px solid var(--theme-border, #333);
	}

	.btn-secondary:hover:not(:disabled) {
		background: var(--theme-surface-hover, #252525);
	}

	.btn-danger {
		background: var(--theme-error, #ef4444);
		color: #fff;
	}

	.btn-danger:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	.btn-text {
		background: transparent;
		color: var(--theme-primary, #00ff41);
		padding: 0.5rem;
	}

	.btn-sm {
		padding: 0.5rem 1rem;
		font-size: 0.85rem;
	}

	/* Modal */
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.8);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.modal {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 12px;
		max-width: 500px;
		width: 100%;
		max-height: 90vh;
		overflow-y: auto;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1.5rem;
		border-bottom: 1px solid var(--theme-border, #333);
	}

	.modal-header h2 {
		margin: 0;
		font-size: 1.25rem;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--theme-text-muted, #888);
		font-size: 1.5rem;
		cursor: pointer;
		line-height: 1;
	}

	.modal-body {
		padding: 1.5rem;
	}

	.modal-footer {
		display: flex;
		justify-content: flex-end;
		gap: 1rem;
		padding: 1.5rem;
		border-top: 1px solid var(--theme-border, #333);
	}

	/* Upgrade Summary */
	.upgrade-summary {
		background: var(--theme-bg, #0a0a0a);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1rem;
	}

	.summary-row {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem 0;
	}

	.summary-row.total {
		border-top: 1px solid var(--theme-border, #333);
		margin-top: 0.5rem;
		padding-top: 1rem;
	}

	.summary-row.total strong {
		color: var(--theme-primary, #00ff41);
		font-size: 1.1rem;
	}

	.prorate-note {
		font-size: 0.9rem;
		color: var(--theme-text-muted, #888);
		margin: 0;
	}

	/* Cancel Modal */
	.cancel-warning {
		background: var(--theme-error-subtle, rgba(239, 68, 68, 0.1));
		border: 1px solid var(--theme-error, #ef4444);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
		color: var(--theme-error, #ef4444);
	}

	.form-group {
		margin-bottom: 1rem;
	}

	.form-group label {
		display: block;
		margin-bottom: 0.5rem;
		font-weight: 500;
	}

	.form-group select,
	.form-group textarea {
		width: 100%;
		padding: 0.75rem;
		background: var(--theme-bg, #0a0a0a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 8px;
		color: var(--theme-text, #e0e0e0);
		font-size: 1rem;
	}

	.form-group textarea {
		resize: vertical;
	}

	@media (max-width: 600px) {
		.billing-page {
			padding: 1rem;
		}

		.plan-header {
			flex-direction: column;
			gap: 1rem;
		}

		.invoice-header,
		.invoice-row {
			grid-template-columns: 80px 1fr 60px;
		}

		.invoice-header span:nth-child(4),
		.invoice-header span:nth-child(5),
		.invoice-row span:nth-child(4),
		.invoice-row a {
			display: none;
		}
	}
</style>
