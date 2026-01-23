<script>
	import { onMount } from 'svelte';
	import { instance, modules, loading, error } from '$lib/stores.js';
	import { getInstanceStatus, getModules } from '$lib/api.js';
	import StatusBadge from '$lib/components/StatusBadge.svelte';

	onMount(async () => {
		$loading = true;
		try {
			const [instanceData, modulesData] = await Promise.all([
				getInstanceStatus(),
				getModules()
			]);
			$instance = instanceData;
			$modules = modulesData;
		} catch (e) {
			$error = e.message;
		} finally {
			$loading = false;
		}
	});

	$: runningModules = $modules.filter(m => m.status === 'running');
	$: trialModules = $modules.filter(m => m.status === 'trial');
</script>

<svelte:head>
	<title>Dashboard | WOPR</title>
</svelte:head>

<div class="dashboard">
	<header>
		<h1>Welcome to WOPR</h1>
		<p class="text-muted">Your Sovereign Suite Dashboard</p>
	</header>

	{#if $loading}
		<div class="loading">Loading...</div>
	{:else if $error}
		<div class="error card">
			<h3>Error loading dashboard</h3>
			<p>{$error}</p>
		</div>
	{:else}
		<!-- Instance Status -->
		<section class="status-section">
			<div class="card status-card">
				<div class="status-header">
					<h2>Instance Status</h2>
					<StatusBadge status={$instance.status} size="large" />
				</div>
				<div class="status-details">
					<div class="detail">
						<span class="label">Bundle</span>
						<span class="value">{$instance.bundle || 'Personal'}</span>
					</div>
					<div class="detail">
						<span class="label">Domain</span>
						<span class="value">{$instance.domain || 'Not configured'}</span>
					</div>
					<div class="detail">
						<span class="label">Modules Active</span>
						<span class="value">{runningModules.length}</span>
					</div>
				</div>
			</div>
		</section>

		<!-- Quick Access -->
		<section class="apps-section">
			<h2>Your Apps</h2>
			<div class="grid grid-3">
				{#each runningModules as module}
					<a href={module.url} target="_blank" class="app-card card">
						<h3>{module.name}</h3>
						<p class="text-muted">{module.subdomain}.{$instance.domain}</p>
						<StatusBadge status="running" size="small" />
					</a>
				{/each}

				{#if runningModules.length === 0}
					<p class="text-muted">No apps running yet.</p>
				{/if}
			</div>
		</section>

		<!-- Active Trials -->
		{#if trialModules.length > 0}
			<section class="trials-section">
				<h2>Active Trials</h2>
				<div class="grid grid-2">
					{#each trialModules as module}
						<div class="trial-card card">
							<div class="trial-header">
								<h3>{module.name}</h3>
								<StatusBadge status="trial" />
							</div>
							<p class="text-warning">
								{module.trial_days_remaining} days remaining
							</p>
							<a href="/billing" class="btn btn-secondary">
								Upgrade to Keep
							</a>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Quick Actions -->
		<section class="actions-section">
			<h2>Quick Actions</h2>
			<div class="actions">
				<a href="/modules" class="btn btn-secondary">Manage Modules</a>
				<a href="/trials" class="btn btn-secondary">Browse Trials</a>
				<a href="/settings" class="btn btn-secondary">Settings</a>
			</div>
		</section>
	{/if}
</div>

<style>
	.dashboard {
		max-width: 1000px;
	}

	header {
		margin-bottom: 2rem;
	}

	header h1 {
		margin-bottom: 0.25rem;
	}

	section {
		margin-bottom: 2rem;
	}

	section h2 {
		margin-bottom: 1rem;
		font-size: 1.25rem;
	}

	.status-card {
		background: linear-gradient(135deg, var(--color-surface), var(--color-surface-hover));
	}

	.status-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.status-details {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1rem;
	}

	.detail {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.detail .label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
	}

	.detail .value {
		font-size: 1.1rem;
		font-weight: 500;
	}

	.app-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		transition: transform 0.2s;
	}

	.app-card:hover {
		transform: translateY(-2px);
	}

	.app-card h3 {
		font-size: 1rem;
	}

	.trial-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.trial-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.actions {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.loading {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}

	@media (max-width: 600px) {
		.status-details {
			grid-template-columns: 1fr;
		}
	}
</style>
