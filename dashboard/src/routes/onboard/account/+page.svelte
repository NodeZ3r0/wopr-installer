<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		tierLabels,
		formattedPrice,
		canProceed,
		needsAdditionalUsers,
		nextStep,
		prevStep,
		addUser,
		removeUser
	} from '$lib/stores/onboarding.js';

	let emailError = '';
	let passwordError = '';
	let showPassword = false;
	let beaconError = '';
	let checkingBeacon = false;
	let debounceTimer;

	// Additional users
	let newUserEmail = '';
	let newUserName = '';
	let userEmailError = '';

	onMount(() => {
		if (!$onboarding.bundle || !$onboarding.tier) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 3 }));
	});

	$: bundleMeta = bundleInfo[$onboarding.bundle] || {};
	$: maxUsers = bundleMeta.maxUsers || 1;
	$: showUsersSection = $needsAdditionalUsers;
	$: remainingSlots = maxUsers === -1 ? Infinity : maxUsers - 1 - $onboarding.additionalUsers.length;

	function validateEmail(email) {
		const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		return re.test(email);
	}

	function handleEmailChange(e) {
		const email = e.target.value;
		onboarding.update(o => ({ ...o, email }));
		emailError = email && !validateEmail(email) ? 'Please enter a valid email address' : '';
	}

	function handlePasswordChange(e) {
		const password = e.target.value;
		onboarding.update(o => ({ ...o, password }));
		passwordError = password.length > 0 && password.length < 8 ? 'Password must be at least 8 characters' : '';
	}

	// Beacon name
	function sanitizeBeaconName(name) {
		return name.toLowerCase().replace(/[^a-z0-9-]/g, '').replace(/^-|-$/g, '');
	}

	async function checkBeaconAvailability(name) {
		if (!name || name.length < 3) {
			onboarding.update(o => ({ ...o, beaconAvailable: null }));
			return;
		}
		checkingBeacon = true;
		try {
			const resp = await fetch('/api/v1/onboard/validate-beacon', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name }),
			});
			if (resp.ok) {
				const data = await resp.json();
				onboarding.update(o => ({ ...o, beaconAvailable: data.available }));
				beaconError = data.available ? '' : (data.message || 'This name is not available');
			} else {
				onboarding.update(o => ({ ...o, beaconAvailable: null }));
				beaconError = 'Could not check availability';
			}
		} catch {
			// Fallback for dev: simulate
			const reserved = ['www', 'api', 'admin', 'mail', 'smtp', 'ftp', 'test', 'demo'];
			const isAvailable = !reserved.includes(name);
			onboarding.update(o => ({ ...o, beaconAvailable: isAvailable }));
			beaconError = isAvailable ? '' : 'This name is not available';
		} finally {
			checkingBeacon = false;
		}
	}

	function handleBeaconInput(e) {
		const sanitized = sanitizeBeaconName(e.target.value);
		onboarding.update(o => ({ ...o, beaconName: sanitized, beaconAvailable: null }));
		beaconError = '';
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => checkBeaconAvailability(sanitized), 500);
	}

	// Additional users
	function handleAddUser() {
		userEmailError = '';
		if (!newUserEmail || !newUserName) {
			userEmailError = 'Please enter both name and email';
			return;
		}
		if (!validateEmail(newUserEmail)) {
			userEmailError = 'Please enter a valid email address';
			return;
		}
		const isDuplicate =
			newUserEmail.toLowerCase() === $onboarding.email.toLowerCase() ||
			$onboarding.additionalUsers.some(u => u.email.toLowerCase() === newUserEmail.toLowerCase());
		if (isDuplicate) {
			userEmailError = 'This email is already added';
			return;
		}
		if (remainingSlots <= 0) {
			userEmailError = `Maximum ${maxUsers} users for this bundle`;
			return;
		}
		addUser(newUserEmail, newUserName);
		newUserEmail = '';
		newUserName = '';
	}

	function handleUserKeydown(e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleAddUser();
		}
	}

	function handleBack() {
		prevStep();
		goto('/onboard/plan');
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
			goto('/onboard/checkout');
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter' && $canProceed) {
			handleContinue();
		}
	}
