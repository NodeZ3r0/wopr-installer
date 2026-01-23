<script>
	import { onMount } from 'svelte';
	import { loading, error } from '$lib/stores.js';
	import { getBillingInfo, getBundles } from '$lib/api.js';

	let billing = null;
	let bundles = [];

	onMount(async () => {
		$loading = true;
		try {
			[billing, bundles] = await Promise.all([
				getBillingInfo(),
				getBundles()
			]);
		} catch (e) {
			$error = e.message;
		} finally {
			$loading = false;
		}
	});

	$: currentBundle = bundles.find(b => b.id === billing?.bundle_id);
	$: upgradeOptions = bundles.filter(b => b.price > (currentBundle?.price || 0));

	function formatDate(dateString) {
		if (!dateString) return 'N/A';
		return new Date(dateString).toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		});
	}
</script>

<svelte:head>
	<title>Billing | WOPR</title>
</svelte:head>

<div class="billing-page">
	<header>
		<h1>Billing & Subscription</h1>
		<p class="text-muted">Manage your WOPR subscription and hosting</p>
	</header>

	{#if $loading}
		<div class="loading">Loading billing information...</div>
	{:else if $error}
		<div class="error card">
			<h3>Error</h3>
			<p>{$error}</p>
		</div>
	{:else if billing}
		<!-- Current Plan -->
		<section class="current-plan">
			<h2>Current Plan</h2>
			<div class="plan-card card">
				<div class="plan-header">
					<div>
						<h3>{currentBundle?.name || billing.bundle_id} Bundle</h3>
						<span class="badge badge-success">Active</span>
					</div>
					<div class="plan-price">
						<span class="amount">${billing.monthly_cost}</span>
						<span class="period">/month</span>
					</div>
				</div>

				<div class="plan-details">
					<div class="detail-row">
						<span class="label">WOPR Service Fee</span>
						<span class="value">${currentBundle?.price || billing.monthly_cost}/mo</span>
					</div>
					<div class="detail-row">
						<span class="label">Hosting ({billing.provider})</span>
						<span class="value">${billing.hosting_cost || '0.00'}/mo</span>
					</div>
					<div class="detail-row">
						<span class="label">Next Billing Date</span>
						<span class="value">{formatDate(billing.next_billing_date)}</span>
					</div>
					<div class="detail-row">
						<span class="label">Payment Method</span>
						<span class="value">
							{#if billing.payment_method}
								{billing.payment_method.brand} ****{billing.payment_method.last4}
							{:else}
								Not configured
							{/if}
						</span>
					</div>
				</div>

				<div class="plan-actions">
					<a href={billing.stripe_portal_url || '#'} class="btn btn-secondary" target="_blank">
						Manage Payment Method
					</a>
					<a href={billing.invoice_history_url || '#'} class="btn btn-secondary" target="_blank">
						View Invoices
					</a>
				</div>
			</div>
		</section>

		<!-- Included Modules -->
		{#if currentBundle?.modules}
			<section>
				<h2>Included in Your Plan</h2>
				<div class="included-modules">
					{#each currentBundle.modules as mod}
						<span class="module-tag">{mod}</span>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Upgrade Options -->
		{#if upgradeOptions.length > 0}
			<section>
				<h2>Upgrade Your Plan</h2>
				<p class="text-muted">Get more modules and capabilities</p>
				<div class="upgrade-grid">
					{#each upgradeOptions as bundle}
						<div class="upgrade-card card">
							<div class="upgrade-header">
								<h3>{bundle.name}</h3>
								<div class="upgrade-price">
									<span class="amount">${bundle.price}</span>
									<span class="period">/mo</span>
								</div>
							</div>
							<p class="text-muted">{bundle.description}</p>
							<div class="upgrade-features">
								<span class="label">Additional modules:</span>
								<ul>
									{#each bundle.modules.filter(m => !currentBundle?.modules?.includes(m)) as mod}
										<li>{mod}</li>
									{/each}
								</ul>
							</div>
							<button class="btn btn-primary">
								Upgrade to {bundle.name}
							</button>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Hosting Details -->
		<section>
			<h2>Hosting Details</h2>
			<div class="hosting-card card">
				<div class="hosting-info">
					<div class="info-item">
						<span class="label">Provider</span>
						<span class="value">{billing.provider || 'Unknown'}</span>
					</div>
					<div class="info-item">
						<span class="label">Region</span>
						<span class="value">{billing.region || 'Unknown'}</span>
					</div>
					<div class="info-item">
						<span class="label">Server Specs</span>
						<span class="value">{billing.server_specs || '2 vCPU, 2GB RAM'}</span>
					</div>
					<div class="info-item">
						<span class="label">IP Address</span>
						<span class="value">{billing.ip_address || 'N/A'}</span>
					</div>
				</div>
			</div>
		</section>

		<!-- Cancel Section -->
		<section class="danger-zone">
			<h2>Cancel Subscription</h2>
			<div class="cancel-card card">
				<p>
					If you cancel your subscription, your WOPR instance will be disabled at the end of your
					current billing period. Your data will be preserved for 30 days.
				</p>
				<button class="btn btn-danger">
					Cancel Subscription
				</button>
			</div>
		</section>
	{/if}
</div>

<style>
	.billing-page {
		max-width: 800px;
	}

	header {
		margin-bottom: 2rem;
	}

	section {
		margin-bottom: 2.5rem;
	}

	section h2 {
		margin-bottom: 1rem;
	}

	.plan-card {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.plan-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
	}

	.plan-header h3 {
		margin-bottom: 0.5rem;
	}

	.plan-price {
		text-align: right;
	}

	.plan-price .amount {
		font-size: 2rem;
		font-weight: bold;
		color: var(--color-primary);
	}

	.plan-price .period {
		color: var(--color-text-muted);
	}

	.plan-details {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
		background: var(--color-surface-hover);
		border-radius: 8px;
	}

	.detail-row {
		display: flex;
		justify-content: space-between;
	}

	.detail-row .label {
		color: var(--color-text-muted);
	}

	.plan-actions {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.included-modules {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.module-tag {
		background: var(--color-surface-hover);
		padding: 0.5rem 1rem;
		border-radius: 20px;
		font-size: 0.9rem;
	}

	.upgrade-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 1.5rem;
		margin-top: 1rem;
	}

	.upgrade-card {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.upgrade-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
	}

	.upgrade-price .amount {
		font-size: 1.5rem;
		font-weight: bold;
		color: var(--color-primary);
	}

	.upgrade-price .period {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	.upgrade-features {
		flex: 1;
	}

	.upgrade-features .label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.upgrade-features ul {
		margin: 0.5rem 0 0 1.25rem;
		padding: 0;
	}

	.upgrade-features li {
		margin-bottom: 0.25rem;
	}

	.hosting-card {
		padding: 1.5rem;
	}

	.hosting-info {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 1.5rem;
	}

	.info-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.info-item .label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.info-item .value {
		font-weight: 500;
	}

	.danger-zone {
		margin-top: 3rem;
		padding-top: 2rem;
		border-top: 1px solid var(--color-border);
	}

	.danger-zone h2 {
		color: var(--color-error);
	}

	.cancel-card {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		align-items: flex-start;
	}

	.cancel-card p {
		color: var(--color-text-muted);
		max-width: 500px;
	}

	.btn-danger {
		background: var(--color-error);
		color: #fff;
	}

	.btn-danger:hover {
		background: #c0392b;
	}

	.loading {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}
</style>
