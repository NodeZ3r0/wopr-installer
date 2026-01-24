/**
 * WOPR Beacon Theme Store
 * =======================
 *
 * Svelte stores for theme state management.
 * Handles preset selection, custom colors, and per-app overrides.
 */

import { writable, derived, get } from 'svelte/store';
import { presets, getPreset, DEFAULT_PRESET } from '$lib/themes/presets.js';

// ============================================
// STORES
// ============================================

/**
 * Main theme configuration store.
 * Synced with backend API.
 */
export const themeConfig = writable({
	preset: DEFAULT_PRESET,
	customColors: {},
	appOverrides: {},
	themedApps: ['defcon', 'brainjoos', 'rag'],
	availablePresets: Object.values(presets),
});

/**
 * Loading state for theme operations.
 */
export const themeLoading = writable(false);

/**
 * Error state for theme operations.
 */
export const themeError = writable(null);

/**
 * Whether theme has been loaded from API.
 */
export const themeInitialized = writable(false);

// ============================================
// DERIVED STORES
// ============================================

/**
 * Current preset object.
 */
export const currentPreset = derived(themeConfig, ($config) => {
	return getPreset($config.preset);
});

/**
 * Computed CSS variables for current theme.
 * Merges preset colors with custom overrides.
 */
export const themeVars = derived(themeConfig, ($config) => {
	const preset = getPreset($config.preset);
	const baseColors = preset?.colors || {};

	// Merge base colors with custom overrides
	return {
		...baseColors,
		...$config.customColors,
	};
});

/**
 * Preview colors for UI display.
 */
export const themePreview = derived(themeConfig, ($config) => {
	const preset = getPreset($config.preset);
	return preset?.preview || {
		primary: '#00d4aa',
		accent: '#ff9b3f',
		bg: '#0a0a0a',
	};
});

// ============================================
// ACTIONS
// ============================================

/**
 * Apply CSS variables to document root.
 * Called when theme changes.
 */
export function applyTheme(vars) {
	const root = document.documentElement;

	for (const [property, value] of Object.entries(vars)) {
		root.style.setProperty(property, value);
	}
}

/**
 * Set theme preset.
 * @param {string} presetId - Preset ID to apply
 */
export function setPreset(presetId) {
	const preset = getPreset(presetId);
	if (!preset) {
		console.warn(`Unknown theme preset: ${presetId}`);
		return;
	}

	themeConfig.update((config) => ({
		...config,
		preset: presetId,
	}));

	// Apply immediately
	applyTheme(preset.colors);

	// Persist to localStorage for instant load on refresh
	try {
		localStorage.setItem('wopr-theme-preset', presetId);
	} catch (e) {
		console.warn('Failed to save theme to localStorage:', e);
	}
}

/**
 * Set custom color override.
 * @param {string} variable - CSS variable name (e.g., '--theme-primary')
 * @param {string} value - Color value (hex)
 */
export function setCustomColor(variable, value) {
	themeConfig.update((config) => ({
		...config,
		customColors: {
			...config.customColors,
			[variable]: value,
		},
	}));

	// Apply immediately
	document.documentElement.style.setProperty(variable, value);
}

/**
 * Clear all custom color overrides.
 */
export function clearCustomColors() {
	const config = get(themeConfig);
	const preset = getPreset(config.preset);

	themeConfig.update((c) => ({
		...c,
		customColors: {},
	}));

	// Reapply preset colors
	if (preset) {
		applyTheme(preset.colors);
	}
}

/**
 * Toggle theme injection for an app.
 * @param {string} appId - App identifier
 * @param {boolean} enabled - Whether to enable theming
 */
export function toggleAppTheming(appId, enabled) {
	themeConfig.update((config) => {
		const themedApps = new Set(config.themedApps);

		if (enabled) {
			themedApps.add(appId);
		} else {
			// Native apps cannot be disabled
			if (!['defcon', 'brainjoos', 'rag'].includes(appId)) {
				themedApps.delete(appId);
			}
		}

		return {
			...config,
			themedApps: Array.from(themedApps),
		};
	});
}

/**
 * Set per-app theme override.
 * @param {string} appId - App identifier
 * @param {string|null} presetId - Preset ID or null to inherit global
 */
export function setAppTheme(appId, presetId) {
	themeConfig.update((config) => {
		const appOverrides = { ...config.appOverrides };

		if (presetId === null || presetId === 'inherit') {
			delete appOverrides[appId];
		} else {
			appOverrides[appId] = { preset: presetId };
		}

		return {
			...config,
			appOverrides,
		};
	});
}

/**
 * Initialize theme from localStorage (instant) then sync with API.
 */
export function initTheme() {
	// First, try localStorage for instant load
	try {
		const savedPreset = localStorage.getItem('wopr-theme-preset');
		if (savedPreset && presets[savedPreset]) {
			setPreset(savedPreset);
		}
	} catch (e) {
		console.warn('Failed to load theme from localStorage:', e);
	}

	themeInitialized.set(true);
}

/**
 * Load theme configuration from API.
 * @param {Function} fetchFn - API fetch function (from api.js)
 */
export async function loadThemeFromAPI(fetchFn) {
	themeLoading.set(true);
	themeError.set(null);

	try {
		const response = await fetchFn();

		themeConfig.set({
			preset: response.preset || DEFAULT_PRESET,
			customColors: response.custom_colors || {},
			appOverrides: response.app_overrides || {},
			themedApps: response.themed_apps || ['defcon', 'brainjoos', 'rag'],
			availablePresets: response.available_presets || Object.values(presets),
		});

		// Apply theme
		const preset = getPreset(response.preset);
		if (preset) {
			applyTheme({
				...preset.colors,
				...response.custom_colors,
			});
		}

		// Save to localStorage
		try {
			localStorage.setItem('wopr-theme-preset', response.preset);
		} catch (e) {
			// Ignore
		}

		themeInitialized.set(true);
	} catch (error) {
		console.error('Failed to load theme from API:', error);
		themeError.set(error.message);
	} finally {
		themeLoading.set(false);
	}
}

/**
 * Save theme configuration to API.
 * @param {Function} saveFn - API save function (from api.js)
 */
export async function saveThemeToAPI(saveFn) {
	themeLoading.set(true);
	themeError.set(null);

	const config = get(themeConfig);

	try {
		await saveFn({
			preset: config.preset,
			custom_colors: config.customColors,
			themed_apps: config.themedApps,
		});
	} catch (error) {
		console.error('Failed to save theme to API:', error);
		themeError.set(error.message);
		throw error;
	} finally {
		themeLoading.set(false);
	}
}
