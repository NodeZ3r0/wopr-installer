<script>
	import { onMount } from 'svelte';
	import { trials, loading, error } from '$lib/stores.js';
	import { getTrials, startTrial } from '$lib/api.js';
	import { notify } from '$lib/stores.js';

	onMount(async () => {
		$loading = true;
		try {
			$trials = await getTrials();
		} catch (e) {
			$error = e.message;
		} finally {
			$loading = false;
		}
	});

	$: availableTrials = $trials.filter(t => t.status === 'available');
	$: activeTrials = $trials.filter(t => t.status === 'active');

	async function handleStartTrial(trialId) {
		try {
			await startTrial(trialId);
			notify('Trial started successfully!', 'success');
			$trials = await getTrials();
		} catch (e) {
			notify(e.message, 'error');
		}
	}
</script>

<svelte:head>
	<title>Trials | WOPR</title>
</svelte:head>

<div class="trials-page">
	<header>
		<h1>Free Trials</h1>
		<p class="text-muted">Try premium modules for free before upgrading</p>
	</header>

	{#if $loading}
		<div class="loading">Loading trials...</div>
	{:else if $error}
		<div class="error card">
			<h3>Error</h3>
			<p>{$error}</p>
		</div>
	{:else}
		<!-- Active Trials -->
		{#if activeTrials.length > 0}
			<section>
				<h2>Your Active Trials</h2>
				<div class="grid grid-2">
					{#each activeTrials as trial}
						<div class="trial-card card">
							<div class="trial-header">
								<h3>{trial.name}</h3>
								<span class="badge badge-warning">Active</span>
							</div>
							<p class="text-muted">{trial.description}</p>
							<div class="trial-progress">
								<div class="progress-bar">
									<div
										class="progress-fill"
										style="width: {((trial.days_total - trial.days_remaining) / trial.days_total) * 100}%"
									></div>
								</div>
								<span class="days-remaining">
									{trial.days_remaining} of {trial.days_total} days remaining
								</span>
							</div>
							<div class="trial-modules">
								<span class="label">Included:</span>
								{#each trial.modules as mod}
									<span class="module-tag">{mod}</span>
								{/each}
							</div>
							<a href="/billing" class="btn btn-primary">
								Upgrade to Keep
							</a>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Available Trials -->
		<section>
			<h2>Available Trials</h2>
			{#if availableTrials.length > 0}
				<div class="grid grid-2">
					{#each availableTrials as trial}
						<div class="trial-card card">
							<div class="trial-header">
								<h3>{trial.name}</h3>
								<span class="badge badge-info">{trial.days} days free</span>
							</div>
							<p class="text-muted">{trial.description}</p>
							<div class="trial-modules">
								<span class="label">Includes:</span>
								{#each trial.modules as mod}
									<span class="module-tag">{mod}</span>
								{/each}
							</div>
							<div class="trial-footer">
								<span class="upgrade-price">
									Then ${trial.upgrade_price}/mo
								</span>
								<button
									class="btn btn-primary"
									on:click={() => handleStartTrial(trial.id)}
								>
									Start Free Trial
								</button>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-muted">No trials available for your current bundle.</p>
			{/if}
		</section>

		<!-- How Trials Work -->
		<section class="info-section">
			<h2>How Trials Work</h2>
			<div class="info-cards grid grid-3">
				<div class="info-card card">
					<div class="info-icon">1</div>
					<h3>Start Free</h3>
					<p>Click "Start Free Trial" to instantly enable premium modules at no cost.</p>
				</div>
				<div class="info-card card">
					<div class="info-icon">2</div>
					<h3>Try for 90 Days</h3>
					<p>Use the modules fully. We'll remind you before the trial ends.</p>
				</div>
				<div class="info-card card">
					<div class="info-icon">3</div>
					<h3>Upgrade or Not</h3>
					<p>Keep the modules by upgrading, or they'll be disabled. Your data is safe.</p>
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.trials-page {
		max-width: 900px;
	}

	header {
		margin-bottom: 2rem;
	}

	section {
		margin-bottom: 3rem;
	}

	section h2 {
		margin-bottom: 1rem;
	}

	.trial-card {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.trial-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.trial-progress {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.progress-bar {
		height: 8px;
		background: var(--color-border);
		border-radius: 4px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: var(--color-warning);
		transition: width 0.3s;
	}

	.days-remaining {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.trial-modules {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}

	.trial-modules .label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.module-tag {
		background: var(--color-surface-hover);
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.8rem;
	}

	.trial-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.5rem;
	}

	.upgrade-price {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.info-section {
		margin-top: 3rem;
		padding-top: 2rem;
		border-top: 1px solid var(--color-border);
	}

	.info-card {
		text-align: center;
	}

	.info-icon {
		width: 40px;
		height: 40px;
		background: var(--color-primary);
		color: #000;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: bold;
		margin: 0 auto 1rem;
	}

	.info-card h3 {
		margin-bottom: 0.5rem;
	}

	.info-card p {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.loading {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}
</style>
