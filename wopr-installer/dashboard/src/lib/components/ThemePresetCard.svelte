<script>
	/**
	 * ThemePresetCard Component
	 * =========================
	 *
	 * Displays a clickable theme preset with color preview.
	 */

	export let preset;
	export let selected = false;
	export let onClick = () => {};

	$: colors = preset.preview || { primary: '#00d4aa', accent: '#ff9b3f', bg: '#0a0a0a' };
</script>

<button
	class="preset-card"
	class:selected
	on:click={() => onClick(preset.id)}
	style="--preview-bg: {colors.bg}; --preview-primary: {colors.primary}; --preview-accent: {colors.accent};"
>
	<div class="color-preview">
		<div class="color-bar primary"></div>
		<div class="color-bar accent"></div>
	</div>

	<div class="preset-info">
		<span class="preset-name">{preset.name}</span>
		{#if selected}
			<span class="check">&#10003;</span>
		{/if}
	</div>
</button>

<style>
	.preset-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
		background: var(--preview-bg);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius);
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
		min-width: 140px;
	}

	.preset-card:hover {
		border-color: var(--theme-text-muted);
		transform: translateY(-2px);
	}

	.preset-card.selected {
		border-color: var(--theme-primary);
		box-shadow: 0 0 0 3px var(--theme-primary-subtle);
	}

	.color-preview {
		display: flex;
		gap: 0.5rem;
		height: 32px;
	}

	.color-bar {
		flex: 1;
		border-radius: 4px;
	}

	.color-bar.primary {
		background: var(--preview-primary);
	}

	.color-bar.accent {
		background: var(--preview-accent);
	}

	.preset-info {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.preset-name {
		font-weight: 500;
		color: var(--theme-text);
		font-size: 0.9rem;
	}

	.check {
		color: var(--theme-primary);
		font-weight: bold;
	}
</style>
