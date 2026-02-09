<script>
	import { onMount } from 'svelte';
	import { loading, error, notify } from '$lib/stores.js';
	import { getInstanceStatus } from '$lib/api.js';

	// Domain state
	let instance = null;
	let currentDomain = '';
	let customDomain = '';
	let domainStatus = 'none'; // none, pending, verifying, active, failed
	let dnsVerificationResult = null;
	let verifying = false;
	let saving = false;

	// DNS instructions visibility
	let showDnsInstructions = false;

	onMount(async () => {
		$loading = true;
		try {
			instance = await getInstanceStatus();
			currentDomain = instance.domain || '';
			customDomain = instance.custom_domain || '';
			domainStatus = instance.custom_domain_status || 'none';
		} catch (e) {
			$error = e.message;
		} finally {
			$loading = false;
		}
	});

	// Reactive: show DNS instructions when custom domain is entered
	$: showDnsInstructions = customDomain && customDomain.length > 3;

	// Validate domain format
	function isValidDomain(domain) {
		const pattern = /^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$/i;
		return pattern.test(domain);
	}

	// Save custom domain
	async function saveCustomDomain() {
		if (!customDomain) {
			notify('Please enter a custom domain', 'error');
			return;
		}

		if (!isValidDomain(customDomain)) {
			notify('Invalid domain format. Example: cloud.yourdomain.com', 'error');
			return;
		}

		saving = true;
		try {
			const response = await fetch('/api/v1/domain/custom', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ domain: customDomain })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to save domain');
			}

			const result = await response.json();
			domainStatus = 'pending';
			notify('Custom domain saved. Please configure your DNS records.', 'success');
		} catch (e) {
			notify(e.message, 'error');
		} finally {
			saving = false;
		}
	}

	// Verify DNS propagation
	async function verifyDns() {
		if (!customDomain) {
			notify('Please enter a custom domain first', 'error');
			return;
		}

		verifying = true;
		dnsVerificationResult = null;
		domainStatus = 'verifying';

		try {
			const response = await fetch('/api/v1/domain/verify', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ domain: customDomain })
			});

			const result = await response.json();
			dnsVerificationResult = result;

			if (result.verified) {
				domainStatus = 'active';
				notify('DNS verified! Your custom domain is now active.', 'success');
			} else {
				domainStatus = 'pending';
				notify('DNS not yet propagated. Please wait and try again.', 'warning');
			}
		} catch (e) {
			domainStatus = 'failed';
			notify('DNS verification failed: ' + e.message, 'error');
		} finally {
			verifying = false;
		}
	}

	// Remove custom domain
	async function removeCustomDomain() {
		if (!confirm('Are you sure you want to remove your custom domain?')) {
			return;
		}

		saving = true;
		try {
			const response = await fetch('/api/v1/domain/custom', {
				method: 'DELETE'
			});

			if (!response.ok) {
				throw new Error('Failed to remove domain');
			}

			customDomain = '';
			domainStatus = 'none';
			dnsVerificationResult = null;
			notify('Custom domain removed', 'success');
		} catch (e) {
			notify(e.message, 'error');
		} finally {
			saving = false;
		}
	}

	// Copy to clipboard helper
	function copyToClipboard(text) {
		navigator.clipboard.writeText(text);
		notify('Copied to clipboard', 'success');
	}

	// Get status badge config
	function getStatusConfig(status) {
		const configs = {
			none: { color: 'muted', icon: '-', text: 'Not configured' },
			pending: { color: 'warning', icon: '◌', text: 'Pending DNS setup' },
			verifying: { color: 'info', icon: '◐', text: 'Verifying...' },
			active: { color: 'success', icon: '●', text: 'Active' },
			failed: { color: 'error', icon: '!', text: 'Verification failed' }
		};
		return configs[status] || configs.none;
	}

	$: statusConfig = getStatusConfig(domainStatus);
</script>

