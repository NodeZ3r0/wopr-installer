<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		formattedPrice,
		canProceed,
		nextStep,
		prevStep
	} from '$lib/stores/onboarding.js';

	let emailError = '';
	let passwordError = '';
	let showPassword = false;

	onMount(() => {
		// Redirect if no bundle selected
		if (!$onboarding.bundle) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 2 }));
	});

	function validateEmail(email) {
		const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		return re.test(email);
	}

	function handleEmailChange(e) {
		const email = e.target.value;
		onboarding.update(o => ({ ...o, email }));

		if (email && !validateEmail(email)) {
			emailError = 'Please enter a valid email address';
		} else {
			emailError = '';
		}
	}

	function handlePasswordChange(e) {
		const password = e.target.value;
		onboarding.update(o => ({ ...o, password }));

		if (password.length > 0 && password.length < 8) {
			passwordError = 'Password must be at least 8 characters';
		} else {
			passwordError = '';
		}
	}

	function handleBack() {
		prevStep();
		goto('/onboard');
	}

	function handleContinue() {
		if (!validateEmail($onboarding.email)) {
			emailError = 'Please enter a valid email address';
			return;
		}
		if ($onboarding.password.length < 8) {
			passwordError = 'Password must be at least 8 characters';
			return;
		}

		if ($canProceed) {
			nextStep();
			goto('/onboard/beacon');
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter' && $canProceed) {
			handleContinue();
		}
	}
</script>

<svelte:head>
	<title>Create Your Account - WOPR Onboarding</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<h1>Create Your Account</h1>
		<p class="subtitle">This will be your admin account for your WOPR Beacon</p>
	</div>

	<div class="form-container">
		<div class="form-card">
			<div class="form-group">
				<label for="name">Full Name</label>
				<input
					type="text"
					id="name"
					placeholder="John Smith"
					bind:value={$onboarding.name}
					on:keydown={handleKeydown}
					autocomplete="name"
				/>
			</div>

			<div class="form-group">
				<label for="email">Email Address</label>
				<input
					type="email"
					id="email"
					placeholder="you@example.com"
					value={$onboarding.email}
					on:input={handleEmailChange}
					on:keydown={handleKeydown}
					class:error={emailError}
					autocomplete="email"
				/>
				{#if emailError}
					<span class="field-error">{emailError}</span>
				{/if}
				<span class="field-hint">We'll send your welcome guide and login credentials here</span>
			</div>

			<div class="form-group">
				<label for="password">Create Password</label>
				<div class="password-input">
					<input
						type={showPassword ? 'text' : 'password'}
						id="password"
						placeholder="Minimum 8 characters"
						value={$onboarding.password}
						on:input={handlePasswordChange}
						on:keydown={handleKeydown}
						class:error={passwordError}
						autocomplete="new-password"
					/>
					<button
						type="button"
						class="toggle-password"
						on:click={() => (showPassword = !showPassword)}
						tabindex="-1"
					>
						{showPassword ? 'Hide' : 'Show'}
					</button>
				</div>
				{#if passwordError}
					<span class="field-error">{passwordError}</span>
				{/if}
				<span class="field-hint">Use a strong password you don't use elsewhere</span>
			</div>
		</div>

		<!-- Selected bundle reminder -->
		<div class="bundle-reminder">
			<span class="reminder-label">Selected Bundle:</span>
			<span class="reminder-bundle">{bundleInfo[$onboarding.bundle]?.name}</span>
			<span class="reminder-price">{$formattedPrice}/mo</span>
		</div>
	</div>

	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">←</span>
			Back
		</button>
		<button class="btn btn-primary" on:click={handleContinue} disabled={!$canProceed}>
			Continue
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

	.form-container {
		max-width: 480px;
		margin: 0 auto;
	}

	.form-card {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 2rem;
	}

	.form-group {
		margin-bottom: 1.5rem;
	}

	.form-group:last-child {
		margin-bottom: 0;
	}

	.form-group label {
		display: block;
		font-weight: 500;
		margin-bottom: 0.5rem;
		color: var(--theme-text);
	}

	.form-group input {
		width: 100%;
		padding: 0.875rem 1rem;
		font-size: 1rem;
		background: var(--theme-bg);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		color: var(--theme-text);
		transition: border-color 0.2s;
	}

	.form-group input:focus {
		outline: none;
		border-color: var(--theme-primary);
	}

	.form-group input.error {
		border-color: var(--theme-error);
	}

	.password-input {
		position: relative;
	}

	.password-input input {
		padding-right: 4rem;
	}

	.toggle-password {
		position: absolute;
		right: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		background: none;
		border: none;
		color: var(--theme-primary);
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
	}

	.toggle-password:hover {
		color: var(--theme-primary-hover);
	}

	.field-error {
		display: block;
		color: var(--theme-error);
		font-size: 0.85rem;
		margin-top: 0.5rem;
	}

	.field-hint {
		display: block;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin-top: 0.5rem;
	}

	.bundle-reminder {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		margin-top: 1.5rem;
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

	@media (max-width: 480px) {
		.form-card {
			padding: 1.5rem;
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
