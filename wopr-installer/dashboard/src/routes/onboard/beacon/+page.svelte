<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		providerOptions,
		formattedPrice,
		canProceed,
		nextStep,
		prevStep,
		needsAdditionalUsers
	} from '$lib/stores/onboarding.js';

	let beaconError = '';
	let checkingBeacon = false;
	let debounceTimer;

	onMount(() => {
		// Redirect if no account info
		if (!$onboarding.email) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 3 }));
	});

	function sanitizeBeaconName(name) {
		// Only allow lowercase letters, numbers, hyphens
		return name.toLowerCase().replace(/[^a-z0-9-]/g, '').replace(/^-|-$/g, '');
	}

	async function checkBeaconAvailability(name) {
		if (!name || name.length < 3) {
			onboarding.update(o => ({ ...o, beaconAvailable: null }));
			return;
		}

		checkingBeacon = true;

		try {
			// In production, this would call the API
			// For now, simulate availability check
			await new Promise(resolve => setTimeout(resolve, 500));

			// Reserved names that aren't available
			const reserved = ['www', 'api', 'admin', 'mail', 'smtp', 'ftp', 'test', 'demo'];
			const isAvailable = !reserved.includes(name);

			onboarding.update(o => ({ ...o, beaconAvailable: isAvailable }));

			if (!isAvailable) {
				beaconError = 'This name is not available';
			} else {
				beaconError = '';
			}
		} catch (err) {
			beaconError = 'Could not check availability';
			onboarding.update(o => ({ ...o, beaconAvailable: null }));
		} finally {
			checkingBeacon = false;
		}
	}

	function handleBeaconInput(e) {
		const raw = e.target.value;
		const sanitized = sanitizeBeaconName(raw);
		onboarding.update(o => ({ ...o, beaconName: sanitized, beaconAvailable: null }));

		beaconError = '';

		// Debounce availability check
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			checkBeaconAvailability(sanitized);
		}, 500);
	}

	function selectProvider(providerId) {
		onboarding.update(o => ({ ...o, provider: providerId }));
	}

	function handleBack() {
		prevStep();
		goto('/onboard/account');
	}

	function handleContinue() {
		if ($canProceed) {
			nextStep();
			// Skip users step if bundle doesn't support multiple users
			if ($needsAdditionalUsers) {
				goto('/onboard/users');
			} else {
				goto('/onboard/checkout');
			}
		}
	}
</script>

