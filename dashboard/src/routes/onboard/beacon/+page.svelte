<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	// This page has been merged into /onboard/account (Step 3)
	onMount(() => {
		goto('/onboard/account');
	});
</script>
