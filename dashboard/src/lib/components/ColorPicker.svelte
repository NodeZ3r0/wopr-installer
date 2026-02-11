<script>
	/**
	 * ColorPicker Component
	 * =====================
	 *
	 * Simple color picker with hex input and visual preview.
	 */

	export let value = '#000000';
	export let label = 'Color';
	export let onChange = () => {};

	function handleInput(event) {
		const newValue = event.target.value;
		// Validate hex format
		if (/^#[0-9a-fA-F]{6}$/.test(newValue)) {
			onChange(newValue);
		}
	}

	function handleColorInput(event) {
		onChange(event.target.value);
	}
</script>

<div class="color-picker">
	<label class="picker-label">{label}</label>

	<div class="picker-controls">
		<input
			type="color"
			class="color-input"
			{value}
			on:input={handleColorInput}
		/>

		<input
			type="text"
			class="hex-input"
			{value}
			placeholder="#000000"
			maxlength="7"
			on:input={handleInput}
		/>

		<div class="color-swatch" style="background: {value};"></div>
	</div>
</div>

<style>
	.color-picker {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.picker-label {
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--theme-text-muted);
	}

	.picker-controls {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.color-input {
		width: 40px;
		height: 40px;
		padding: 0;
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius-sm);
		cursor: pointer;
		background: transparent;
	}

	.color-input::-webkit-color-swatch-wrapper {
		padding: 0;
	}

	.color-input::-webkit-color-swatch {
		border: none;
		border-radius: 4px;
	}

	.hex-input {
		flex: 1;
		max-width: 120px;
		padding: 0.5rem 0.75rem;
		font-family: monospace;
		font-size: 0.9rem;
		text-transform: uppercase;
	}

	.color-swatch {
		width: 24px;
		height: 24px;
		border-radius: var(--theme-radius-sm);
		border: 1px solid var(--theme-border);
	}
</style>
