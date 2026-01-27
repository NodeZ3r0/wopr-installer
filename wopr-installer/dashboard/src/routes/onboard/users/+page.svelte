<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		onboarding,
		bundleInfo,
		formattedPrice,
		canProceed,
		needsAdditionalUsers,
		nextStep,
		prevStep,
		addUser,
		removeUser
	} from '$lib/stores/onboarding.js';

	let newUserEmail = '';
	let newUserName = '';
	let emailError = '';

	onMount(() => {
		// Redirect if bundle doesn't support additional users
		if (!$needsAdditionalUsers) {
			goto('/onboard/checkout');
			return;
		}
		// Redirect if no beacon configured
		if (!$onboarding.beaconName) {
			goto('/onboard');
			return;
		}
		onboarding.update(o => ({ ...o, currentStep: 4 }));
	});

	$: bundleMeta = bundleInfo[$onboarding.bundle] || {};
	$: maxUsers = bundleMeta.maxUsers || 1;
	$: remainingSlots = maxUsers === -1 ? Infinity : maxUsers - 1 - $onboarding.additionalUsers.length;

	function validateEmail(email) {
		const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		return re.test(email);
	}

	function handleAddUser() {
		emailError = '';

		if (!newUserEmail || !newUserName) {
			emailError = 'Please enter both name and email';
			return;
		}

		if (!validateEmail(newUserEmail)) {
			emailError = 'Please enter a valid email address';
			return;
		}

		// Check for duplicates
		const isDuplicate =
			newUserEmail.toLowerCase() === $onboarding.email.toLowerCase() ||
			$onboarding.additionalUsers.some(u => u.email.toLowerCase() === newUserEmail.toLowerCase());

		if (isDuplicate) {
			emailError = 'This email is already added';
			return;
		}

		if (remainingSlots <= 0) {
			emailError = `Maximum ${maxUsers} users allowed for this bundle`;
			return;
		}

		addUser(newUserEmail, newUserName);
		newUserEmail = '';
		newUserName = '';
	}

	function handleRemoveUser(index) {
		removeUser(index);
	}

	function handleBack() {
		prevStep();
		goto('/onboard/beacon');
	}

	function handleContinue() {
		nextStep();
		goto('/onboard/checkout');
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleAddUser();
		}
	}
</script>

<svelte:head>
	<title>Add Team Members - WOPR Onboarding</title>
</svelte:head>

