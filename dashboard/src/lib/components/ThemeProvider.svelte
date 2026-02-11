<script>
	/**
	 * ThemeProvider Component
	 * =======================
	 *
	 * Wraps the app and manages theme state.
	 * - Loads theme from localStorage on mount (instant)
	 * - Syncs with API when available
	 * - Applies CSS variables to document root
	 * - Provides theme context to children
	 */

	import { onMount, setContext } from 'svelte';
	import {
		themeConfig,
		themeVars,
		themeLoading,
		themeError,
		themeInitialized,
		currentPreset,
		initTheme,
		loadThemeFromAPI,
		saveThemeToAPI,
		setPreset,
		setCustomColor,
		clearCustomColors,
		toggleAppTheming,
		setAppTheme,
		applyTheme,
	} from '$lib/stores/theme.js';
	import { getTheme, updateTheme } from '$lib/api.js';

	// Provide theme context to children
	setContext('theme', {
		config: themeConfig,
		vars: themeVars,
		loading: themeLoading,
		error: themeError,
		initialized: themeInitialized,
		currentPreset,
		setPreset,
		setCustomColor,
		clearCustomColors,
		toggleAppTheming,
		setAppTheme,
		save: () => saveThemeToAPI(updateTheme),
		reload: () => loadThemeFromAPI(getTheme),
	});

	// Subscribe to theme changes and apply CSS
	$: if ($themeInitialized && $themeVars) {
		applyTheme($themeVars);
	}

	onMount(() => {
		// Initialize from localStorage first (instant)
		initTheme();

		// Then sync with API (may update if server has different config)
		loadThemeFromAPI(getTheme).catch((err) => {
			// API might not be available in dev, that's ok
			console.warn('Theme API not available:', err.message);
		});
	});
</script>

<slot />

<style>
	/* Theme transition for smooth color changes */
	:global(body) {
		transition:
			background-color 0.2s ease,
			color 0.2s ease;
	}

	:global(.card),
	:global(.btn),
	:global(.sidebar),
	:global(nav),
	:global(input),
	:global(select) {
		transition:
			background-color 0.2s ease,
			border-color 0.2s ease,
			color 0.2s ease;
	}
</style>
