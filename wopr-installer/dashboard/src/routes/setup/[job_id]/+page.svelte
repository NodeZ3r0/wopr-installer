<script>
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import SetupSlides from '$lib/components/SetupSlides.svelte';

	const jobId = $page.params.job_id;

	let progress = 0;
	let currentStep = 0;
	let status = 'connecting';
	let error = null;
	let beaconUrl = '';
	let dashboardUrl = '';
	let instanceIp = '';
	let customDomain = '';
	let eventSource = null;
	let currentModule = '';

	// Steps with ASCII icons instead of emojis
	const steps = [
		{ id: 'payment', label: 'Payment Received', icon: '[$]', description: 'Transaction verified' },
		{ id: 'server', label: 'Creating Server', icon: '[#]', description: 'Spawning cloud instance' },
		{ id: 'dns', label: 'Configuring DNS', icon: '[@]', description: 'Mapping your domain' },
		{ id: 'install', label: 'Installing WOPR', icon: '[*]', description: 'Deploying modules' },
		{ id: 'configure', label: 'Final Setup', icon: '[~]', description: 'Creating accounts' },
		{ id: 'ready', label: 'Online', icon: '[>]', description: 'Beacon operational' },
	];

	onMount(() => {
		connectToStream();
	});

	onDestroy(() => {
		if (eventSource) {
			eventSource.close();
		}
	});

	function connectToStream() {
		status = 'connecting';
		eventSource = new EventSource(`/api/v1/provisioning/${jobId}/stream`);

		eventSource.onopen = () => {
			status = 'connected';
		};

		eventSource.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data);
				handleUpdate(data);
			} catch (e) {
				console.error('Failed to parse SSE data:', e);
			}
		};

		eventSource.onerror = (e) => {
			console.error('SSE error:', e);
			status = 'error';
			setTimeout(() => {
				if (eventSource) eventSource.close();
				connectToStream();
			}, 5000);
		};
	}

	function handleUpdate(data) {
		if (data.progress !== undefined) {
			progress = data.progress;
		}

		if (data.step !== undefined) {
			currentStep = data.step;
		}

		if (data.current_module) {
			currentModule = data.current_module;
		}

		if (data.status === 'complete') {
			status = 'complete';
			beaconUrl = data.beacon_url || '';
			dashboardUrl = data.dashboard_url || '';
			instanceIp = data.instance_ip || '';
			customDomain = data.custom_domain || '';
			if (eventSource) eventSource.close();
		}

		if (data.status === 'error') {
			status = 'error';
			error = data.error || 'An unknown error occurred';
			if (eventSource) eventSource.close();
		}
	}

	function goToDashboard() {
		if (dashboardUrl) {
			window.location.href = dashboardUrl;
		}
	}

	$: circumference = 2 * Math.PI * 54;
	$: strokeDashoffset = circumference - (progress / 100) * circumference;
</script>

<svelte:head>
	<title>Deploying Beacon - WOPR</title>
</svelte:head>

