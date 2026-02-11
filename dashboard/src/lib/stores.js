import { writable } from 'svelte/store';

// Instance state
export const instance = writable({
	status: 'loading',
	bundle: null,
	domain: null,
	modules: []
});

// Module list
export const modules = writable([]);

// Available trials
export const trials = writable([]);

// User info (from Authentik headers)
export const user = writable({
	username: null,
	email: null,
	groups: []
});

// UI state
export const loading = writable(false);
export const error = writable(null);

// Notification helper
export const notifications = writable([]);

export function notify(message, type = 'info') {
	const id = Date.now();
	notifications.update(n => [...n, { id, message, type }]);

	// Auto-dismiss after 5 seconds
	setTimeout(() => {
		notifications.update(n => n.filter(notif => notif.id !== id));
	}, 5000);
}
