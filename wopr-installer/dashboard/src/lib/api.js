// WOPR Dashboard API Client

const API_BASE = '/api/v1';

async function fetchAPI(endpoint, options = {}) {
	const response = await fetch(`${API_BASE}${endpoint}`, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options.headers
		}
	});

	if (!response.ok) {
		const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
		throw new Error(error.detail || `HTTP ${response.status}`);
	}

	return response.json();
}

// Instance API
export async function getInstanceStatus() {
	return fetchAPI('/instance');
}

// Modules API
export async function getModules() {
	return fetchAPI('/modules');
}

export async function getModuleStatus(moduleId) {
	return fetchAPI(`/modules/${moduleId}`);
}

// Trials API
export async function getTrials() {
	return fetchAPI('/trials');
}

export async function startTrial(trialId) {
	return fetchAPI('/trials/start', {
		method: 'POST',
		body: JSON.stringify({ trial_id: trialId })
	});
}

// Bundles API
export async function getBundles() {
	return fetchAPI('/bundles');
}

export async function upgradeBundle(bundleId) {
	return fetchAPI('/upgrade', {
		method: 'POST',
		body: JSON.stringify({ bundle_id: bundleId })
	});
}

// Billing API
export async function getBillingInfo() {
	return fetchAPI('/billing');
}

// Settings API
export async function getSettings() {
	return fetchAPI('/settings');
}

export async function updateSettings(settings) {
	return fetchAPI('/settings', {
		method: 'PATCH',
		body: JSON.stringify(settings)
	});
}

// Theme API
export async function getTheme() {
	return fetchAPI('/themes');
}

export async function updateTheme(themeConfig) {
	return fetchAPI('/themes', {
		method: 'PATCH',
		body: JSON.stringify(themeConfig)
	});
}

export async function getThemePresets() {
	return fetchAPI('/themes/presets');
}

export async function updateAppTheme(appId, themeOverride) {
	return fetchAPI(`/themes/apps/${appId}`, {
		method: 'PATCH',
		body: JSON.stringify(themeOverride)
	});
}

export async function removeAppTheme(appId) {
	return fetchAPI(`/themes/apps/${appId}`, {
		method: 'DELETE'
	});
}

export async function getThemeCSS() {
	return fetchAPI('/themes/css');
}

export async function getThemeJSON() {
	return fetchAPI('/themes/json');
}

// Domain Registration API (Cloudflare Registrar)
export async function checkDomainAvailability(domain) {
	return fetchAPI(`/domains/check/${encodeURIComponent(domain)}`);
}

export async function searchDomains(query, tlds = null) {
	return fetchAPI('/domains/search', {
		method: 'POST',
		body: JSON.stringify({ query, tlds })
	});
}

export async function getDomainPricing() {
	return fetchAPI('/domains/pricing');
}

export async function registerDomain(registrationData) {
	return fetchAPI('/domains/register', {
		method: 'POST',
		body: JSON.stringify(registrationData)
	});
}

export async function listRegisteredDomains() {
	return fetchAPI('/domains');
}

export async function getDomainDetails(domain) {
	return fetchAPI(`/domains/${encodeURIComponent(domain)}`);
}

export async function updateDomainSettings(domain, settings) {
	return fetchAPI(`/domains/${encodeURIComponent(domain)}`, {
		method: 'PATCH',
		body: JSON.stringify(settings)
	});
}

export async function getCloudflareStatus() {
	return fetchAPI('/domains/cloudflare-status');
}

// Custom Domain (BYOD) API
export async function getCustomDomain() {
	return fetchAPI('/domain/custom');
}

export async function setCustomDomain(domain) {
	return fetchAPI('/domain/custom', {
		method: 'POST',
		body: JSON.stringify({ domain })
	});
}

export async function removeCustomDomain() {
	return fetchAPI('/domain/custom', {
		method: 'DELETE'
	});
}

export async function verifyCustomDomainDns(domain) {
	return fetchAPI('/domain/verify', {
		method: 'POST',
		body: JSON.stringify({ domain })
	});
}

export async function getDomainStatus() {
	return fetchAPI('/domain/status');
}
