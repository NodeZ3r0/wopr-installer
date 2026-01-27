/**
 * WOPR Checkout Integration
 *
 * Handles bundle selection and Stripe checkout flow for wopr.systems/join
 *
 * Usage:
 *   <script src="/static/js/wopr-checkout.js"></script>
 *   <script>
 *     WOPRCheckout.init({
 *       apiUrl: 'https://api.wopr.systems',
 *       onError: (error) => console.error(error),
 *     });
 *   </script>
 */

const WOPRCheckout = (function() {
    'use strict';

    // Configuration
    let config = {
        apiUrl: 'https://api.wopr.systems',
        successUrl: 'https://wopr.systems/checkout/success',
        cancelUrl: 'https://wopr.systems/join',
        onError: null,
        onCheckoutStart: null,
        onCheckoutComplete: null,
    };

    // Current selection state
    let currentSelection = {
        bundleType: null,  // 'sovereign' or 'micro'
        bundleId: null,    // e.g., 'starter', 'meeting_room'
        storageTier: 1,    // 1, 2, or 3
        email: null,
        domain: null,
        username: null,
        displayName: null,
    };

    /**
     * Initialize checkout with config
     */
    function init(userConfig) {
        if (userConfig) {
            Object.assign(config, userConfig);
        }

        // Bind event listeners to bundle cards
        bindBundleCards();
        bindTierButtons();
        bindCheckoutButtons();

        console.log('WOPR Checkout initialized');
    }

    /**
     * Bind click events to bundle selection cards
     */
    function bindBundleCards() {
        // Sovereign suite cards
        document.querySelectorAll('[data-bundle-type="sovereign"]').forEach(card => {
            card.addEventListener('click', function() {
                selectBundle('sovereign', this.dataset.bundleId);
            });
        });

        // Micro bundle cards
        document.querySelectorAll('[data-bundle-type="micro"]').forEach(card => {
            card.addEventListener('click', function() {
                selectBundle('micro', this.dataset.bundleId);
            });
        });
    }

    /**
     * Bind click events to storage tier buttons
     */
    function bindTierButtons() {
        document.querySelectorAll('[data-storage-tier]').forEach(button => {
            button.addEventListener('click', function() {
                selectTier(parseInt(this.dataset.storageTier));
            });
        });
    }

    /**
     * Bind checkout/subscribe buttons
     */
    function bindCheckoutButtons() {
        document.querySelectorAll('[data-checkout-button]').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                startCheckout();
            });
        });

        // Also handle forms with checkout action
        document.querySelectorAll('form[data-checkout-form]').forEach(form => {
            form.addEventListener('submit', function(e) {
                e.preventDefault();

                // Extract form data
                const formData = new FormData(form);
                currentSelection.email = formData.get('email');
                currentSelection.domain = formData.get('domain');
                currentSelection.username = formData.get('username');
                currentSelection.displayName = formData.get('display_name');

                startCheckout();
            });
        });
    }

    /**
     * Select a bundle
     */
    function selectBundle(bundleType, bundleId) {
        currentSelection.bundleType = bundleType;
        currentSelection.bundleId = bundleId;

        // Update UI
        document.querySelectorAll('[data-bundle-type]').forEach(card => {
            card.classList.remove('selected', 'border-primary', 'ring-2');
        });

        const selectedCard = document.querySelector(
            `[data-bundle-type="${bundleType}"][data-bundle-id="${bundleId}"]`
        );
        if (selectedCard) {
            selectedCard.classList.add('selected', 'border-primary', 'ring-2');
        }

        // Show tier selection
        const tierSection = document.getElementById('tier-selection');
        if (tierSection) {
            tierSection.classList.remove('hidden');
        }

        // Update displayed prices for selected bundle
        updateDisplayedPrices();

        console.log(`Selected: ${bundleType}-${bundleId}`);
    }

    /**
     * Select a storage tier
     */
    function selectTier(tier) {
        currentSelection.storageTier = tier;

        // Update UI
        document.querySelectorAll('[data-storage-tier]').forEach(button => {
            button.classList.remove('selected', 'bg-primary', 'text-white');
            button.classList.add('bg-gray-100');
        });

        const selectedButton = document.querySelector(`[data-storage-tier="${tier}"]`);
        if (selectedButton) {
            selectedButton.classList.remove('bg-gray-100');
            selectedButton.classList.add('selected', 'bg-primary', 'text-white');
        }

        // Show checkout section
        const checkoutSection = document.getElementById('checkout-section');
        if (checkoutSection) {
            checkoutSection.classList.remove('hidden');
        }

        // Update total price display
        updateTotalPrice();

        console.log(`Selected tier: ${tier}`);
    }

    /**
     * Update displayed prices based on selected bundle
     */
    function updateDisplayedPrices() {
        if (!currentSelection.bundleType || !currentSelection.bundleId) return;

        // Fetch prices from API
        fetch(`${config.apiUrl}/api/checkout/prices`)
            .then(response => response.json())
            .then(data => {
                const bundleData = data[currentSelection.bundleType]?.[currentSelection.bundleId];
                if (!bundleData) return;

                // Update tier price displays
                [1, 2, 3].forEach(tier => {
                    const priceEl = document.querySelector(`[data-tier-price="${tier}"]`);
                    if (priceEl && bundleData.prices?.[`tier_${tier}`]) {
                        // Price ID doesn't contain price, need to look it up
                        // For now, use the static prices from page
                    }
                });
            })
            .catch(error => {
                console.error('Error fetching prices:', error);
            });
    }

    /**
     * Update total price display
     */
    function updateTotalPrice() {
        const priceEl = document.getElementById('total-price');
        if (!priceEl) return;

        // Get price from the tier button
        const tierButton = document.querySelector(
            `[data-storage-tier="${currentSelection.storageTier}"]`
        );
        if (tierButton && tierButton.dataset.price) {
            priceEl.textContent = tierButton.dataset.price;
        }
    }

    /**
     * Set selection programmatically
     */
    function setSelection(selection) {
        Object.assign(currentSelection, selection);
    }

    /**
     * Get current selection
     */
    function getSelection() {
        return { ...currentSelection };
    }

    /**
     * Start the checkout process
     */
    async function startCheckout() {
        if (!currentSelection.bundleType || !currentSelection.bundleId) {
            handleError('Please select a bundle');
            return;
        }

        if (!currentSelection.storageTier) {
            handleError('Please select a storage tier');
            return;
        }

        // Call onCheckoutStart callback
        if (config.onCheckoutStart) {
            config.onCheckoutStart(currentSelection);
        }

        // Show loading state
        const checkoutButton = document.querySelector('[data-checkout-button]');
        if (checkoutButton) {
            checkoutButton.disabled = true;
            checkoutButton.textContent = 'Processing...';
        }

        try {
            const bundle = `${currentSelection.bundleType}-${currentSelection.bundleId}`;

            const response = await fetch(`${config.apiUrl}/api/checkout/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    bundle: bundle,
                    tier: currentSelection.storageTier,
                    email: currentSelection.email,
                    domain: currentSelection.domain,
                    username: currentSelection.username,
                    display_name: currentSelection.displayName,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Checkout failed');
            }

            const data = await response.json();

            // Call onCheckoutComplete callback
            if (config.onCheckoutComplete) {
                config.onCheckoutComplete(data);
            }

            // Redirect to Stripe Checkout
            if (data.checkout_url) {
                window.location.href = data.checkout_url;
            }

        } catch (error) {
            handleError(error.message);

            // Reset button
            if (checkoutButton) {
                checkoutButton.disabled = false;
                checkoutButton.textContent = 'Subscribe';
            }
        }
    }

    /**
     * Handle errors
     */
    function handleError(message) {
        console.error('Checkout error:', message);

        if (config.onError) {
            config.onError(message);
        } else {
            alert(message);
        }
    }

    /**
     * Quick checkout - for direct links with bundle pre-selected
     * Usage: WOPRCheckout.quickCheckout('sovereign-starter', 1, 'user@email.com')
     */
    async function quickCheckout(bundle, tier, email, metadata = {}) {
        currentSelection.bundleType = bundle.split('-')[0];
        currentSelection.bundleId = bundle.split('-').slice(1).join('-');
        currentSelection.storageTier = tier;
        currentSelection.email = email;

        if (metadata.domain) currentSelection.domain = metadata.domain;
        if (metadata.username) currentSelection.username = metadata.username;
        if (metadata.displayName) currentSelection.displayName = metadata.displayName;

        await startCheckout();
    }

    // Public API
    return {
        init,
        selectBundle,
        selectTier,
        setSelection,
        getSelection,
        startCheckout,
        quickCheckout,
    };
})();

// Auto-initialize if data attribute present
document.addEventListener('DOMContentLoaded', function() {
    const autoInit = document.querySelector('[data-wopr-checkout-auto]');
    if (autoInit) {
        WOPRCheckout.init({
            apiUrl: autoInit.dataset.apiUrl || 'https://api.wopr.systems',
        });
    }
});
