<script>
	import { onMount, getContext } from 'svelte';
	import { loading, error } from '$lib/stores.js';
	import { notify } from '$lib/stores.js';
	import { getInstanceStatus, getModules, updateTheme } from '$lib/api.js';
	import ThemePresetCard from '$lib/components/ThemePresetCard.svelte';
	import ColorPicker from '$lib/components/ColorPicker.svelte';
	import AppThemeToggle from '$lib/components/AppThemeToggle.svelte';
	import { getPresetList } from '$lib/themes/presets.js';

	// Get theme context from ThemeProvider
	const theme = getContext('theme');

	let instance = null;
	let modules = [];
	let customDomain = '';
	let adminEmail = '';
	let backupEnabled = true;
	let backupFrequency = 'daily';
	let saving = false;
	let savingTheme = false;

	// Theme state
	let showCustomColors = false;
	let customPrimary = '#00d4aa';
	let customAccent = '#ff9b3f';

	// Get preset list
	const themePresets = getPresetList();

	// Native apps that are always themed
	const nativeApps = ['defcon', 'brainjoos', 'rag'];

	onMount(async () => {
		$loading = true;
		try {
			const [instanceData, modulesData] = await Promise.all([
				getInstanceStatus(),
				getModules().catch(() => ({ modules: [] }))
			]);

			instance = instanceData;
			modules = modulesData.modules || [];
			customDomain = instance.custom_domain || '';
			adminEmail = instance.admin_email || '';
			backupEnabled = instance.backup_enabled !== false;
			backupFrequency = instance.backup_frequency || 'daily';

			// Initialize custom colors from theme context
			if ($theme?.config?.customColors) {
				customPrimary = $theme.config.customColors['--theme-primary'] || '#00d4aa';
				customAccent = $theme.config.customColors['--theme-accent'] || '#ff9b3f';
			}
		} catch (e) {
			$error = e.message;
		} finally {
			$loading = false;
		}
	});

	function handlePresetSelect(presetId) {
		theme?.setPreset(presetId);
		showCustomColors = false;
	}

	function handleCustomColor(variable, value) {
		theme?.setCustomColor(variable, value);
		if (variable === '--theme-primary') customPrimary = value;
		if (variable === '--theme-accent') customAccent = value;
	}

	function handleAppThemeToggle(appId, enabled) {
		theme?.toggleAppTheming(appId, enabled);
	}

	async function saveTheme() {
		savingTheme = true;
		try {
			await theme?.save();
			notify('Theme saved successfully', 'success');
		} catch (e) {
			notify('Failed to save theme: ' + e.message, 'error');
		} finally {
			savingTheme = false;
		}
	}

	function resetTheme() {
		theme?.setPreset('reactor');
		theme?.clearCustomColors();
		showCustomColors = false;
		customPrimary = '#00d4aa';
		customAccent = '#ff9b3f';
	}

	async function saveSettings() {
		saving = true;
		try {
			const response = await fetch('/api/settings', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					custom_domain: customDomain,
					admin_email: adminEmail,
					backup_enabled: backupEnabled,
					backup_frequency: backupFrequency
				})
			});
			if (!response.ok) throw new Error('Failed to save settings');
			notify('Settings saved successfully', 'success');
		} catch (e) {
			notify(e.message, 'error');
		} finally {
			saving = false;
		}
	}

	async function triggerBackup() {
		try {
			const response = await fetch('/api/backup/trigger', { method: 'POST' });
			if (!response.ok) throw new Error('Failed to trigger backup');
			notify('Backup started', 'success');
		} catch (e) {
			notify(e.message, 'error');
		}
	}

	async function downloadBackup() {
		window.location.href = '/api/backup/download';
	}

	// Reactive: current theme config
	$: currentPreset = $theme?.config?.preset || 'reactor';
	$: themedApps = $theme?.config?.themedApps || nativeApps;
</script>

<svelte:head>
	<title>Settings | WOPR</title>
