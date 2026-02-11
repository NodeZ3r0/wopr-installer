/**
 * WOPR Beacon Theme Presets
 * =========================
 * Each preset defines colors that override the semantic tokens.
 * The ThemeProvider applies these by setting CSS custom properties on :root.
 */

export const presets = {
	reactor: {
		id: 'reactor',
		name: 'Reactor',
		description: 'Default WOPR theme with teal and orange accents',
		colors: {
			'--theme-bg': '#0a0a0a',
			'--theme-surface': '#1a1a1a',
			'--theme-surface-hover': '#252525',
			'--theme-elevated': '#2a2a2a',
			'--theme-border': '#333333',
			'--theme-border-subtle': '#262626',
			'--theme-text': '#e0e0e0',
			'--theme-text-muted': '#888888',
			'--theme-text-on-primary': '#000000',
			'--theme-primary': '#00d4aa',
			'--theme-primary-hover': '#00f0c0',
			'--theme-primary-subtle': 'rgba(0, 212, 170, 0.15)',
			'--theme-accent': '#ff9b3f',
			'--theme-accent-hover': '#ffb366',
			'--theme-accent-subtle': 'rgba(255, 155, 63, 0.15)'
		},
		preview: {
			primary: '#00d4aa',
			accent: '#ff9b3f',
			bg: '#0a0a0a'
		}
	},

	midnight: {
		id: 'midnight',
		name: 'Midnight',
		description: 'Deep violet and purple tones',
		colors: {
			'--theme-bg': '#0c0a1a',
			'--theme-surface': '#1a1730',
			'--theme-surface-hover': '#252240',
			'--theme-elevated': '#2d2950',
			'--theme-border': '#3d3860',
			'--theme-border-subtle': '#2a2545',
			'--theme-text': '#e8e4f0',
			'--theme-text-muted': '#9990b0',
			'--theme-text-on-primary': '#000000',
			'--theme-primary': '#818cf8',
			'--theme-primary-hover': '#a5b4fc',
			'--theme-primary-subtle': 'rgba(129, 140, 248, 0.15)',
			'--theme-accent': '#c084fc',
			'--theme-accent-hover': '#d8b4fe',
			'--theme-accent-subtle': 'rgba(192, 132, 252, 0.15)'
		},
		preview: {
			primary: '#818cf8',
			accent: '#c084fc',
			bg: '#0c0a1a'
		}
	},

	solaris: {
		id: 'solaris',
		name: 'Solaris',
		description: 'Warm amber and orange sunset tones',
		colors: {
			'--theme-bg': '#0f0a05',
			'--theme-surface': '#1a1408',
			'--theme-surface-hover': '#2a2010',
			'--theme-elevated': '#352818',
			'--theme-border': '#4a3520',
			'--theme-border-subtle': '#2d2015',
			'--theme-text': '#f5f0e8',
			'--theme-text-muted': '#b0a080',
			'--theme-text-on-primary': '#000000',
			'--theme-primary': '#fbbf24',
			'--theme-primary-hover': '#fcd34d',
			'--theme-primary-subtle': 'rgba(251, 191, 36, 0.15)',
			'--theme-accent': '#f97316',
			'--theme-accent-hover': '#fb923c',
			'--theme-accent-subtle': 'rgba(249, 115, 22, 0.15)'
		},
		preview: {
			primary: '#fbbf24',
			accent: '#f97316',
			bg: '#0f0a05'
		}
	},

	arctic: {
		id: 'arctic',
		name: 'Arctic',
		description: 'Cool sky blue and cyan tones',
		colors: {
			'--theme-bg': '#050a0f',
			'--theme-surface': '#0a1520',
			'--theme-surface-hover': '#102030',
			'--theme-elevated': '#152838',
			'--theme-border': '#1e3a50',
			'--theme-border-subtle': '#152535',
			'--theme-text': '#e8f4f8',
			'--theme-text-muted': '#80a0b0',
			'--theme-text-on-primary': '#000000',
			'--theme-primary': '#38bdf8',
			'--theme-primary-hover': '#7dd3fc',
			'--theme-primary-subtle': 'rgba(56, 189, 248, 0.15)',
			'--theme-accent': '#22d3ee',
			'--theme-accent-hover': '#67e8f9',
			'--theme-accent-subtle': 'rgba(34, 211, 238, 0.15)'
		},
		preview: {
			primary: '#38bdf8',
			accent: '#22d3ee',
			bg: '#050a0f'
		}
	},

	terminal: {
		id: 'terminal',
		name: 'Terminal',
		description: 'Classic hacker green on black',
		colors: {
			'--theme-bg': '#000000',
			'--theme-surface': '#0a0f0a',
			'--theme-surface-hover': '#101810',
			'--theme-elevated': '#152015',
			'--theme-border': '#1a2a1a',
			'--theme-border-subtle': '#102010',
			'--theme-text': '#e0f0e0',
			'--theme-text-muted': '#60a060',
			'--theme-text-on-primary': '#000000',
			'--theme-primary': '#4ade80',
			'--theme-primary-hover': '#86efac',
			'--theme-primary-subtle': 'rgba(74, 222, 128, 0.15)',
			'--theme-accent': '#22c55e',
			'--theme-accent-hover': '#4ade80',
			'--theme-accent-subtle': 'rgba(34, 197, 94, 0.15)'
		},
		preview: {
			primary: '#4ade80',
			accent: '#22c55e',
			bg: '#000000'
		}
	},

	ember: {
		id: 'ember',
		name: 'Ember',
		description: 'Warm rose and red tones',
		colors: {
			'--theme-bg': '#0f0508',
			'--theme-surface': '#1a0a10',
			'--theme-surface-hover': '#2a1018',
			'--theme-elevated': '#351520',
			'--theme-border': '#4a2030',
			'--theme-border-subtle': '#2d1520',
			'--theme-text': '#f8e8f0',
			'--theme-text-muted': '#b08090',
			'--theme-text-on-primary': '#ffffff',
			'--theme-primary': '#fb7185',
			'--theme-primary-hover': '#fda4af',
			'--theme-primary-subtle': 'rgba(251, 113, 133, 0.15)',
			'--theme-accent': '#f43f5e',
			'--theme-accent-hover': '#fb7185',
			'--theme-accent-subtle': 'rgba(244, 63, 94, 0.15)'
		},
		preview: {
			primary: '#fb7185',
			accent: '#f43f5e',
			bg: '#0f0508'
		}
	}
};

// Get preset by ID with fallback to reactor
export function getPreset(id) {
	return presets[id] || presets.reactor;
}

// Get list of all presets for UI
export function getPresetList() {
	return Object.values(presets);
}

// Default preset ID
export const DEFAULT_PRESET = 'reactor';
