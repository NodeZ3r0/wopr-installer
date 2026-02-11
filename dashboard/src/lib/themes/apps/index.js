/**
 * WOPR App Theme Overrides Index
 * ===============================
 *
 * Registry of app-specific CSS overrides that map WOPR theme
 * variables to each app's native CSS selectors.
 *
 * Each app has:
 * - id: Module ID from registry
 * - name: Display name
 * - compatibility: 'full' | 'partial' | 'minimal'
 * - cssFile: Path to the override CSS file
 * - selectors: Key selectors that get themed
 */

export const appThemeOverrides = {
	// =====================================
	// PERSONAL BUNDLE APPS
	// =====================================

	nextcloud: {
		id: 'nextcloud',
		name: 'Nextcloud',
		compatibility: 'full',
		description: 'Full theme support - header, sidebar, buttons, and accents',
		cssFile: 'nextcloud.css',
		selectors: [
			'header#header',
			'.app-navigation',
			'.button.primary',
			'input:focus',
			'.icon-confirm',
		],
	},

	vaultwarden: {
		id: 'vaultwarden',
		name: 'Vaultwarden',
		compatibility: 'partial',
		description: 'Partial support - buttons, links, and form elements',
		cssFile: 'vaultwarden.css',
		selectors: [
			'.btn.btn-primary',
			'.btn.btn-outline-primary',
			'a:hover',
			'input:focus',
		],
	},

	freshrss: {
		id: 'freshrss',
		name: 'FreshRSS',
		compatibility: 'full',
		description: 'Full theme support - sidebar, header, and article styling',
		cssFile: 'freshrss.css',
		selectors: [
			'.aside',
			'.nav-head',
			'.item.active',
			'.btn',
		],
	},

	authentik: {
		id: 'authentik',
		name: 'Authentik',
		compatibility: 'full',
		description: 'Full theme support - login page, admin interface',
		cssFile: 'authentik.css',
		selectors: [
			'.pf-c-page',
			'.pf-c-button.pf-m-primary',
			'.pf-c-nav__link',
			'.ak-brand',
		],
	},

	// =====================================
	// CREATOR BUNDLE APPS
	// =====================================

	ghost: {
		id: 'ghost',
		name: 'Ghost',
		compatibility: 'partial',
		description: 'Admin panel theming - editor and dashboard',
		cssFile: 'ghost.css',
		selectors: [
			'.gh-nav',
			'.gh-btn.gh-btn-primary',
			'.gh-publishmenu-trigger',
		],
	},

	saleor: {
		id: 'saleor',
		name: 'Saleor',
		compatibility: 'partial',
		description: 'Dashboard theming - navigation and buttons',
		cssFile: 'saleor.css',
		selectors: [
			'.MuiButton-containedPrimary',
			'.MuiAppBar-root',
		],
	},

	// =====================================
	// DEVELOPER BUNDLE APPS
	// =====================================

	forgejo: {
		id: 'forgejo',
		name: 'Forgejo',
		compatibility: 'full',
		description: 'Full theme support - Forgejo has CSS variable support',
		cssFile: 'forgejo.css',
		selectors: [
			'.ui.primary.button',
			'.ui.menu .active.item',
			'.repository',
		],
	},

	woodpecker: {
		id: 'woodpecker',
		name: 'Woodpecker CI',
		compatibility: 'partial',
		description: 'Navigation and status colors',
		cssFile: 'woodpecker.css',
		selectors: [
			'.navbar',
			'.btn-primary',
			'.status-success',
		],
	},

	code_server: {
		id: 'code_server',
		name: 'VS Code Server',
		compatibility: 'minimal',
		description: 'VS Code has its own theming - minimal override',
		cssFile: 'code-server.css',
		selectors: [
			// VS Code themes are handled internally
		],
	},

	uptime_kuma: {
		id: 'uptime_kuma',
		name: 'Uptime Kuma',
		compatibility: 'full',
		description: 'Full theme support - uses CSS variables',
		cssFile: 'uptime-kuma.css',
		selectors: [
			'.navbar',
			'.btn-primary',
			'.monitor-list',
		],
	},

	// =====================================
	// COMMUNICATION APPS
	// =====================================

	element: {
		id: 'element',
		name: 'Element',
		compatibility: 'full',
		description: 'Full theme support - Element uses CSS variables',
		cssFile: 'element.css',
		selectors: [
			'.mx_RoomHeader',
			'.mx_AccessibleButton_kind_primary',
			'.mx_LeftPanel',
		],
	},

	// =====================================
	// MEDIA APPS
	// =====================================

	immich: {
		id: 'immich',
		name: 'Immich',
		compatibility: 'partial',
		description: 'Photo backup - navigation and button theming',
		cssFile: 'immich.css',
		selectors: [
			'.side-bar',
			'button.primary',
			'.album-card',
		],
	},

	jellyfin: {
		id: 'jellyfin',
		name: 'Jellyfin',
		compatibility: 'full',
		description: 'Full theme support - Jellyfin has CSS variable support',
		cssFile: 'jellyfin.css',
		selectors: [
			'.mainDrawer',
			'.raised.emby-button',
			'.headerButton',
		],
	},
};

/**
 * Get theme override info for an app
 */
export function getAppThemeInfo(appId) {
	return appThemeOverrides[appId] || null;
}

/**
 * Get all apps with full compatibility
 */
export function getFullyThemedApps() {
	return Object.values(appThemeOverrides).filter(
		(app) => app.compatibility === 'full'
	);
}

/**
 * Get apps by compatibility level
 */
export function getAppsByCompatibility(level) {
	return Object.values(appThemeOverrides).filter(
		(app) => app.compatibility === level
	);
}

/**
 * Check if an app supports theming
 */
export function isThemeable(appId) {
	return appId in appThemeOverrides;
}
