<script>
	import { createEventDispatcher } from 'svelte';
	import { notify } from '$lib/stores.js';

	export let cloudflareConfigured = false;
	export let namecheapConfigured = false;

	const dispatch = createEventDispatcher();

	let searchQuery = '';
	let searching = false;
	let results = [];
	let selectedDomain = null;
	let selectedRegistrar = null;
	let showPurchaseModal = false;
	let purchasing = false;
	let registrarsQueried = [];

	// Contact info for domain registration
	let contactInfo = {
		firstName: '',
		lastName: '',
		email: '',
		phone: '',
		address1: '',
		address2: '',
		city: '',
		state: '',
		postalCode: '',
		country: 'US'
	};

	// Popular TLDs to search
	const defaultTlds = ['com', 'net', 'org', 'io', 'co', 'dev', 'app'];

	// Check if any registrar is configured
	$: anyRegistrarConfigured = cloudflareConfigured || namecheapConfigured;

	async function searchDomains() {
		if (!searchQuery.trim()) return;

		searching = true;
		results = [];
		registrarsQueried = [];

		try {
			const response = await fetch('/api/v1/domains/search', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					query: searchQuery.trim(),
					tlds: defaultTlds
				})
			});

			if (!response.ok) {
				const error = await response.json().catch(() => ({}));
				throw new Error(error.detail || 'Search failed');
			}

			const data = await response.json();

			// Handle new multi-registrar response format
			if (data.results) {
				results = data.results;
				registrarsQueried = data.registrars_queried || [];
			} else {
				// Fallback for legacy single-registrar response
				results = data.map(r => ({
					...r,
					prices: r.price ? [{
						registrar: 'cloudflare',
						registration: r.price,
						renewal: r.renewal,
						total_first_year: r.price + 0.18
					}] : [],
					best_price: r.price ? {
						registrar: 'cloudflare',
						registration: r.price,
						renewal: r.renewal,
						total_first_year: r.price + 0.18
					} : null
				}));
				registrarsQueried = ['cloudflare'];
			}
		} catch (e) {
			notify(e.message, 'error');
		} finally {
			searching = false;
		}
	}

	function selectDomain(domain, registrar) {
		selectedDomain = domain;
		selectedRegistrar = registrar;
		showPurchaseModal = true;
	}

	function closeModal() {
		showPurchaseModal = false;
		selectedDomain = null;
		selectedRegistrar = null;
	}

	async function purchaseDomain() {
		if (!selectedDomain || !selectedRegistrar || !validateContactInfo()) return;

		purchasing = true;

		try {
			const response = await fetch('/api/v1/domains/register', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					domain: selectedDomain.domain,
					registrar: selectedRegistrar.registrar,
					auto_renew: true,
					privacy: true,
					first_name: contactInfo.firstName,
					last_name: contactInfo.lastName,
					email: contactInfo.email,
					phone: contactInfo.phone,
					address1: contactInfo.address1,
					address2: contactInfo.address2,
					city: contactInfo.city,
					state: contactInfo.state,
					postal_code: contactInfo.postalCode,
					country: contactInfo.country
				})
			});

			if (!response.ok) {
				const error = await response.json().catch(() => ({}));
				throw new Error(error.detail || 'Registration failed');
			}

			const result = await response.json();
			notify(`Domain ${selectedDomain.domain} registered successfully via ${selectedRegistrar.registrar}!`, 'success');
			dispatch('registered', result);
			closeModal();

			// Refresh search to show updated status
			await searchDomains();
		} catch (e) {
			notify(e.message, 'error');
		} finally {
			purchasing = false;
		}
	}

	function validateContactInfo() {
		const required = ['firstName', 'lastName', 'email', 'phone', 'address1', 'city', 'state', 'postalCode', 'country'];
		for (const field of required) {
			if (!contactInfo[field]?.trim()) {
				notify(`Please fill in ${field.replace(/([A-Z])/g, ' $1').toLowerCase()}`, 'error');
				return false;
			}
		}
		return true;
	}

	function formatPrice(price) {
		if (price === null || price === undefined) return 'N/A';
		return `$${price.toFixed(2)}`;
	}

	function getRegistrarLabel(registrar) {
		const labels = {
			'cloudflare': 'Cloudflare',
			'namecheap': 'Namecheap'
		};
		return labels[registrar] || registrar;
	}

	function getRegistrarBadgeClass(registrar) {
		const classes = {
			'cloudflare': 'badge-cloudflare',
			'namecheap': 'badge-namecheap'
		};
		return classes[registrar] || '';
	}

	function handleKeydown(event) {
		if (event.key === 'Enter') {
			searchDomains();
		}
	}

	function getBestPriceForDomain(result) {
		if (result.best_price) {
			return result.best_price;
		}
		// Fallback: find lowest price
		if (result.prices && result.prices.length > 0) {
			return result.prices.reduce((best, p) =>
				(!best || (p.total_first_year && p.total_first_year < best.total_first_year)) ? p : best
			, null);
		}
		return null;
	}
