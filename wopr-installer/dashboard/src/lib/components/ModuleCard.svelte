<script>
	export let module;

	const statusColors = {
		running: 'success',
		stopped: 'error',
		trial: 'warning',
		available: 'info'
	};

	function getStatusText(status) {
		switch (status) {
			case 'running': return 'Running';
			case 'stopped': return 'Stopped';
			case 'trial': return 'Trial';
			case 'trial_available': return 'Try Free';
			case 'addon_available': return 'Add-on';
			default: return status;
		}
	}
</script>

<div class="module-card card">
	<div class="module-header">
		<h3>{module.name}</h3>
		<span class="badge badge-{statusColors[module.status] || 'info'}">
			{getStatusText(module.status)}
		</span>
	</div>

	<p class="module-description text-muted">
		{module.description}
	</p>

	{#if module.trial_days_remaining}
		<p class="trial-info text-warning">
			{module.trial_days_remaining} days remaining in trial
		</p>
	{/if}

	<div class="module-actions">
		{#if module.status === 'running' && module.url}
			<a href={module.url} target="_blank" class="btn btn-primary">
				Open
			</a>
		{:else if module.status === 'trial_available'}
			<button class="btn btn-secondary" on:click={() => dispatch('start-trial', module.id)}>
				Start Free Trial
			</button>
		{:else if module.status === 'addon_available'}
			<button class="btn btn-secondary" on:click={() => dispatch('add-module', module.id)}>
				Add for ${module.price}/mo
			</button>
		{/if}
	</div>
</div>

<style>
	.module-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.module-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.module-header h3 {
		font-size: 1.1rem;
	}

	.module-description {
		font-size: 0.9rem;
		flex-grow: 1;
	}

	.trial-info {
		font-size: 0.85rem;
	}

	.module-actions {
		margin-top: 0.5rem;
	}

	.module-actions .btn {
		width: 100%;
		justify-content: center;
	}
</style>