<div class="step-container">
	<div class="step-header">
		<h1>Add Team Members</h1>
		<p class="subtitle">
			{#if maxUsers === -1}
				Add unlimited users to your {bundleMeta.name}
			{:else}
				Add up to {maxUsers - 1} additional users to your {bundleMeta.name}
			{/if}
		</p>
	</div>

	<div class="users-container">
		<!-- Admin user (read-only) -->
		<div class="user-list">
			<div class="user-card admin">
				<div class="user-info">
					<span class="user-name">{$onboarding.name}</span>
					<span class="user-email">{$onboarding.email}</span>
				</div>
				<span class="admin-badge">Admin (You)</span>
			</div>

			<!-- Additional users -->
			{#each $onboarding.additionalUsers as user, index}
				<div class="user-card">
					<div class="user-info">
						<span class="user-name">{user.name}</span>
						<span class="user-email">{user.email}</span>
					</div>
					<button class="remove-btn" on:click={() => handleRemoveUser(index)}>
						Remove
					</button>
				</div>
			{/each}
		</div>

		<!-- Add user form -->
		{#if remainingSlots > 0}
			<div class="add-user-form">
				<h3>Add a Team Member</h3>
				<p class="slots-remaining">
					{#if maxUsers === -1}
						Unlimited slots available
					{:else}
						{remainingSlots} slot{remainingSlots !== 1 ? 's' : ''} remaining
					{/if}
				</p>

				<div class="form-row">
					<div class="form-group">
						<label for="user-name">Name</label>
						<input
							type="text"
							id="user-name"
							placeholder="Jane Smith"
							bind:value={newUserName}
							on:keydown={handleKeydown}
						/>
					</div>
					<div class="form-group">
						<label for="user-email">Email</label>
						<input
							type="email"
							id="user-email"
							placeholder="jane@example.com"
							bind:value={newUserEmail}
							on:keydown={handleKeydown}
							class:error={emailError}
						/>
					</div>
					<button class="btn btn-add" on:click={handleAddUser}>
						Add
					</button>
				</div>

				{#if emailError}
					<span class="field-error">{emailError}</span>
				{/if}

				<p class="add-hint">
					They'll receive an invitation email with login instructions
				</p>
			</div>
		{:else}
			<div class="slots-full">
				<p>All user slots are filled for this bundle.</p>
				<p class="upgrade-hint">Need more users? Consider upgrading to a larger bundle.</p>
			</div>
		{/if}

		<!-- Summary -->
		<div class="user-summary">
			<div class="summary-row">
				<span>Total Users:</span>
				<strong>{1 + $onboarding.additionalUsers.length}</strong>
			</div>
			<div class="summary-row">
				<span>Bundle:</span>
				<strong>{bundleMeta.name}</strong>
			</div>
			<div class="summary-row">
				<span>Monthly Cost:</span>
				<strong class="price">{$formattedPrice}/mo</strong>
			</div>
		</div>

		<p class="skip-note">
			You can add more users later from your Beacon's admin dashboard.
		</p>
	</div>

	<div class="step-actions">
		<button class="btn btn-secondary" on:click={handleBack}>
			<span class="arrow">←</span>
			Back
		</button>
		<button class="btn btn-primary" on:click={handleContinue}>
			Review Order
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

	.users-container {
		max-width: 600px;
		margin: 0 auto;
	}

	/* User list */
	.user-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 2rem;
	}

	.user-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.25rem;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
	}

	.user-card.admin {
		background: var(--theme-primary-subtle);
		border-color: var(--theme-primary);
	}

	.user-info {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.user-name {
		font-weight: 600;
	}

	.user-email {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.admin-badge {
		font-size: 0.8rem;
		font-weight: 600;
		padding: 0.25rem 0.75rem;
		background: var(--theme-primary);
		color: var(--theme-text-on-primary);
		border-radius: var(--theme-radius);
	}

	.remove-btn {
		padding: 0.5rem 1rem;
		background: transparent;
		border: 1px solid var(--theme-error);
		color: var(--theme-error);
		border-radius: var(--theme-radius);
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.remove-btn:hover {
		background: var(--theme-error);
		color: #fff;
	}

	/* Add user form */
	.add-user-form {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.5rem;
		margin-bottom: 1.5rem;
	}

	.add-user-form h3 {
		font-size: 1.1rem;
		margin-bottom: 0.25rem;
	}

	.slots-remaining {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}

	.form-row {
		display: flex;
		gap: 1rem;
		align-items: flex-end;
	}

	.form-group {
		flex: 1;
	}

	.form-group label {
		display: block;
		font-weight: 500;
		font-size: 0.9rem;
		margin-bottom: 0.5rem;
	}

	.form-group input {
		width: 100%;
		padding: 0.75rem 1rem;
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

	.btn-add {
		padding: 0.75rem 1.5rem;
		background: var(--theme-success);
		color: #fff;
		border: none;
		border-radius: var(--theme-radius);
		font-weight: 600;
		cursor: pointer;
		transition: opacity 0.2s;
	}

	.btn-add:hover {
		opacity: 0.9;
	}

	.field-error {
		display: block;
		color: var(--theme-error);
		font-size: 0.85rem;
		margin-top: 0.75rem;
	}

	.add-hint {
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin-top: 0.75rem;
	}

	/* Slots full */
	.slots-full {
		text-align: center;
		padding: 2rem;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		margin-bottom: 1.5rem;
	}

	.upgrade-hint {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		margin-top: 0.5rem;
	}

	/* Summary */
	.user-summary {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: var(--theme-radius);
		padding: 1.25rem;
		margin-bottom: 1rem;
	}

	.summary-row {
		display: flex;
		justify-content: space-between;
		padding: 0.5rem 0;
	}

	.summary-row:not(:last-child) {
		border-bottom: 1px solid var(--theme-border);
	}

	.summary-row .price {
		color: var(--theme-primary);
	}

	.skip-note {
		text-align: center;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

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

	.btn-primary:hover {
		background: var(--theme-primary-hover);
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
		.form-row {
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