<svelte:head>
	<title>Custom Domain | WOPR Settings</title>
</svelte:head>

<div class="domain-page">
	<header>
		<a href="/settings" class="back-link">← Back to Settings</a>
		<h1>Custom Domain</h1>
		<p class="text-muted">Bring Your Own Domain (BYOD) - Use your own domain instead of the default wopr.systems subdomain</p>
	</header>

	{#if $loading}
		<div class="loading">
			<div class="loading-spinner"></div>
			<span>Loading domain settings...</span>
		</div>
	{:else if $error}
		<div class="error card">
			<h3>Error</h3>
			<p>{$error}</p>
		</div>
	{:else}
		<!-- Current Domain -->
		<section class="current-domain-section">
			<h2>Current Domain</h2>
			<div class="card domain-card">
				<div class="domain-info">
					<div class="domain-row">
						<span class="label">Default Domain</span>
						<div class="domain-value">
							<span class="domain mono">{currentDomain || 'Not assigned'}</span>
							<span class="badge badge-success">Always Active</span>
						</div>
					</div>

					{#if customDomain && domainStatus !== 'none'}
						<div class="domain-row">
							<span class="label">Custom Domain</span>
							<div class="domain-value">
								<span class="domain mono">{customDomain}</span>
								<span class="badge badge-{statusConfig.color}">
									<span class="icon">{statusConfig.icon}</span>
									{statusConfig.text}
								</span>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</section>

		<!-- Configure Custom Domain -->
		<section>
			<h2>{domainStatus === 'none' ? 'Add Custom Domain' : 'Custom Domain Settings'}</h2>
			<p class="text-muted">Point your own domain to your WOPR beacon</p>

			<div class="card">
				<div class="form-group">
					<label for="custom-domain">Custom Domain</label>
					<div class="input-group">
						<input
							type="text"
							id="custom-domain"
							bind:value={customDomain}
							placeholder="cloud.yourdomain.com"
							class:has-value={customDomain}
							disabled={domainStatus === 'active'}
						/>
						{#if domainStatus === 'active'}
							<button class="btn btn-danger btn-small" on:click={removeCustomDomain} disabled={saving}>
								Remove
							</button>
						{/if}
					</div>
					<p class="help-text">
						Enter the domain you want to use for your WOPR beacon. This can be a subdomain (e.g., cloud.yourdomain.com) or a root domain.
					</p>
				</div>

				{#if showDnsInstructions && domainStatus !== 'active'}
					<div class="dns-instructions">
						<h3>DNS Configuration Required</h3>
						<p>Add the following DNS records to your domain registrar or DNS provider:</p>

						<div class="dns-records">
							<div class="dns-record">
								<div class="record-header">
									<span class="record-type">A Record</span>
									<span class="record-purpose">Root domain</span>
								</div>
								<div class="record-details">
									<div class="record-field">
										<span class="field-label">Name / Host</span>
										<div class="field-value-wrapper">
											<code class="field-value">@</code>
											<button class="copy-btn" on:click={() => copyToClipboard('@')} title="Copy">
												<span class="copy-icon">&#x2398;</span>
											</button>
										</div>
									</div>
									<div class="record-field">
										<span class="field-label">Points to / Value</span>
										<div class="field-value-wrapper">
											<code class="field-value">{instance?.ip_address || 'YOUR_SERVER_IP'}</code>
											<button class="copy-btn" on:click={() => copyToClipboard(instance?.ip_address || '')} title="Copy">
												<span class="copy-icon">&#x2398;</span>
											</button>
										</div>
									</div>
									<div class="record-field">
										<span class="field-label">TTL</span>
										<code class="field-value">300</code>
									</div>
								</div>
							</div>

							<div class="dns-record">
								<div class="record-header">
									<span class="record-type">A Record</span>
									<span class="record-purpose">Wildcard (for subdomains)</span>
								</div>
								<div class="record-details">
									<div class="record-field">
										<span class="field-label">Name / Host</span>
										<div class="field-value-wrapper">
											<code class="field-value">*</code>
											<button class="copy-btn" on:click={() => copyToClipboard('*')} title="Copy">
												<span class="copy-icon">&#x2398;</span>
											</button>
										</div>
									</div>
									<div class="record-field">
										<span class="field-label">Points to / Value</span>
										<div class="field-value-wrapper">
											<code class="field-value">{instance?.ip_address || 'YOUR_SERVER_IP'}</code>
											<button class="copy-btn" on:click={() => copyToClipboard(instance?.ip_address || '')} title="Copy">
												<span class="copy-icon">&#x2398;</span>
											</button>
										</div>
									</div>
									<div class="record-field">
										<span class="field-label">TTL</span>
										<code class="field-value">300</code>
									</div>
								</div>
							</div>
						</div>

						<div class="dns-notes">
							<h4>Important Notes:</h4>
							<ul>
								<li>DNS changes can take up to 48 hours to propagate globally, but usually complete within 5-30 minutes.</li>
								<li>The wildcard (*) record is required for WOPR apps (auth.domain.com, files.domain.com, etc.)</li>
								<li>Some DNS providers require you to use the full subdomain instead of "@" - check your provider's documentation.</li>
								<li>If you're using Cloudflare, make sure the records are set to "DNS only" (gray cloud), not "Proxied" (orange cloud).</li>
							</ul>
						</div>
					</div>
				{/if}

				{#if dnsVerificationResult && !dnsVerificationResult.verified}
					<div class="verification-result error-result">
						<h4>DNS Verification Failed</h4>
						<p>The following issues were detected:</p>
						<ul>
							{#if dnsVerificationResult.a_record_status === 'missing'}
								<li>A record for @ is missing or not pointing to {instance?.ip_address}</li>
							{/if}
							{#if dnsVerificationResult.wildcard_status === 'missing'}
								<li>Wildcard A record (*) is missing or not pointing to {instance?.ip_address}</li>
							{/if}
							{#if dnsVerificationResult.error}
								<li>{dnsVerificationResult.error}</li>
							{/if}
						</ul>
						<p class="help-text">Please check your DNS configuration and wait a few minutes for propagation.</p>
					</div>
				{/if}

				{#if dnsVerificationResult && dnsVerificationResult.verified}
					<div class="verification-result success-result">
						<h4>DNS Verified Successfully</h4>
						<p>Your custom domain is properly configured and active!</p>
						<ul>
							<li>A record: {customDomain} -> {instance?.ip_address}</li>
							<li>Wildcard: *.{customDomain} -> {instance?.ip_address}</li>
						</ul>
					</div>
				{/if}

				<div class="domain-actions">
					{#if domainStatus !== 'active'}
						<button
							class="btn btn-primary"
							on:click={saveCustomDomain}
							disabled={saving || !customDomain || !isValidDomain(customDomain)}
						>
							{saving ? 'Saving...' : 'Save Domain'}
						</button>
					{/if}

					{#if customDomain && domainStatus !== 'none'}
						<button
							class="btn btn-secondary verify-btn"
							on:click={verifyDns}
							disabled={verifying}
						>
							{#if verifying}
								<span class="spinner"></span>
								Verifying DNS...
							{:else}
								Verify DNS
							{/if}
						</button>
					{/if}
				</div>
			</div>
		</section>

		<!-- How It Works -->
		<section class="how-it-works">
			<h2>How It Works</h2>
			<div class="card">
				<div class="steps">
					<div class="step">
						<div class="step-number">1</div>
						<div class="step-content">
							<h4>Enter Your Domain</h4>
							<p>Enter the domain you want to use for your WOPR beacon.</p>
						</div>
					</div>
					<div class="step">
						<div class="step-number">2</div>
						<div class="step-content">
							<h4>Configure DNS</h4>
							<p>Add the A records shown above to your DNS provider.</p>
						</div>
					</div>
					<div class="step">
						<div class="step-number">3</div>
						<div class="step-content">
							<h4>Verify & Activate</h4>
							<p>Click "Verify DNS" to check propagation. Once verified, your domain is active!</p>
						</div>
					</div>
					<div class="step">
						<div class="step-number">4</div>
						<div class="step-content">
							<h4>SSL Certificates</h4>
							<p>WOPR automatically provisions SSL certificates via Let's Encrypt.</p>
						</div>
					</div>
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.domain-page {
		max-width: 800px;
	}

	header {
		margin-bottom: 2rem;
	}

	.back-link {
		display: inline-block;
		margin-bottom: 1rem;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.back-link:hover {
		color: var(--theme-primary);
	}

	section {
		margin-bottom: 2.5rem;
	}

	section h2 {
		margin-bottom: 0.5rem;
		color: var(--theme-text);
	}

	section > .text-muted {
		margin-bottom: 1rem;
	}

	/* Domain Card */
	.domain-card {
		background: var(--theme-surface);
	}

	.domain-info {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.domain-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--theme-border);
	}

	.domain-row:last-child {
		border-bottom: none;
	}

	.domain-row .label {
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.domain-value {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.domain {
		font-size: 1rem;
		font-weight: 500;
	}

	.mono {
		font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
	}

	/* Badge styles */
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.25rem 0.75rem;
		border-radius: 999px;
		font-weight: 600;
		font-size: 0.75rem;
	}

	.badge-success {
		background: rgba(0, 255, 65, 0.15);
		color: #00ff41;
	}

	.badge-warning {
		background: rgba(245, 158, 11, 0.15);
		color: #f59e0b;
	}

	.badge-info {
		background: rgba(59, 130, 246, 0.15);
		color: #3b82f6;
	}

	.badge-error {
		background: rgba(239, 68, 68, 0.15);
		color: #ef4444;
	}

	.badge-muted {
		background: rgba(136, 136, 136, 0.15);
		color: #888;
	}

	/* Form styles */
	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.form-group label {
		font-weight: 500;
		color: var(--theme-text);
	}

	.input-group {
		display: flex;
		gap: 0.5rem;
	}

	.input-group input {
		flex: 1;
	}

	.form-group input {
		padding: 0.75rem 1rem;
		border: 1px solid var(--theme-border);
		border-radius: 6px;
		background: var(--theme-bg);
		color: var(--theme-text);
		font-size: 1rem;
		font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
	}

	.form-group input:focus {
		outline: none;
		border-color: #00ff41;
		box-shadow: 0 0 0 2px rgba(0, 255, 65, 0.2);
	}

	.form-group input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.help-text {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	/* DNS Instructions */
	.dns-instructions {
		padding: 1.5rem;
		background: rgba(0, 255, 65, 0.05);
		border: 1px solid rgba(0, 255, 65, 0.2);
		border-radius: 8px;
		margin-top: 1.5rem;
	}

	.dns-instructions h3 {
		color: #00ff41;
		margin-bottom: 0.5rem;
		font-size: 1.1rem;
	}

	.dns-instructions > p {
		color: var(--theme-text-muted);
		margin-bottom: 1rem;
	}

	.dns-records {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.dns-record {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: 6px;
		overflow: hidden;
	}

	.record-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
		background: var(--theme-surface-hover);
		border-bottom: 1px solid var(--theme-border);
	}

	.record-type {
		font-weight: 600;
		color: #00ff41;
	}

	.record-purpose {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	.record-details {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1rem;
		padding: 1rem;
	}

	.record-field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.field-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
	}

	.field-value-wrapper {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.field-value {
		font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
		background: var(--theme-bg);
		padding: 0.35rem 0.5rem;
		border-radius: 4px;
		color: #00ff41;
	}

	.copy-btn {
		padding: 0.35rem;
		background: transparent;
		border: 1px solid var(--theme-border);
		border-radius: 4px;
		color: var(--theme-text-muted);
		cursor: pointer;
		transition: all 0.2s;
	}

	.copy-btn:hover {
		background: var(--theme-surface-hover);
		color: #00ff41;
		border-color: #00ff41;
	}

	.copy-icon {
		font-size: 0.9rem;
	}

	.dns-notes {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(0, 255, 65, 0.2);
	}

	.dns-notes h4 {
		color: var(--theme-text);
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}

	.dns-notes ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.dns-notes li {
		position: relative;
		padding-left: 1.25rem;
		margin-bottom: 0.5rem;
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	.dns-notes li::before {
		content: '>';
		position: absolute;
		left: 0;
		color: #00ff41;
	}

	/* Verification Results */
	.verification-result {
		padding: 1rem;
		border-radius: 8px;
		margin-top: 1rem;
	}

	.verification-result h4 {
		margin-bottom: 0.5rem;
	}

	.verification-result ul {
		margin: 0.5rem 0;
		padding-left: 1.5rem;
	}

	.verification-result li {
		margin-bottom: 0.25rem;
	}

	.error-result {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.error-result h4 {
		color: #ef4444;
	}

	.success-result {
		background: rgba(0, 255, 65, 0.1);
		border: 1px solid rgba(0, 255, 65, 0.3);
	}

	.success-result h4 {
		color: #00ff41;
	}

	/* Action Buttons */
	.domain-actions {
		display: flex;
		gap: 1rem;
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--theme-border);
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		border-radius: 6px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		border: none;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-primary {
		background: #00ff41;
		color: #000;
	}

	.btn-primary:hover:not(:disabled) {
		background: #00cc34;
	}

	.btn-secondary {
		background: var(--theme-surface);
		color: var(--theme-text);
		border: 1px solid var(--theme-border);
	}

	.btn-secondary:hover:not(:disabled) {
		background: var(--theme-surface-hover);
		border-color: #00ff41;
	}

	.btn-danger {
		background: rgba(239, 68, 68, 0.2);
		color: #ef4444;
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.btn-danger:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.3);
	}

	.btn-small {
		padding: 0.5rem 1rem;
		font-size: 0.85rem;
	}

	.verify-btn {
		min-width: 140px;
	}

	.spinner {
		width: 14px;
		height: 14px;
		border: 2px solid transparent;
		border-top-color: currentColor;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* How It Works */
	.how-it-works .card {
		background: var(--theme-surface);
	}

	.steps {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 1.5rem;
	}

	.step {
		display: flex;
		gap: 1rem;
	}

	.step-number {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: rgba(0, 255, 65, 0.15);
		color: #00ff41;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 600;
		flex-shrink: 0;
	}

	.step-content h4 {
		margin-bottom: 0.25rem;
		color: var(--theme-text);
		font-size: 0.95rem;
	}

	.step-content p {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	/* Card base styles */
	.card {
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: 8px;
		padding: 1.5rem;
	}

	/* Loading */
	.loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 3rem;
		color: var(--theme-text-muted);
		gap: 1rem;
	}

	.loading-spinner {
		width: 32px;
		height: 32px;
		border: 3px solid var(--theme-border);
		border-top-color: #00ff41;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	/* Error */
	.error {
		background: rgba(239, 68, 68, 0.1);
		border-color: rgba(239, 68, 68, 0.3);
	}

	.error h3 {
		color: #ef4444;
		margin-bottom: 0.5rem;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.record-details {
			grid-template-columns: 1fr;
		}

		.steps {
			grid-template-columns: 1fr;
		}

		.domain-actions {
			flex-direction: column;
		}

		.domain-row {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.5rem;
		}

		.domain-value {
			width: 100%;
			justify-content: space-between;
		}
	}
</style>
