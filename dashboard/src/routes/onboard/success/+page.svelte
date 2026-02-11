<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { resetOnboarding } from '$lib/stores/onboarding.js';

	let loading = true;
	let error = '';
	let orderDetails = null;
	let jobId = null;
	let autoRedirectCountdown = 5;

	onMount(async () => {
		// Get session_id from URL params (from Stripe redirect)
		const sessionId = $page.url.searchParams.get('session_id');

		if (!sessionId) {
			error = 'No session ID provided';
			loading = false;
			return;
		}

		try {
			// Verify the session and get order details
			const response = await fetch(`/api/v1/onboard/success?session_id=${sessionId}`);

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to verify payment');
			}

			const data = await response.json();
			orderDetails = data.order;
			jobId = data.job_id;

			// Clear the onboarding state
			resetOnboarding();

			// Auto-redirect to progress page after countdown
			if (jobId) {
				startAutoRedirect();
			}

		} catch (err) {
			error = err.message;
		} finally {
			loading = false;
		}
	});

	function startAutoRedirect() {
		const interval = setInterval(() => {
			autoRedirectCountdown--;
			if (autoRedirectCountdown <= 0) {
				clearInterval(interval);
				goToProgress();
			}
		}, 1000);
	}

	function goToProgress() {
		if (jobId) {
			goto(`/setup/${jobId}`);
		}
	}
</script>

<svelte:head>
	<title>Payment Successful - WOPR</title>
</svelte:head>

<div class="success-container">
	{#if loading}
		<div class="loading-state">
			<div class="spinner"></div>
			<p>Verifying your payment...</p>
		</div>
	{:else if error}
		<div class="error-state">
			<div class="error-icon">!</div>
			<h1>Something went wrong</h1>
			<p>{error}</p>
			<a href="/onboard" class="btn btn-primary">Try Again</a>
		</div>
	{:else}
		<div class="success-state">
			<div class="success-icon">
				<span class="checkmark">&#10003;</span>
			</div>

			<h1>Welcome to WOPR!</h1>
			<p class="subtitle">Your payment was successful. We're now setting up your Beacon.</p>

			{#if orderDetails}
				<div class="order-card">
					<h2>Order Details</h2>
					<div class="order-row">
						<span>Bundle:</span>
						<strong>{orderDetails.bundle_name}</strong>
					</div>
					<div class="order-row">
						<span>Beacon:</span>
						<strong>{orderDetails.beacon_name}.wopr.systems</strong>
					</div>
					<div class="order-row">
						<span>Admin Email:</span>
						<strong>{orderDetails.email}</strong>
					</div>
					<div class="order-row total">
						<span>Total:</span>
						<strong>{orderDetails.amount}</strong>
					</div>
				</div>
			{/if}

			<div class="next-steps">
				<h3>What happens next?</h3>
				<ol>
					<li>
						<strong>Server Creation</strong>
						<p>We're spinning up your personal cloud server now.</p>
					</li>
					<li>
						<strong>App Installation</strong>
						<p>All your apps will be installed and configured automatically.</p>
					</li>
					<li>
						<strong>Welcome Email</strong>
						<p>You'll receive login credentials and a getting started guide.</p>
					</li>
				</ol>
			</div>

			<div class="actions">
				{#if jobId}
					<button class="btn btn-primary" on:click={goToProgress}>
						Watch Setup Progress
						<span class="arrow">→</span>
					</button>
					<p class="auto-redirect">
						Redirecting in {autoRedirectCountdown} seconds...
					</p>
				{/if}
				<p class="timing-note">
					Setup typically completes in 5-10 minutes. We'll email you when it's ready!
				</p>
			</div>
		</div>
	{/if}
</div>

<style>
	.success-container {
		max-width: 600px;
		margin: 0 auto;
		padding: 2rem;
		text-align: center;
	}

	/* Loading state */
	.loading-state {
		padding: 4rem 0;
	}

	.spinner {
		width: 48px;
		height: 48px;
		border: 4px solid var(--theme-border);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		margin: 0 auto 1.5rem;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.loading-state p {
		color: var(--theme-text-muted);
		font-size: 1.1rem;
	}

	/* Error state */
	.error-state {
		padding: 4rem 0;
	}

	.error-icon {
		width: 64px;
		height: 64px;
		background: var(--theme-error);
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 2rem;
		font-weight: bold;
		margin: 0 auto 1.5rem;
	}

	.error-state h1 {
		margin-bottom: 0.5rem;
	}

	.error-state p {
		color: var(--theme-text-muted);
		margin-bottom: 2rem;
	}

	/* Success state */
	.success-state {
		animation: fadeIn 0.5s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; transform: translateY(20px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.success-icon {
		width: 80px;
		height: 80px;
		background: var(--theme-success);
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 1.5rem;
		animation: popIn 0.3s ease 0.2s both;
	}

	@keyframes popIn {
		from { transform: scale(0); }
		to { transform: scale(1); }
	}

	.checkmark {
		color: #fff;
		font-size: 2.5rem;
	}

	.success-state h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.subtitle {
		color: var(--theme-text-muted);
		font-size: 1.1rem;
		margin-bottom: 2rem;
	}

	/* Order card */
	.order-card {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
		text-align: left;
		margin-bottom: 2rem;
	}

	.order-card h2 {
		font-size: 1rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
		margin-bottom: 1rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--theme-border);
	}

	.order-row {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem 0;
	}

	.order-row span {
		color: var(--theme-text-muted);
	}

	.order-row.total {
		margin-top: 0.5rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--theme-border);
	}

	.order-row.total strong {
		color: var(--theme-primary);
		font-size: 1.1rem;
	}

	/* Next steps */
	.next-steps {
		text-align: left;
		margin-bottom: 2rem;
	}

	.next-steps h3 {
		font-size: 1.1rem;
		margin-bottom: 1rem;
	}

	.next-steps ol {
		list-style: none;
		padding: 0;
		counter-reset: steps;
	}

	.next-steps li {
		counter-increment: steps;
		padding: 1rem;
		padding-left: 3.5rem;
		position: relative;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		margin-bottom: 0.75rem;
	}

	.next-steps li::before {
		content: counter(steps);
		position: absolute;
		left: 1rem;
		top: 1rem;
		width: 28px;
		height: 28px;
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 600;
		font-size: 0.9rem;
	}

	.next-steps li strong {
		display: block;
		margin-bottom: 0.25rem;
	}

	.next-steps li p {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		margin: 0;
	}

	/* Actions */
	.actions {
		margin-top: 2rem;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem 2rem;
		border-radius: var(--theme-radius);
		font-weight: 600;
		font-size: 1.1rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
		text-decoration: none;
	}

	.btn-primary {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	.btn-primary:hover {
		background: var(--theme-primary-hover);
	}

	.arrow {
		font-size: 1.1rem;
	}

	.timing-note {
		margin-top: 1rem;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.auto-redirect {
		margin-top: 0.75rem;
		color: var(--theme-primary);
		font-size: 0.9rem;
		font-weight: 500;
	}
</style>