</script>

<div class="domain-search">
	{#if !anyRegistrarConfigured}
		<div class="notice notice-warning">
			<h4>No Registrar Configured</h4>
			<p>
				To register domains, you need to connect at least one domain registrar.
				Configure your Cloudflare or Namecheap API credentials in the environment settings.
			</p>
		</div>
	{:else}
		<div class="search-box">
			<div class="search-input-wrapper">
				<input
					type="text"
					placeholder="Search for a domain..."
					bind:value={searchQuery}
					on:keydown={handleKeydown}
					disabled={searching}
				/>
				<button
					class="btn btn-primary"
					on:click={searchDomains}
					disabled={searching || !searchQuery.trim()}
				>
					{searching ? 'Searching...' : 'Search'}
				</button>
			</div>
			<p class="help-text">
				Enter a domain name (e.g., "mycompany") to check availability and compare prices
				{#if cloudflareConfigured && namecheapConfigured}
					across Cloudflare and Namecheap.
				{:else if cloudflareConfigured}
					via Cloudflare (at wholesale prices).
				{:else if namecheapConfigured}
					via Namecheap.
				{/if}
			</p>

			{#if registrarsQueried.length > 0}
				<div class="registrars-info">
					<span class="label">Searching:</span>
					{#each registrarsQueried as registrar}
						<span class="registrar-tag {getRegistrarBadgeClass(registrar)}">
							{getRegistrarLabel(registrar)}
						</span>
					{/each}
				</div>
			{/if}
		</div>

		{#if results.length > 0}
			<div class="results">
				<h4>Search Results</h4>
				<div class="results-grid">
					{#each results as result}
						{@const bestPrice = getBestPriceForDomain(result)}
						<div class="result-card" class:available={result.available} class:unavailable={!result.available}>
							<div class="domain-info">
								<span class="domain-name">{result.domain}</span>
								<span class="status-badge" class:badge-success={result.available} class:badge-error={!result.available}>
									{result.available ? 'Available' : 'Taken'}
								</span>
							</div>

							{#if result.available && result.prices && result.prices.length > 0}
								<div class="pricing-comparison">
									{#each result.prices as price}
										<div class="price-row" class:best-price={bestPrice && price.registrar === bestPrice.registrar}>
											<span class="registrar-badge {getRegistrarBadgeClass(price.registrar)}">
												{getRegistrarLabel(price.registrar)}
											</span>
											<div class="price-details">
												<span class="price">{formatPrice(price.registration)}/yr</span>
												{#if price.renewal && price.renewal !== price.registration}
													<span class="renewal">Renews: {formatPrice(price.renewal)}/yr</span>
												{/if}
												{#if price.is_premium}
													<span class="premium-tag">Premium</span>
												{/if}
											</div>
											<button
												class="btn btn-secondary btn-small"
												on:click={() => selectDomain(result, price)}
											>
												Register
											</button>
										</div>
									{/each}
								</div>
							{:else if result.available}
								<div class="pricing">
									<span class="price-na">Pricing unavailable</span>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>

<!-- Purchase Modal -->
{#if showPurchaseModal && selectedDomain && selectedRegistrar}
	<div class="modal-overlay" on:click={closeModal} on:keydown={(e) => e.key === 'Escape' && closeModal()}>
		<div class="modal" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="modal-title">
			<div class="modal-header">
				<h3 id="modal-title">Register {selectedDomain.domain}</h3>
				<button class="close-btn" on:click={closeModal} aria-label="Close">&times;</button>
			</div>

			<div class="modal-body">
				<div class="order-summary">
					<div class="summary-row">
						<span>Domain</span>
						<span class="mono">{selectedDomain.domain}</span>
					</div>
					<div class="summary-row">
						<span>Registrar</span>
						<span class="registrar-badge {getRegistrarBadgeClass(selectedRegistrar.registrar)}">
							{getRegistrarLabel(selectedRegistrar.registrar)}
						</span>
					</div>
					<div class="summary-row">
						<span>Registration (1 year)</span>
						<span>{formatPrice(selectedRegistrar.registration)}</span>
					</div>
					<div class="summary-row">
						<span>ICANN Fee</span>
						<span>$0.18</span>
					</div>
					<div class="summary-row total">
						<span>Total</span>
						<span>{formatPrice((selectedRegistrar.registration || 0) + 0.18)}</span>
					</div>
					{#if selectedRegistrar.renewal && selectedRegistrar.renewal !== selectedRegistrar.registration}
						<div class="summary-row renewal-note">
							<span>Annual Renewal</span>
							<span>{formatPrice(selectedRegistrar.renewal)}/yr</span>
						</div>
					{/if}
				</div>

				<div class="contact-form">
					<h4>Registrant Contact Information</h4>
					<p class="text-muted">This information is required for domain registration.</p>

					<div class="form-row">
						<div class="form-group">
							<label for="firstName">First Name *</label>
							<input type="text" id="firstName" bind:value={contactInfo.firstName} required />
						</div>
						<div class="form-group">
							<label for="lastName">Last Name *</label>
							<input type="text" id="lastName" bind:value={contactInfo.lastName} required />
						</div>
					</div>

					<div class="form-row">
						<div class="form-group">
							<label for="email">Email *</label>
							<input type="email" id="email" bind:value={contactInfo.email} required />
						</div>
						<div class="form-group">
							<label for="phone">Phone *</label>
							<input type="tel" id="phone" bind:value={contactInfo.phone} placeholder="+1.5551234567" required />
						</div>
					</div>

					<div class="form-group">
						<label for="address1">Address *</label>
						<input type="text" id="address1" bind:value={contactInfo.address1} required />
					</div>

					<div class="form-group">
						<label for="address2">Address Line 2</label>
						<input type="text" id="address2" bind:value={contactInfo.address2} />
					</div>

					<div class="form-row">
						<div class="form-group">
							<label for="city">City *</label>
							<input type="text" id="city" bind:value={contactInfo.city} required />
						</div>
						<div class="form-group">
							<label for="state">State/Province *</label>
							<input type="text" id="state" bind:value={contactInfo.state} required />
						</div>
					</div>

					<div class="form-row">
						<div class="form-group">
							<label for="postalCode">Postal Code *</label>
							<input type="text" id="postalCode" bind:value={contactInfo.postalCode} required />
						</div>
						<div class="form-group">
							<label for="country">Country *</label>
							<select id="country" bind:value={contactInfo.country} required>
								<option value="US">United States</option>
								<option value="CA">Canada</option>
								<option value="GB">United Kingdom</option>
								<option value="AU">Australia</option>
								<option value="DE">Germany</option>
								<option value="FR">France</option>
								<option value="NL">Netherlands</option>
								<option value="JP">Japan</option>
								<option value="SG">Singapore</option>
							</select>
						</div>
					</div>

					<div class="privacy-notice">
						<p>
							<strong>Privacy Protection Included:</strong>
							{#if selectedRegistrar.registrar === 'cloudflare'}
								Your contact information will be protected by Cloudflare's privacy service at no extra cost.
							{:else if selectedRegistrar.registrar === 'namecheap'}
								WhoisGuard privacy protection is included free with your domain registration.
							{:else}
								Privacy protection may be available depending on the registrar.
							{/if}
						</p>
					</div>
				</div>
			</div>

			<div class="modal-footer">
				<button class="btn btn-secondary" on:click={closeModal} disabled={purchasing}>
					Cancel
				</button>
				<button class="btn btn-primary" on:click={purchaseDomain} disabled={purchasing}>
					{purchasing ? 'Processing...' : `Purchase for ${formatPrice((selectedRegistrar.registration || 0) + 0.18)}`}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.domain-search {
		width: 100%;
	}

	.notice {
		padding: 1rem;
		border-radius: 8px;
		margin-bottom: 1rem;
	}

	.notice-warning {
		background: rgba(245, 158, 11, 0.1);
		border: 1px solid rgba(245, 158, 11, 0.3);
	}

	.notice h4 {
		color: var(--color-warning);
		margin-bottom: 0.5rem;
	}

	.search-box {
		margin-bottom: 1.5rem;
	}

	.search-input-wrapper {
		display: flex;
		gap: 0.75rem;
	}

	.search-input-wrapper input {
		flex: 1;
		padding: 0.75rem 1rem;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 1rem;
	}

	.search-input-wrapper input:focus {
		outline: none;
		border-color: var(--color-primary);
	}

	.help-text {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin-top: 0.5rem;
	}

	.registrars-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.75rem;
		font-size: 0.85rem;
	}

	.registrars-info .label {
		color: var(--color-text-muted);
	}

	.registrar-tag,
	.registrar-badge {
		padding: 0.2rem 0.5rem;
		border-radius: 4px;
		font-size: 0.75rem;
		font-weight: 600;
	}

	.badge-cloudflare {
		background: rgba(245, 124, 0, 0.15);
		color: #f57c00;
	}

	.badge-namecheap {
		background: rgba(222, 69, 32, 0.15);
		color: #de4520;
	}

	.results h4 {
		margin-bottom: 1rem;
	}

	.results-grid {
		display: grid;
		gap: 0.75rem;
	}

	.result-card {
		padding: 1rem;
		border: 1px solid var(--color-border);
		border-radius: 8px;
		background: var(--color-surface);
	}

	.result-card.available {
		border-color: rgba(34, 197, 94, 0.3);
	}

	.result-card.unavailable {
		opacity: 0.6;
	}

	.domain-info {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.domain-name {
		font-weight: 600;
		font-family: monospace;
		font-size: 1rem;
	}

	.status-badge {
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 600;
	}

	.badge-success {
		background: rgba(34, 197, 94, 0.2);
		color: var(--color-success);
	}

	.badge-error {
		background: rgba(239, 68, 68, 0.2);
		color: var(--color-error);
	}

	.pricing-comparison {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.price-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.5rem 0.75rem;
		background: var(--color-surface-hover);
		border-radius: 6px;
		border: 1px solid transparent;
	}

	.price-row.best-price {
		border-color: var(--color-primary);
		background: rgba(var(--color-primary-rgb), 0.05);
	}

	.price-details {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.price {
		font-weight: 600;
		color: var(--color-primary);
	}

	.renewal {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.premium-tag {
		display: inline-block;
		padding: 0.1rem 0.4rem;
		background: rgba(168, 85, 247, 0.2);
		color: #a855f7;
		border-radius: 4px;
		font-size: 0.7rem;
		font-weight: 600;
	}

	.price-na {
		color: var(--color-text-muted);
		font-style: italic;
	}

	.btn-small {
		padding: 0.4rem 0.8rem;
		font-size: 0.85rem;
	}

	/* Modal Styles */
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.7);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.modal {
		background: var(--color-surface);
		border-radius: 12px;
		max-width: 600px;
		width: 100%;
		max-height: 90vh;
		overflow-y: auto;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1.25rem 1.5rem;
		border-bottom: 1px solid var(--color-border);
	}

	.modal-header h3 {
		font-size: 1.25rem;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 1.5rem;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}

	.close-btn:hover {
		color: var(--color-text);
	}

	.modal-body {
		padding: 1.5rem;
	}

	.order-summary {
		background: var(--color-surface-hover);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
	}

	.summary-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 0;
	}

	.summary-row.total {
		border-top: 1px solid var(--color-border);
		margin-top: 0.5rem;
		padding-top: 0.75rem;
		font-weight: 600;
	}

	.summary-row.renewal-note {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		border-top: 1px dashed var(--color-border);
		margin-top: 0.5rem;
		padding-top: 0.5rem;
	}

	.mono {
		font-family: monospace;
	}

	.contact-form h4 {
		margin-bottom: 0.5rem;
	}

	.contact-form .text-muted {
		margin-bottom: 1rem;
	}

	.form-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 1rem;
	}

	.form-group label {
		font-weight: 500;
		font-size: 0.9rem;
	}

	.form-group input,
	.form-group select {
		padding: 0.65rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 0.95rem;
	}

	.form-group input:focus,
	.form-group select:focus {
		outline: none;
		border-color: var(--color-primary);
	}

	.privacy-notice {
		background: rgba(34, 197, 94, 0.1);
		border: 1px solid rgba(34, 197, 94, 0.3);
		border-radius: 6px;
		padding: 0.75rem;
		font-size: 0.85rem;
	}

	.modal-footer {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		padding: 1rem 1.5rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-surface-hover);
	}

	@media (max-width: 600px) {
		.price-row {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.5rem;
		}

		.price-details {
			width: 100%;
		}

		.form-row {
			grid-template-columns: 1fr;
		}
	}
</style>
