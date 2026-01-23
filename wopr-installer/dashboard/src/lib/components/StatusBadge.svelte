<script>
	export let status = 'unknown';
	export let size = 'normal';

	const statusConfig = {
		running: { color: 'success', icon: '●', text: 'Running' },
		healthy: { color: 'success', icon: '●', text: 'Healthy' },
		stopped: { color: 'error', icon: '○', text: 'Stopped' },
		error: { color: 'error', icon: '!', text: 'Error' },
		warning: { color: 'warning', icon: '!', text: 'Warning' },
		trial: { color: 'warning', icon: '◐', text: 'Trial' },
		pending: { color: 'info', icon: '◌', text: 'Pending' },
		unknown: { color: 'info', icon: '?', text: 'Unknown' }
	};

	$: config = statusConfig[status] || statusConfig.unknown;
</script>

<span class="status-badge badge-{config.color} size-{size}">
	<span class="icon">{config.icon}</span>
	<span class="text">{config.text}</span>
</span>

<style>
	.status-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.25rem 0.75rem;
		border-radius: 999px;
		font-weight: 600;
	}

	.size-small {
		font-size: 0.7rem;
		padding: 0.15rem 0.5rem;
	}

	.size-normal {
		font-size: 0.8rem;
	}

	.size-large {
		font-size: 0.9rem;
		padding: 0.35rem 1rem;
	}

	.badge-success {
		background: rgba(34, 197, 94, 0.2);
		color: var(--color-success);
	}

	.badge-warning {
		background: rgba(245, 158, 11, 0.2);
		color: var(--color-warning);
	}

	.badge-error {
		background: rgba(239, 68, 68, 0.2);
		color: var(--color-error);
	}

	.badge-info {
		background: rgba(59, 130, 246, 0.2);
		color: var(--color-info);
	}

	.icon {
		font-size: 0.9em;
	}
</style>
