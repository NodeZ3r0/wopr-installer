<script>
	import { onMount } from 'svelte';
	import { modules, instance, loading, error } from '$lib/stores.js';
	import { getModules, getInstanceStatus, startTrial } from '$lib/api.js';
	import ModuleCard from '$lib/components/ModuleCard.svelte';
	import { notify } from '$lib/stores.js';

	onMount(async () => {
		$loading = true;
		try {
			const [modulesData, instanceData] = await Promise.all([
				getModules(),
				getInstanceStatus()
			]);
			$modules = modulesData;
			$instance = instanceData;
		} catch (e) {
			$error = e.message;
		} finally {
			$loading = false;
		}
	});

	// Group modules by status
	$: includedModules = $modules.filter(m => m.status === 'running' || m.status === 'included');
	$: trialModules = $modules.filter(m => m.status === 'trial');
	$: availableTrials = $modules.filter(m => m.status === 'trial_available');
	$: addonModules = $modules.filter(m => m.status === 'addon_available');

	async function handleStartTrial(event) {
		const moduleId = event.detail;
		try {
			await startTrial(moduleId);
			notify(`Trial started for ${moduleId}`, 'success');
			// Refresh modules
			$modules = await getModules();
		} catch (e) {
			notify(e.message, 'error');
		}
	}
</script>

<svelte:head>
	<title>Modules | WOPR</title>
</svelte:head>

<div class="modules-page">
	<header>
		<h1>Modules</h1>
		<p class="text-muted">Manage your installed and available applications</p>
	</header>

	{#if $loading}
		<div class="loading">Loading modules...</div>
	{:else if $error}
		<div class="error card">
			<h3>Error</h3>
			<p>{$error}</p>
		</div>
	{:else}
		<!-- Included Modules -->
		<section>
			<h2>Installed Modules</h2>
			<p class="text-muted section-desc">
				These modules are included in your {$instance.bundle || 'Personal'} bundle
			</p>
			<div class="grid grid-3">
				{#each includedModules as module}
					<ModuleCard {module} />
				{:else}
					<p class="text-muted">No modules installed yet.</p>
				{/each}
			</div>
		</section>

		<!-- Active Trials -->
		{#if trialModules.length > 0}
			<section>
				<h2>Active Trials</h2>
				<p class="text-muted section-desc">
					You're trying these modules for free
				</p>
				<div class="grid grid-3">
					{#each trialModules as module}
						<ModuleCard {module} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- Available Trials -->
		{#if availableTrials.length > 0}
			<section>
				<h2>Try for Free</h2>
				<p class="text-muted section-desc">
					Start a free 90-day trial of these modules
				</p>
				<div class="grid grid-3">
					{#each availableTrials as module}
						<ModuleCard {module} on:start-trial={handleStartTrial} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- Paid Add-ons -->
		{#if addonModules.length > 0}
			<section>
				<h2>Add-on Modules</h2>
				<p class="text-muted section-desc">
					Expand your suite with these premium modules
				</p>
				<div class="grid grid-3">
					{#each addonModules as module}
						<ModuleCard {module} />
					{/each}
				</div>
			</section>
		{/if}
	{/if}
</div>

<style>
	.modules-page {
		max-width: 1000px;
	}

	header {
		margin-bottom: 2rem;
	}

	header h1 {
		margin-bottom: 0.25rem;
	}

	section {
		margin-bottom: 3rem;
	}

	section h2 {
		margin-bottom: 0.5rem;
	}

	.section-desc {
		margin-bottom: 1rem;
		font-size: 0.9rem;
	}

	.loading {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}
</style>