</svelte:head>

<div class="settings-page">
	<header>
		<h1>Settings</h1>
		<p class="text-muted">Configure your WOPR instance</p>
	</header>

	{#if $loading}
		<div class="loading">Loading settings...</div>
	{:else if $error}
		<div class="error card">
			<h3>Error</h3>
			<p>{$error}</p>
		</div>
	{:else}
		<!-- Theme Settings -->
		<section class="theme-section">
			<h2>Theme</h2>
			<p class="text-muted">Personalize your dashboard appearance</p>

			<div class="card">
				<div class="theme-presets">
					<label class="section-label">Choose a Preset</label>
					<div class="preset-grid">
						{#each themePresets as preset}
							<ThemePresetCard
								{preset}
								selected={currentPreset === preset.id}
								onClick={handlePresetSelect}
							/>
						{/each}
					</div>
				</div>

				<div class="custom-colors-section">
					<button
						class="btn btn-secondary btn-small"
						on:click={() => showCustomColors = !showCustomColors}
					>
						{showCustomColors ? 'Hide' : 'Show'} Custom Colors
					</button>

					{#if showCustomColors}
						<div class="custom-colors-panel">
							<ColorPicker
								label="Primary Color"
								value={customPrimary}
								onChange={(v) => handleCustomColor('--theme-primary', v)}
							/>
							<ColorPicker
								label="Accent Color"
								value={customAccent}
								onChange={(v) => handleCustomColor('--theme-accent', v)}
							/>
						</div>
					{/if}
				</div>

				<div class="theme-actions">
					<button
						class="btn btn-primary"
						on:click={saveTheme}
						disabled={savingTheme}
					>
						{savingTheme ? 'Saving...' : 'Save Theme'}
					</button>
					<button class="btn btn-secondary" on:click={resetTheme}>
						Reset to Default
					</button>
				</div>
			</div>
		</section>

		<!-- Per-App Theming -->
		<section>
			<h2>App Theming</h2>
			<p class="text-muted">Choose which apps receive your theme colors</p>

			<div class="card">
				<div class="app-list">
					{#each nativeApps as appId}
						<AppThemeToggle
							app={{ id: appId, name: appId.charAt(0).toUpperCase() + appId.slice(1) }}
							enabled={true}
							isNative={true}
							onToggle={handleAppThemeToggle}
						/>
					{/each}

					{#each modules.filter(m => !nativeApps.includes(m.id) && m.status === 'installed') as module}
						<AppThemeToggle
							app={{ id: module.id, name: module.name }}
							enabled={themedApps.includes(module.id)}
							isNative={false}
							onToggle={handleAppThemeToggle}
						/>
					{/each}
				</div>

				<p class="help-text">
					WOPR-native apps are always themed. Third-party apps may have varying
					levels of theme support.
				</p>
			</div>
		</section>

		<!-- Instance Info -->
		<section>
			<h2>Instance Information</h2>
			<div class="card info-card">
				<div class="info-grid">
					<div class="info-item">
						<span class="label">Instance ID</span>
						<span class="value mono">{instance?.instance_id || 'N/A'}</span>
					</div>
					<div class="info-item">
						<span class="label">Default Domain</span>
						<span class="value mono">{instance?.domain || 'N/A'}</span>
					</div>
					<div class="info-item">
						<span class="label">IP Address</span>
						<span class="value mono">{instance?.ip_address || 'N/A'}</span>
					</div>
					<div class="info-item">
						<span class="label">Created</span>
						<span class="value">{instance?.created_at ? new Date(instance.created_at).toLocaleDateString() : 'N/A'}</span>
					</div>
				</div>
			</div>
		</section>

		<!-- Custom Domain -->
		<section>
			<h2>Custom Domain</h2>
			<p class="text-muted">Use your own domain instead of the default wopr.systems subdomain</p>
			<div class="card">
				<div class="form-group">
					<label for="custom-domain">Custom Domain</label>
					<input
						type="text"
						id="custom-domain"
						bind:value={customDomain}
						placeholder="cloud.yourdomain.com"
					/>
					<p class="help-text">
						Point your domain's DNS to <strong>{instance?.ip_address || 'your server IP'}</strong> before enabling.
					</p>
				</div>

				{#if customDomain}
					<div class="dns-instructions">
						<h4>DNS Configuration Required</h4>
						<p>Add the following DNS records to your domain:</p>
						<table class="dns-table">
							<thead>
								<tr>
									<th>Type</th>
									<th>Name</th>
									<th>Value</th>
								</tr>
							</thead>
							<tbody>
								<tr>
									<td>A</td>
									<td>@</td>
									<td class="mono">{instance?.ip_address || 'SERVER_IP'}</td>
								</tr>
								<tr>
									<td>A</td>
									<td>*</td>
									<td class="mono">{instance?.ip_address || 'SERVER_IP'}</td>
								</tr>
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		</section>

		<!-- Admin Settings -->
		<section>
			<h2>Admin Settings</h2>
			<div class="card">
				<div class="form-group">
					<label for="admin-email">Admin Email</label>
					<input
						type="email"
						id="admin-email"
						bind:value={adminEmail}
						placeholder="admin@example.com"
					/>
					<p class="help-text">
						Used for important notifications and certificate expiry warnings.
					</p>
				</div>
			</div>
		</section>

		<!-- Backup Settings -->
		<section>
			<h2>Backups</h2>
			<div class="card">
				<div class="form-group">
					<label class="checkbox-label">
						<input type="checkbox" bind:checked={backupEnabled} />
						<span>Enable automatic backups</span>
					</label>
				</div>

				{#if backupEnabled}
					<div class="form-group">
						<label for="backup-frequency">Backup Frequency</label>
						<select id="backup-frequency" bind:value={backupFrequency}>
							<option value="daily">Daily</option>
							<option value="weekly">Weekly</option>
							<option value="hourly">Hourly</option>
						</select>
					</div>
				{/if}

				<div class="backup-status">
					<div class="status-item">
						<span class="label">Last Backup</span>
						<span class="value">{instance?.last_backup || 'Never'}</span>
					</div>
					<div class="status-item">
						<span class="label">Backup Size</span>
						<span class="value">{instance?.backup_size || 'N/A'}</span>
					</div>
				</div>

				<div class="backup-actions">
					<button class="btn btn-secondary" on:click={triggerBackup}>
						Backup Now
					</button>
					<button class="btn btn-secondary" on:click={downloadBackup}>
						Download Latest Backup
					</button>
				</div>
			</div>
		</section>

		<!-- Security -->
		<section>
			<h2>Security</h2>
			<div class="card">
				<div class="security-item">
					<div>
						<h4>SSL Certificates</h4>
						<p class="text-muted">Managed automatically via Let's Encrypt</p>
					</div>
					<span class="badge badge-success">Active</span>
				</div>

				<div class="security-item">
					<div>
						<h4>Firewall</h4>
						<p class="text-muted">Only ports 80, 443, and 22 are exposed</p>
					</div>
					<span class="badge badge-success">Enabled</span>
				</div>

				<div class="security-item">
					<div>
						<h4>Fail2ban</h4>
						<p class="text-muted">Protection against brute force attacks</p>
					</div>
					<span class="badge badge-success">Active</span>
				</div>
			</div>
		</section>

		<!-- Save Button -->
		<div class="save-section">
			<button class="btn btn-primary btn-large" on:click={saveSettings} disabled={saving}>
				{saving ? 'Saving...' : 'Save Settings'}
			</button>
		</div>

		<!-- Danger Zone -->
		<section class="danger-zone">
			<h2>Danger Zone</h2>
			<div class="card">
				<div class="danger-item">
					<div>
						<h4>Restart All Services</h4>
						<p class="text-muted">Restarts all WOPR containers. Causes brief downtime.</p>
					</div>
					<button class="btn btn-warning">Restart</button>
				</div>

				<div class="danger-item">
					<div>
						<h4>Factory Reset</h4>
						<p class="text-muted">Removes all data and reinstalls WOPR. This cannot be undone.</p>
					</div>
					<button class="btn btn-danger">Reset</button>
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.settings-page {
		max-width: 700px;
	}

	header {
		margin-bottom: 2rem;
	}

	section {
		margin-bottom: 2.5rem;
	}

	section h2 {
		margin-bottom: 0.5rem;
	}

	section > .text-muted {
		margin-bottom: 1rem;
	}

	/* Theme Section Styles */
	.theme-section {
		padding-bottom: 2rem;
		border-bottom: 1px solid var(--theme-border);
	}

	.section-label {
		display: block;
		font-weight: 500;
		margin-bottom: 0.75rem;
		color: var(--theme-text-muted);
	}

	.preset-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
		gap: 1rem;
	}

	.custom-colors-section {
		padding-top: 1rem;
		border-top: 1px solid var(--theme-border-subtle);
	}

	.custom-colors-panel {
		display: flex;
		gap: 2rem;
		margin-top: 1rem;
		padding: 1rem;
		background: var(--theme-surface-hover);
		border-radius: var(--theme-radius);
	}

	.btn-small {
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
	}

	.theme-actions {
		display: flex;
		gap: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--theme-border-subtle);
	}

	.app-list {
		display: flex;
		flex-direction: column;
	}

	/* Existing Styles */
	.info-card {
		padding: 1.5rem;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 1.5rem;
	}

	.info-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.info-item .label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.info-item .value {
		font-weight: 500;
	}

	.mono {
		font-family: monospace;
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.form-group label {
		font-weight: 500;
	}

	.form-group input[type="text"],
	.form-group input[type="email"],
	.form-group select {
		padding: 0.75rem 1rem;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 1rem;
	}

	.form-group input:focus,
	.form-group select:focus {
		outline: none;
		border-color: var(--color-primary);
	}

	.help-text {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.checkbox-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
	}

	.checkbox-label input {
		width: 18px;
		height: 18px;
	}

	.dns-instructions {
		padding: 1rem;
		background: var(--color-surface-hover);
		border-radius: 8px;
	}

	.dns-instructions h4 {
		margin-bottom: 0.5rem;
	}

	.dns-table {
		width: 100%;
		margin-top: 1rem;
		border-collapse: collapse;
	}

	.dns-table th,
	.dns-table td {
		padding: 0.5rem;
		text-align: left;
		border-bottom: 1px solid var(--color-border);
	}

	.dns-table th {
		color: var(--color-text-muted);
		font-weight: 500;
	}

	.backup-status {
		display: flex;
		gap: 2rem;
		padding: 1rem;
		background: var(--color-surface-hover);
		border-radius: 8px;
	}

	.status-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.status-item .label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.backup-actions {
		display: flex;
		gap: 1rem;
	}

	.security-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--color-border);
	}

	.security-item:last-child {
		padding-bottom: 0;
		border-bottom: none;
	}

	.security-item h4 {
		margin-bottom: 0.25rem;
	}

	.save-section {
		margin: 2rem 0;
	}

	.btn-large {
		padding: 1rem 2rem;
		font-size: 1rem;
	}

	.danger-zone {
		margin-top: 3rem;
		padding-top: 2rem;
		border-top: 1px solid var(--color-border);
	}

	.danger-zone h2 {
		color: var(--color-error);
	}

	.danger-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-bottom: 1.5rem;
		border-bottom: 1px solid var(--color-border);
	}

	.danger-item:last-child {
		padding-bottom: 0;
		border-bottom: none;
	}

	.danger-item h4 {
		margin-bottom: 0.25rem;
	}

	.btn-warning {
		background: var(--color-warning);
		color: #000;
	}

	.btn-danger {
		background: var(--color-error);
		color: #fff;
	}

	.loading {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}
</style>
