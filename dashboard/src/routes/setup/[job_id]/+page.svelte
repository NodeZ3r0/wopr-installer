<script>
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

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

	const steps = [
		{ id: 'payment', label: 'Payment Received', icon: '💳', description: 'Your payment has been confirmed' },
		{ id: 'server', label: 'Creating Server', icon: '🖥️', description: 'Spinning up your cloud server' },
		{ id: 'dns', label: 'Configuring DNS', icon: '🌐', description: 'Setting up your beacon domain' },
		{ id: 'install', label: 'Installing WOPR', icon: '⚙️', description: 'Deploying your apps and services' },
		{ id: 'configure', label: 'Final Configuration', icon: '🔧', description: 'Configuring accounts and permissions' },
		{ id: 'ready', label: 'Ready!', icon: '🚀', description: 'Your Beacon is online' },
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

		// Connect to SSE endpoint for real-time updates
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
			// Try to reconnect after 5 seconds
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

	// Calculate the stroke-dashoffset for the progress ring
	$: circumference = 2 * Math.PI * 120; // radius = 120
	$: strokeDashoffset = circumference - (progress / 100) * circumference;
</script>

<svelte:head>
	<title>Setting Up Your Beacon - WOPR</title>
</svelte:head>

<div class="setup-container">
	<div class="setup-content">
		<!-- WOPR Gear Progress Animation -->
		<div class="gear-container">
			<svg class="progress-ring" viewBox="0 0 280 280">
				<!-- Background circle -->
				<circle
					class="progress-bg"
					cx="140"
					cy="140"
					r="120"
					fill="none"
					stroke-width="12"
				/>
				<!-- Progress circle -->
				<circle
					class="progress-bar"
					cx="140"
					cy="140"
					r="120"
					fill="none"
					stroke-width="12"
					stroke-dasharray={circumference}
					stroke-dashoffset={strokeDashoffset}
					transform="rotate(-90 140 140)"
				/>
			</svg>

			<!-- Gear icon in center -->
			<div class="gear-icon" class:spinning={status !== 'complete' && status !== 'error'}>
				<svg viewBox="0 0 24 24" fill="currentColor">
					<path d="M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97 0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.31-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66z"/>
				</svg>
			</div>

			<!-- Percentage display -->
			<div class="progress-text">
				<span class="percentage">{Math.round(progress)}%</span>
			</div>
		</div>

		<!-- Status message -->
		<h1 class="status-title">
			{#if status === 'connecting'}
				Connecting...
			{:else if status === 'complete'}
				Your Beacon is Ready!
			{:else if status === 'error'}
				Setup Error
			{:else}
				Setting Up Your Beacon
			{/if}
		</h1>

		{#if status === 'error' && error}
			<div class="error-message">
				<p>{error}</p>
				<button class="btn btn-secondary" on:click={() => window.location.reload()}>
					Try Again
				</button>
			</div>
		{/if}

		<!-- Step progress -->
		<div class="steps-container">
			{#each steps as step, index}
				<div
					class="step"
					class:completed={index < currentStep}
					class:active={index === currentStep}
					class:pending={index > currentStep}
				>
					<div class="step-icon">
						{#if index < currentStep}
							<span class="check">✓</span>
						{:else}
							<span>{step.icon}</span>
						{/if}
					</div>
					<div class="step-content">
						<span class="step-label">{step.label}</span>
						{#if index === currentStep}
							<span class="step-description">{step.description}</span>
						{/if}
					</div>
					{#if index === currentStep && status !== 'complete' && status !== 'error'}
						<div class="step-spinner"></div>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Completion actions -->
		{#if status === 'complete'}
			<div class="completion-section">
				<div class="beacon-url">
					<span class="url-label">Your Beacon:</span>
					<a href={beaconUrl} target="_blank" class="url-link">{beaconUrl}</a>
				</div>

				<div class="completion-actions">
					<button class="btn btn-primary btn-large" on:click={goToDashboard}>
						Open Your Dashboard
						<span class="arrow">→</span>
					</button>
				</div>

				<div class="next-steps-hint">
					<p>Check your email for login credentials and a getting started guide.</p>
				</div>

				{#if customDomain}
					<div class="custom-domain-section">
						<h3>Custom Domain Setup</h3>
						<p>To use <strong>{customDomain}</strong> with your beacon, point it to your server:</p>
						<div class="dns-instructions">
							<div class="dns-row"><span class="dns-label">Type:</span><span class="dns-value">A</span></div>
							<div class="dns-row"><span class="dns-label">Name:</span><span class="dns-value">@ (or your subdomain)</span></div>
							<div class="dns-row"><span class="dns-label">Value:</span><span class="dns-value">{instanceIp}</span></div>
							<div class="dns-row"><span class="dns-label">TTL:</span><span class="dns-value">3600</span></div>
						</div>
						<p class="dns-note">Add this record at your domain registrar. DNS changes can take up to 48 hours to propagate. SSL will be provisioned automatically.</p>
					</div>
				{:else if instanceIp}
					<div class="custom-domain-section">
						<h3>Want to use your own domain?</h3>
						<p>Point any domain to your server with a DNS A record to:</p>
						<div class="dns-instructions">
							<div class="dns-row"><span class="dns-label">IP Address:</span><span class="dns-value">{instanceIp}</span></div>
						</div>
						<p class="dns-note">Then activate it in your beacon's Settings &gt; Custom Domain page.</p>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Waiting message -->
		{#if status !== 'complete' && status !== 'error'}
			<div class="waiting-message">
				<p>This usually takes 5-10 minutes. Feel free to grab a coffee!</p>
				<p class="email-note">We'll also email you when it's ready.</p>
			</div>
		{/if}
	</div>
</div>

<style>
	.setup-container {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--theme-bg, #0a0a0a);
		padding: 2rem;
	}

	.setup-content {
		max-width: 600px;
		width: 100%;
		text-align: center;
	}

	/* Gear Progress Animation */
	.gear-container {
		position: relative;
		width: 280px;
		height: 280px;
		margin: 0 auto 2rem;
	}

	.progress-ring {
		width: 100%;
		height: 100%;
	}

	.progress-bg {
		stroke: var(--theme-border, #333);
	}

	.progress-bar {
		stroke: var(--theme-primary, #00ff41);
		stroke-linecap: round;
		transition: stroke-dashoffset 0.5s ease;
		filter: drop-shadow(0 0 10px var(--theme-primary, #00ff41));
	}

	.gear-icon {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 80px;
		height: 80px;
		color: var(--theme-primary, #00ff41);
		filter: drop-shadow(0 0 15px var(--theme-primary, #00ff41));
	}

	.gear-icon.spinning {
		animation: spin 3s linear infinite;
	}

	@keyframes spin {
		from { transform: translate(-50%, -50%) rotate(0deg); }
		to { transform: translate(-50%, -50%) rotate(360deg); }
	}

	.gear-icon svg {
		width: 100%;
		height: 100%;
	}

	.progress-text {
		position: absolute;
		bottom: 30px;
		left: 50%;
		transform: translateX(-50%);
	}

	.percentage {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--theme-primary, #00ff41);
		text-shadow: 0 0 10px var(--theme-primary, #00ff41);
	}

	/* Status title */
	.status-title {
		font-size: 2rem;
		color: var(--theme-text, #e0e0e0);
		margin-bottom: 2rem;
	}

	/* Error message */
	.error-message {
		background: var(--theme-error-subtle, rgba(239, 68, 68, 0.1));
		border: 1px solid var(--theme-error, #ef4444);
		border-radius: var(--theme-radius, 8px);
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.error-message p {
		color: var(--theme-error, #ef4444);
		margin-bottom: 1rem;
	}

	/* Steps */
	.steps-container {
		text-align: left;
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: var(--theme-radius, 8px);
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.step {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 0.75rem 0;
		opacity: 0.4;
		transition: opacity 0.3s;
	}

	.step.completed,
	.step.active {
		opacity: 1;
	}

	.step:not(:last-child) {
		border-bottom: 1px solid var(--theme-border, #333);
	}

	.step-icon {
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.25rem;
		flex-shrink: 0;
	}

	.step.completed .step-icon {
		background: var(--theme-success, #22c55e);
		color: #fff;
		border-radius: 50%;
		font-size: 0.9rem;
	}

	.step-content {
		flex: 1;
	}

	.step-label {
		display: block;
		font-weight: 600;
		color: var(--theme-text, #e0e0e0);
	}

	.step.completed .step-label {
		color: var(--theme-success, #22c55e);
	}

	.step.active .step-label {
		color: var(--theme-primary, #00ff41);
	}

	.step-description {
		display: block;
		font-size: 0.85rem;
		color: var(--theme-text-muted, #888);
		margin-top: 0.25rem;
	}

	.step-spinner {
		width: 20px;
		height: 20px;
		border: 2px solid var(--theme-border, #333);
		border-top-color: var(--theme-primary, #00ff41);
		border-radius: 50%;
		animation: spinner 0.8s linear infinite;
	}

	@keyframes spinner {
		to { transform: rotate(360deg); }
	}

	/* Completion section */
	.completion-section {
		animation: fadeIn 0.5s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; transform: translateY(20px); }
		to { opacity: 1; transform: translateY(0); }
	}

	.beacon-url {
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-primary, #00ff41);
		border-radius: var(--theme-radius, 8px);
		padding: 1.25rem;
		margin-bottom: 1.5rem;
	}

	.url-label {
		display: block;
		font-size: 0.85rem;
		color: var(--theme-text-muted, #888);
		margin-bottom: 0.5rem;
	}

	.url-link {
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--theme-primary, #00ff41);
		text-decoration: none;
	}

	.url-link:hover {
		text-decoration: underline;
	}

	.completion-actions {
		margin-bottom: 1.5rem;
	}

	.next-steps-hint {
		color: var(--theme-text-muted, #888);
		font-size: 0.9rem;
		margin-bottom: 1.5rem;
	}

	.custom-domain-section {
		text-align: left;
		background: var(--theme-surface, #1a1a1a);
		border: 1px solid var(--theme-border, #333);
		border-radius: var(--theme-radius, 8px);
		padding: 1.5rem;
		margin-top: 1.5rem;
	}

	.custom-domain-section h3 {
		color: var(--theme-text, #e0e0e0);
		margin-bottom: 0.75rem;
	}

	.custom-domain-section p {
		color: var(--theme-text-muted, #888);
		font-size: 0.9rem;
		margin-bottom: 0.75rem;
	}

	.dns-instructions {
		background: var(--theme-bg, #0a0a0a);
		border: 1px solid var(--theme-border, #333);
		border-radius: 4px;
		padding: 1rem;
		margin-bottom: 0.75rem;
		font-family: monospace;
	}

	.dns-row {
		display: flex;
		gap: 1rem;
		padding: 0.25rem 0;
	}

	.dns-label {
		color: var(--theme-text-muted, #888);
		min-width: 80px;
	}

	.dns-value {
		color: var(--theme-primary, #00ff41);
		font-weight: 600;
	}

	.dns-note {
		font-size: 0.8rem;
		color: var(--theme-text-muted, #666);
	}

	/* Waiting message */
	.waiting-message {
		color: var(--theme-text-muted, #888);
	}

	.waiting-message p {
		margin-bottom: 0.5rem;
	}

	.email-note {
		font-size: 0.85rem;
	}

	/* Buttons */
	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.875rem 1.5rem;
		border-radius: var(--theme-radius, 8px);
		font-weight: 600;
		font-size: 1rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.btn-primary {
		background: var(--theme-primary, #00ff41);
		color: var(--theme-text-on-primary, #000);
	}

	.btn-primary:hover {
		filter: brightness(1.1);
		box-shadow: 0 0 20px var(--theme-primary, #00ff41);
	}

	.btn-secondary {
		background: var(--theme-surface, #1a1a1a);
		color: var(--theme-text, #e0e0e0);
		border: 1px solid var(--theme-border, #333);
	}

	.btn-secondary:hover {
		background: var(--theme-surface-hover, #252525);
	}

	.btn-large {
		padding: 1rem 2rem;
		font-size: 1.1rem;
	}

	.arrow {
		font-size: 1.2rem;
	}

	@media (max-width: 480px) {
		.gear-container {
			width: 220px;
			height: 220px;
		}

		.gear-icon {
			width: 60px;
			height: 60px;
		}

		.status-title {
			font-size: 1.5rem;
		}
	}
</style>