<div class="setup-page">
	<div class="scanlines-overlay"></div>

	<header class="page-header">
		<div class="terminal-title">WOPR://beacon/deploy/{jobId}</div>
		<div class="connection-status" class:connected={status === 'connected'} class:error={status === 'error'}>
			{#if status === 'connecting'}
				[CONNECTING...]
			{:else if status === 'connected'}
				[STREAM ACTIVE]
			{:else if status === 'complete'}
				[COMPLETE]
			{:else if status === 'error'}
				[CONNECTION ERROR]
			{/if}
		</div>
	</header>

	<div class="setup-grid">
		<!-- Left: Educational Slides -->
		<div class="slides-panel">
			{#if status !== 'complete'}
				<SetupSlides {currentStep} {progress} />
			{:else}
				<div class="completion-panel">
					<div class="ascii-beacon">
<pre>
      *
     /|\
    / | \
   /  |  \
  /___|___\
     |||
  ___|||___
 |  WOPR  |
 |_________|
   BEACON
   ONLINE
</pre>
					</div>
					<h2 class="complete-title">DEPLOYMENT SUCCESSFUL</h2>
					<p class="complete-subtitle">All systems nominal</p>
				</div>
			{/if}
		</div>

		<!-- Right: Progress Panel -->
		<div class="progress-panel">
			<div class="panel-header">
				<span class="panel-title">DEPLOYMENT STATUS</span>
			</div>

			<!-- Compact Progress Ring -->
			<div class="progress-ring-container">
				<svg class="progress-ring" viewBox="0 0 120 120">
					<circle class="ring-bg" cx="60" cy="60" r="54" fill="none" stroke-width="6" />
					<circle
						class="ring-fill"
						cx="60"
						cy="60"
						r="54"
						fill="none"
						stroke-width="6"
						stroke-dasharray={circumference}
						stroke-dashoffset={strokeDashoffset}
						transform="rotate(-90 60 60)"
					/>
				</svg>
				<div class="ring-text">
					<span class="ring-percentage">{Math.round(progress)}%</span>
				</div>
			</div>

			<!-- Step List -->
			<div class="steps-list">
				{#each steps as step, index}
					<div
						class="step-row"
						class:completed={index < currentStep}
						class:active={index === currentStep && status !== 'complete'}
						class:pending={index > currentStep}
						class:final={status === 'complete' && index === 5}
					>
						<span class="step-icon">
							{#if index < currentStep || (status === 'complete' && index === 5)}
								[OK]
							{:else if index === currentStep && status !== 'complete'}
								{step.icon}
							{:else}
								[--]
							{/if}
						</span>
						<span class="step-label">{step.label}</span>
						{#if index === currentStep && status !== 'complete' && status !== 'error'}
							<span class="step-spinner">|</span>
						{/if}
					</div>
				{/each}
			</div>

			<!-- Current Module -->
			{#if currentModule && status !== 'complete'}
				<div class="module-status">
					<span class="module-label">Installing:</span>
					<span class="module-name">{currentModule}</span>
				</div>
			{/if}

			<!-- Error Display -->
			{#if status === 'error' && error}
				<div class="error-box">
					<div class="error-header">[ERROR]</div>
					<p class="error-text">{error}</p>
					<button class="retry-btn" on:click={() => window.location.reload()}>
						[RETRY]
					</button>
				</div>
			{/if}

			<!-- Completion Actions -->
			{#if status === 'complete'}
				<div class="completion-box">
					<div class="beacon-info">
						<span class="info-label">BEACON URL:</span>
						<a href={beaconUrl} target="_blank" class="beacon-link">{beaconUrl}</a>
					</div>

					<button class="dashboard-btn" on:click={goToDashboard}>
						[[ OPEN DASHBOARD ]]
					</button>

					<p class="email-hint">Login credentials sent to your email</p>

					{#if customDomain}
						<div class="dns-box">
							<div class="dns-header">CUSTOM DOMAIN: {customDomain}</div>
							<div class="dns-record">
								<span>Type: A</span>
								<span>Value: {instanceIp}</span>
								<span>TTL: 3600</span>
							</div>
						</div>
					{:else if instanceIp}
						<div class="dns-box">
							<div class="dns-header">SERVER IP</div>
							<div class="dns-value">{instanceIp}</div>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Footer -->
			{#if status !== 'complete' && status !== 'error'}
				<div class="panel-footer">
					<p>Estimated time: 5-10 minutes</p>
					<p class="dim">Notification email on completion</p>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	/* Base CRT Theme */
	.setup-page {
		min-height: 100vh;
		background: #050505;
		color: #00ff41;
		font-family: 'Courier New', 'Consolas', monospace;
		position: relative;
		overflow: hidden;
	}

	.scanlines-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: repeating-linear-gradient(
			0deg,
			rgba(0, 0, 0, 0.15),
			rgba(0, 0, 0, 0.15) 1px,
			transparent 1px,
			transparent 2px
		);
		pointer-events: none;
		z-index: 100;
	}

	/* Header */
	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 2rem;
		border-bottom: 1px solid #00ff4130;
		background: #0a0a0a;
	}

	.terminal-title {
		font-size: 0.9rem;
		opacity: 0.7;
	}

	.connection-status {
		font-size: 0.8rem;
		padding: 0.25rem 0.5rem;
		border: 1px solid #00ff4140;
	}

	.connection-status.connected {
		color: #00ff41;
		border-color: #00ff41;
	}

	.connection-status.error {
		color: #ff4141;
		border-color: #ff4141;
	}

	/* Grid Layout */
	.setup-grid {
		display: grid;
		grid-template-columns: 1fr 380px;
		min-height: calc(100vh - 60px);
	}

	@media (max-width: 900px) {
		.setup-grid {
			grid-template-columns: 1fr;
		}
		.slides-panel {
			display: none;
		}
	}

	/* Slides Panel */
	.slides-panel {
		padding: 2rem;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.completion-panel {
		text-align: center;
	}

	.ascii-beacon {
		color: #00ff41;
		font-size: 0.9rem;
		margin-bottom: 2rem;
		text-shadow: 0 0 10px #00ff41;
	}

	.ascii-beacon pre {
		margin: 0;
		line-height: 1.2;
	}

	.complete-title {
		font-size: 1.5rem;
		margin: 0 0 0.5rem 0;
		text-shadow: 0 0 20px #00ff41;
	}

	.complete-subtitle {
		opacity: 0.7;
		margin: 0;
	}

	/* Progress Panel */
	.progress-panel {
		background: #0a0a0a;
		border-left: 1px solid #00ff4130;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.panel-header {
		border-bottom: 1px solid #00ff4140;
		padding-bottom: 0.75rem;
	}

	.panel-title {
		font-size: 0.85rem;
		letter-spacing: 2px;
		opacity: 0.8;
	}

	/* Progress Ring */
	.progress-ring-container {
		position: relative;
		width: 120px;
		height: 120px;
		margin: 0 auto;
	}

	.progress-ring {
		width: 100%;
		height: 100%;
	}

	.ring-bg {
		stroke: #00ff4120;
	}

	.ring-fill {
		stroke: #00ff41;
		stroke-linecap: round;
		transition: stroke-dashoffset 0.5s ease;
		filter: drop-shadow(0 0 8px #00ff41);
	}

	.ring-text {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
	}

	.ring-percentage {
		font-size: 1.5rem;
		font-weight: bold;
		text-shadow: 0 0 10px #00ff41;
	}

	/* Steps */
	.steps-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.step-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem;
		font-size: 0.85rem;
		border: 1px solid transparent;
		transition: all 0.2s;
	}

	.step-row.pending {
		opacity: 0.3;
	}

	.step-row.active {
		background: #00ff4110;
		border-color: #00ff4140;
	}

	.step-row.completed .step-icon,
	.step-row.final .step-icon {
		color: #00ff41;
	}

	.step-row.active .step-icon {
		color: #ffff00;
		animation: blink 1s infinite;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	.step-icon {
		font-family: inherit;
		min-width: 40px;
	}

	.step-label {
		flex: 1;
	}

	.step-spinner {
		animation: spin-char 0.2s steps(4) infinite;
	}

	@keyframes spin-char {
		0% { content: '|'; }
		25% { content: '/'; }
		50% { content: '-'; }
		75% { content: '\\'; }
	}

	/* Module Status */
	.module-status {
		background: #00ff4110;
		border: 1px solid #00ff4130;
		padding: 0.75rem;
		font-size: 0.8rem;
	}

	.module-label {
		opacity: 0.7;
	}

	.module-name {
		color: #00ffff;
	}

	/* Error Box */
	.error-box {
		background: #ff414110;
		border: 1px solid #ff4141;
		padding: 1rem;
	}

	.error-header {
		color: #ff4141;
		font-weight: bold;
		margin-bottom: 0.5rem;
	}

	.error-text {
		color: #ff8888;
		font-size: 0.85rem;
		margin: 0 0 1rem 0;
	}

	.retry-btn {
		background: transparent;
		border: 1px solid #ff4141;
		color: #ff4141;
		padding: 0.5rem 1rem;
		font-family: inherit;
		cursor: pointer;
		transition: all 0.2s;
	}

	.retry-btn:hover {
		background: #ff414120;
	}

	/* Completion Box */
	.completion-box {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.beacon-info {
		background: #00ff4110;
		border: 1px solid #00ff41;
		padding: 1rem;
	}

	.info-label {
		display: block;
		font-size: 0.75rem;
		opacity: 0.7;
		margin-bottom: 0.5rem;
	}

	.beacon-link {
		color: #00ffff;
		text-decoration: none;
		word-break: break-all;
	}

	.beacon-link:hover {
		text-decoration: underline;
	}

	.dashboard-btn {
		background: #00ff41;
		border: none;
		color: #000;
		padding: 1rem;
		font-family: inherit;
		font-size: 1rem;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.2s;
		text-align: center;
	}

	.dashboard-btn:hover {
		box-shadow: 0 0 20px #00ff41;
	}

	.email-hint {
		text-align: center;
		font-size: 0.8rem;
		opacity: 0.6;
		margin: 0;
	}

	.dns-box {
		background: #0a0a0a;
		border: 1px solid #00ff4140;
		padding: 1rem;
		font-size: 0.8rem;
	}

	.dns-header {
		opacity: 0.7;
		margin-bottom: 0.5rem;
	}

	.dns-record {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		color: #00ffff;
	}

	.dns-value {
		color: #00ffff;
		font-size: 1rem;
	}

	/* Footer */
	.panel-footer {
		margin-top: auto;
		padding-top: 1rem;
		border-top: 1px solid #00ff4130;
		font-size: 0.8rem;
		text-align: center;
	}

	.panel-footer p {
		margin: 0.25rem 0;
	}

	.dim {
		opacity: 0.5;
	}
</style>