<svelte:head>
	<title>Configure Your Beacon - WOPR Onboarding</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<h1>Configure Your Beacon</h1>
		<p class="subtitle">Choose your beacon name and where it will be hosted</p>
	</div>

	<div class="config-grid">
		<!-- Beacon name section -->
		<div class="config-section">
			<h2>Beacon Name</h2>
			<p class="section-description">This will be your personal cloud domain</p>

			<div class="beacon-input-wrapper">
				<div class="beacon-input-container">
					<input
						type="text"
						id="beacon-name"
						placeholder="mybeacon"
						value={$onboarding.beaconName}
						on:input={handleBeaconInput}
						class:error={beaconError}
						class:success={$onboarding.beaconAvailable === true}
						maxlength="32"
					/>
					<span class="beacon-domain">.wopr.systems</span>
					{#if checkingBeacon}
						<span class="checking">Checking...</span>
					{:else if $onboarding.beaconAvailable === true}
						<span class="available">&#10003; Available</span>
					{:else if $onboarding.beaconAvailable === false}
						<span class="unavailable">&#10007; Taken</span>
					{/if}
				</div>

				{#if beaconError}
					<span class="field-error">{beaconError}</span>
				{/if}

				<div class="beacon-preview">
					{#if $onboarding.beaconName}
						Your apps will be at: <strong>https://{$onboarding.beaconName}.wopr.systems</strong>
					{:else}
						Your apps will be at: <strong>https://[name].wopr.systems</strong>
					{/if}
				</div>

				<p class="field-hint">
					You can connect a custom domain later (e.g., cloud.yourname.com)
				</p>
			</div>
		</div>

		<!-- Provider section -->
		<div class="config-section">
			<h2>Server Provider</h2>
			<p class="section-description">Where should we host your Beacon?</p>

			<div class="provider-grid">
				{#each providerOptions as provider}
					<button
						class="provider-card {$onboarding.provider === provider.id ? 'selected' : ''}"
						on:click={() => selectProvider(provider.id)}
					>
						<div class="provider-header">
							<span class="provider-name">{provider.name}</span>
							{#if provider.recommended}
								<span class="recommended-badge">Recommended</span>
							{/if}
						</div>
						<p class="provider-description">{provider.description}</p>
						<span class="provider-price">{provider.priceRange}</span>

						{#if $onboarding.provider === provider.id}
							<div class="selected-check">&#10003;</div>
						{/if}
					</button>
				{/each}
			</div>

			<p class="provider-note">
				VPS hosting is billed separately by your chosen provider. We'll guide you through setup.
			</p>
		</div>
	</div>

	<!-- Bundle reminder -->
	<div class="bundle-reminder">
		<span class="reminder-label">Your Bundle:</span>
		<span class="reminder-bundle">{bundleInfo[$onboarding.bundle]?.name}</span>
		<span class="reminder-price">{$formattedPrice}/mo</span>
		<span class="reminder-email">for {$onboarding.email}</span>
	</div>

	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">←</span>
			Back
		</button>
		<button class="btn btn-primary" on:click={handleContinue} disabled={!$canProceed}>
			{$needsAdditionalUsers ? 'Add Users' : 'Review Order'}
			<span class="arrow">→</span>
		</button>
	</div>
</div>

<style>
	.step-container {
		animation: fadeIn 0.3s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; transform: translateY(10px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.step-header {
		text-align: center;
		margin-bottom: 2rem;
	}

	.step-header h1 {
		font-size: 2rem;
		margin-bottom: 0.5rem;
	}

	.subtitle {
		color: var(--theme-text-muted);
		font-size: 1.1rem;
	}

	.config-grid {
		display: grid;
		gap: 2rem;
	}

	.config-section {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
	}

	.config-section h2 {
		font-size: 1.25rem;
		margin-bottom: 0.25rem;
	}

	.section-description {
		color: var(--theme-text-muted);
		margin-bottom: 1.25rem;
	}

	/* Beacon input */
	.beacon-input-wrapper {
		max-width: 500px;
	}

	.beacon-input-container {
		display: flex;
		align-items: center;
		gap: 0;
		position: relative;
	}

	.beacon-input-container input {
		flex: 1;
		padding: 0.875rem 1rem;
		font-size: 1.1rem;
		font-weight: 500;
		background: var(--theme-bg);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius) 0 0 var(--theme-radius);
		color: var(--theme-text);
		transition: border-color 0.2s;
	}

	.beacon-input-container input:focus {
		outline: none;
		border-color: var(--theme-primary);
	}

	.beacon-input-container input.error {
		border-color: var(--theme-error);
	}

	.beacon-input-container input.success {
		border-color: var(--theme-success);
	}

	.beacon-domain {
		padding: 0.875rem 1rem;
		background: var(--theme-border);
		color: var(--theme-text-muted);
		font-size: 1.1rem;
		font-weight: 500;
		border-radius: 0 var(--theme-radius) var(--theme-radius) 0;
	}

	.checking,
	.available,
	.unavailable {
		position: absolute;
		right: -6rem;
		font-size: 0.85rem;
		font-weight: 500;
	}

	.checking { color: var(--theme-text-muted); }
	.available { color: var(--theme-success); }
	.unavailable { color: var(--theme-error); }

	.beacon-preview {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: var(--theme-bg);
		border-radius: var(--theme-radius);
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.beacon-preview strong {
		color: var(--theme-primary);
	}

	.field-error {
		display: block;
		color: var(--theme-error);
		font-size: 0.85rem;
		margin-top: 0.5rem;
	}

	.field-hint {
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin-top: 0.75rem;
	}

	/* Provider grid */
	.provider-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.provider-card {
		background: var(--theme-bg);
		border: 2px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.25rem;
		text-align: left;
		cursor: pointer;
		transition: all 0.2s;
		position: relative;
	}

	.provider-card:hover {
		border-color: var(--theme-primary);
	}

	.provider-card.selected {
		border-color: var(--theme-primary);
		background: var(--theme-surface-hover);
	}

	.provider-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.provider-name {
		font-weight: 600;
	}

	.recommended-badge {
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		padding: 0.2rem 0.5rem;
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
		border-radius: var(--theme-radius);
	}

	.provider-description {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin-bottom: 0.75rem;
	}

	.provider-price {
		font-weight: 600;
		color: var(--theme-primary);
	}

	.selected-check {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		width: 24px;
		height: 24px;
		background: var(--theme-success);
		color: #fff;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.85rem;
	}

	.provider-note {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		font-style: italic;
	}

	/* Bundle reminder */
	.bundle-reminder {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		margin-top: 2rem;
		padding: 1rem;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		flex-wrap: wrap;
	}

	.reminder-label {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.reminder-bundle {
		font-weight: 600;
	}

	.reminder-price {
		color: var(--theme-primary);
		font-weight: 700;
	}

	.reminder-email {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.step-actions {
		display: flex;
		justify-content: space-between;
		margin-top: 2rem;
		gap: 1rem;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.875rem 1.5rem;
		border-radius: var(--theme-radius);
		font-weight: 600;
		font-size: 1rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.btn-primary {
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
	}

	.btn-primary:hover:not(:disabled) {
		background: var(--theme-primary-hover);
	}

	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-secondary {
		background: var(--theme-surface);
		color: var(--theme-text);
		border: 1px solid var(--theme-border);
	}

	.btn-secondary:hover {
		background: var(--theme-surface-hover);
	}

	.arrow {
		font-size: 1rem;
	}

	@media (max-width: 600px) {
		.beacon-input-container {
			flex-direction: column;
			align-items: stretch;
		}

		.beacon-input-container input {
			border-radius: var(--theme-radius) var(--theme-radius) 0 0;
		}

		.beacon-domain {
			border-radius: 0 0 var(--theme-radius) var(--theme-radius);
			text-align: center;
		}

		.checking,
		.available,
		.unavailable {
			position: static;
			display: block;
			margin-top: 0.5rem;
		}

		.step-actions {
			flex-direction: column-reverse;
		}

		.btn {
			width: 100%;
			justify-content: center;
		}
	}
</style>
