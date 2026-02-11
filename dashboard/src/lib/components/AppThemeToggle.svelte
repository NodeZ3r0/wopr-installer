<script>
	/**
	 * AppThemeToggle Component
	 * ========================
	 *
	 * Toggle for enabling/disabling theme injection per app.
	 */

	export let app;
	export let enabled = false;
	export let isNative = false;
	export let onToggle = () => {};

	function handleToggle() {
		if (!isNative) {
			onToggle(app.id, !enabled);
		}
	}
</script>

<div class="app-theme-toggle">
	<div class="app-info">
		<span class="app-name">{app.name}</span>
		{#if isNative}
			<span class="badge badge-primary">WOPR Native</span>
		{/if}
	</div>

	<button
		class="toggle"
		class:active={enabled}
		class:disabled={isNative}
		on:click={handleToggle}
		disabled={isNative}
		title={isNative ? 'Native apps are always themed' : (enabled ? 'Click to disable theming' : 'Click to enable theming')}
	>
		<span class="toggle-label">{enabled ? 'On' : 'Off'}</span>
	</button>
</div>

<style>
	.app-theme-toggle {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--theme-border-subtle);
	}

	.app-theme-toggle:last-child {
		border-bottom: none;
	}

	.app-info {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.app-name {
		font-weight: 500;
	}

	.toggle {
		position: relative;
		display: flex;
		align-items: center;
		width: 60px;
		height: 30px;
		padding: 0 8px;
		background: var(--theme-border);
		border: none;
		border-radius: var(--theme-radius-full);
		cursor: pointer;
		transition: background-color 0.2s ease;
	}

	.toggle:hover:not(.disabled) {
		background: var(--theme-text-muted);
	}

	.toggle.active {
		background: var(--theme-primary);
		justify-content: flex-end;
	}

	.toggle.disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.toggle::before {
		content: '';
		position: absolute;
		left: 4px;
		width: 22px;
		height: 22px;
		background: white;
		border-radius: 50%;
		transition: transform 0.2s ease;
	}

	.toggle.active::before {
		transform: translateX(28px);
	}

	.toggle-label {
		position: absolute;
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		color: var(--theme-text-on-primary);
	}

	.toggle:not(.active) .toggle-label {
		right: 8px;
		color: var(--theme-text);
	}

	.toggle.active .toggle-label {
		left: 8px;
	}
</style>