</script>

<svelte:head>
	<title>Create Your Account - WOPR</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<span class="step-badge">Step 3 of 4</span>
		<h1>Create your account</h1>
		<p class="subtitle">Set up your login and pick a name for your server</p>
	</div>

	<div class="form-container">
		<!-- Account fields -->
		<div class="form-card">
			<h2 class="section-title">Your Info</h2>

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
				<span class="field-hint">We'll send your welcome guide and login info here</span>
			</div>

			<div class="form-group">
				<label for="password">Create Password</label>
				<div class="password-input">
					<input
						type={showPassword ? 'text' : 'password'}
						id="password"
						placeholder="At least 8 characters"
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
			</div>
		</div>

		<!-- Beacon name -->
		<div class="form-card">
			<h2 class="section-title">Pick Your Server Name</h2>
			<p class="section-desc">This becomes your personal web address</p>

			<div class="beacon-input-wrapper">
				<div class="beacon-input-container">
					<input
						type="text"
						id="beacon-name"
						placeholder="myname"
						value={$onboarding.beaconName}
						on:input={handleBeaconInput}
						class:error={beaconError}
						class:success={$onboarding.beaconAvailable === true}
						maxlength="32"
					/>
					<span class="beacon-domain">.wopr.systems</span>
				</div>

				<div class="beacon-status">
					{#if checkingBeacon}
						<span class="checking">Checking...</span>
					{:else if $onboarding.beaconAvailable === true}
						<span class="available">&#10003; Available!</span>
					{:else if $onboarding.beaconAvailable === false}
						<span class="unavailable">&#10007; Taken</span>
					{/if}
				</div>

				{#if beaconError}
					<span class="field-error">{beaconError}</span>
				{/if}

				{#if $onboarding.beaconName}
					<div class="beacon-preview">
						Your apps will live at: <strong>https://{$onboarding.beaconName}.wopr.systems</strong>
					</div>
				{/if}

				<p class="field-hint">You can connect your own domain later (like cloud.yourname.com)</p>
			</div>
		</div>

		<!-- Additional users (only for multi-user bundles) -->
		{#if showUsersSection}
			<div class="form-card">
				<h2 class="section-title">Add Team Members</h2>
				<p class="section-desc">
					{#if maxUsers === -1}
						Add as many users as you need
					{:else}
						You can add up to {maxUsers - 1} more people
					{/if}
				</p>

				<!-- Existing users -->
				{#if $onboarding.additionalUsers.length > 0}
					<div class="user-list">
						{#each $onboarding.additionalUsers as user, index}
							<div class="user-card">
								<div class="user-info">
									<span class="user-name">{user.name}</span>
									<span class="user-email">{user.email}</span>
								</div>
								<button class="remove-btn" on:click={() => removeUser(index)}>
									Remove
								</button>
							</div>
						{/each}
					</div>
				{/if}

				<!-- Add form -->
				{#if remainingSlots > 0}
					<div class="add-user-row">
						<input
							type="text"
							placeholder="Name"
							bind:value={newUserName}
							on:keydown={handleUserKeydown}
						/>
						<input
							type="email"
							placeholder="Email"
							bind:value={newUserEmail}
							on:keydown={handleUserKeydown}
							class:error={userEmailError}
						/>
						<button class="btn-add" on:click={handleAddUser}>Add</button>
					</div>
					{#if userEmailError}
						<span class="field-error">{userEmailError}</span>
					{/if}
				{/if}

				<p class="field-hint">You can always add more users later from your dashboard.</p>
			</div>
		{/if}

		<!-- Selection reminder -->
		<div class="bundle-reminder">
			<span class="reminder-bundle">{bundleMeta.name}</span>
			<span class="reminder-tier">{tierLabels[$onboarding.tier]}</span>
			<span class="reminder-price">{$formattedPrice}/mo</span>
		</div>
	</div>

	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">&larr;</span>
			Back
		</button>
		<button class="btn btn-primary" on:click={handleContinue} disabled={!$canProceed}>
			Review Your Order
			<span class="arrow">&rarr;</span>
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

	.step-badge {
		display: inline-block;
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--theme-primary);
		background: var(--theme-primary-subtle);
		padding: 0.3rem 0.75rem;
		border-radius: var(--theme-radius);
		margin-bottom: 0.75rem;
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
		max-width: 520px;
		margin: 0 auto;
	}

	.form-card {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
		margin-bottom: 1.25rem;
	}

	.section-title {
		font-size: 1.1rem;
		margin-bottom: 0.25rem;
	}

	.section-desc {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}

	.form-group {
		margin-bottom: 1.25rem;
	}

	.form-group:last-child {
		margin-bottom: 0;
	}

	.form-group label {
		display: block;
		font-weight: 500;
		margin-bottom: 0.5rem;
	}

	.form-group input,
	.add-user-row input {
		width: 100%;
		padding: 0.875rem 1rem;
		font-size: 1rem;
		background: var(--theme-bg);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		color: var(--theme-text);
		transition: border-color 0.2s;
	}

	.form-group input:focus,
	.add-user-row input:focus {
		outline: none;
		border-color: var(--theme-primary);
	}

	.form-group input.error,
	.add-user-row input.error {
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

	/* Beacon */
	.beacon-input-wrapper {
		max-width: 100%;
	}

	.beacon-input-container {
		display: flex;
		align-items: center;
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
		white-space: nowrap;
	}

	.beacon-status {
		margin-top: 0.5rem;
		min-height: 1.25rem;
	}

	.checking { color: var(--theme-text-muted); font-size: 0.85rem; }
	.available { color: var(--theme-success); font-size: 0.85rem; font-weight: 500; }
	.unavailable { color: var(--theme-error); font-size: 0.85rem; font-weight: 500; }

	.beacon-preview {
		margin-top: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--theme-bg);
		border-radius: var(--theme-radius);
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.beacon-preview strong {
		color: var(--theme-primary);
	}

	/* Users section */
	.user-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.user-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		background: var(--theme-bg);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
	}

	.user-info {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.user-name { font-weight: 600; font-size: 0.9rem; }
	.user-email { font-size: 0.8rem; color: var(--theme-text-muted); }

	.remove-btn {
		padding: 0.35rem 0.75rem;
		background: transparent;
		border: 1px solid var(--theme-error);
		color: var(--theme-error);
		border-radius: var(--theme-radius);
		font-size: 0.8rem;
		cursor: pointer;
	}

	.remove-btn:hover {
		background: var(--theme-error);
		color: #fff;
	}

	.add-user-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.btn-add {
		padding: 0.875rem 1.25rem;
		background: var(--theme-success);
		color: #fff;
		border: none;
		border-radius: var(--theme-radius);
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
	}

	/* Reminder */
	.bundle-reminder {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: 1rem;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		flex-wrap: wrap;
	}

	.reminder-bundle { font-weight: 600; }
	.reminder-tier {
		font-size: 0.85rem;
		padding: 0.2rem 0.6rem;
		background: var(--theme-border);
		border-radius: var(--theme-radius);
	}
	.reminder-price { color: var(--theme-primary); font-weight: 700; }

	/* Actions */
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
			padding: 1.25rem;
		}

		.beacon-input-container {
			flex-direction: column;
		}

		.beacon-input-container input {
			border-radius: var(--theme-radius) var(--theme-radius) 0 0;
		}

		.beacon-domain {
			border-radius: 0 0 var(--theme-radius) var(--theme-radius);
			text-align: center;
			width: 100%;
		}

		.add-user-row {
			flex-direction: column;
		}

		.btn-add {
			width: 100%;
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
