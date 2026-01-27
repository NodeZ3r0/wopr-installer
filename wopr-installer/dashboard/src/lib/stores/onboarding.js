import { writable, derived } from 'svelte/store';

// Onboarding wizard state
export const onboarding = writable({
    // Step tracking
    currentStep: 1,
    maxStep: 5,

    // Step 1: Bundle selection
    bundle: null,           // 'starter', 'creator', 'developer', etc.
    tier: 't1',             // 't1', 't2', 't3'

    // Step 2: Account info
    email: '',
    name: '',
    password: '',

    // Step 3: Beacon configuration
    beaconName: '',         // subdomain (e.g., 'mybeacon' -> mybeacon.wopr.systems)
    provider: 'hetzner',    // 'hetzner', 'contabo', 'bring_your_own'

    // Step 4: Additional users (Family/Business bundles only)
    additionalUsers: [],    // Array of { email, name }

    // Validation states
    beaconAvailable: null,  // null = unchecked, true/false = result
    emailValid: null,
});

// Bundle pricing data (matches stripe_catalog.py)
export const bundlePricing = {
    // Sovereign Suites
    starter: { t1: 1599, t2: 2599, t3: 3599 },
    creator: { t1: 3599, t2: 5599, t3: 9599 },
    developer: { t1: 3599, t2: 5599, t3: 9599 },
    professional: { t1: 6599, t2: 9599, t3: 14999 },
    family: { t1: 4599, t2: 6599, t3: 9599 },
    small_business: { t1: 9599, t2: 14999, t3: 19999 },
    enterprise: { t1: 19999, t2: 29999, t3: 0 },

    // Micro-Bundles
    meeting_room: { t1: 1599, t2: 2599, t3: 3599 },
    privacy_pack: { t1: 1599, t2: 2599, t3: 3599 },
    writer_studio: { t1: 1999, t2: 2999, t3: 4599 },
    artist_storefront: { t1: 1999, t2: 2999, t3: 4599 },
    podcaster: { t1: 2599, t2: 3599, t3: 5599 },
    freelancer: { t1: 2599, t2: 3599, t3: 5599 },
    musician: { t1: 2599, t2: 3599, t3: 5599 },
    family_hub: { t1: 2999, t2: 4599, t3: 6599 },
    photographer: { t1: 2999, t2: 4599, t3: 6599 },
    bookkeeper: { t1: 2999, t2: 4599, t3: 6599 },
    video_creator: { t1: 3599, t2: 5599, t3: 9599 },
    contractor: { t1: 3599, t2: 5599, t3: 9599 },
    realtor: { t1: 3599, t2: 5599, t3: 9599 },
    educator: { t1: 3599, t2: 5599, t3: 9599 },
    therapist: { t1: 4599, t2: 6599, t3: 12599 },
    legal: { t1: 4599, t2: 6599, t3: 12599 },
};

// Bundle metadata
export const bundleInfo = {
    // Sovereign Suites
    starter: {
        name: 'Starter Sovereign Suite',
        description: 'Drive, calendar, notes, tasks, passwords - the essentials to ditch Big Tech.',
        type: 'sovereign',
        maxUsers: 1,
    },
    creator: {
        name: 'Creator Sovereign Suite',
        description: 'Blog, portfolio, online store, newsletter - monetize your work.',
        type: 'sovereign',
        maxUsers: 1,
    },
    developer: {
        name: 'Developer Sovereign Suite',
        description: 'Git hosting, CI/CD, code editor, Reactor AI coding assistant.',
        type: 'sovereign',
        maxUsers: 1,
    },
    professional: {
        name: 'Professional Sovereign Suite',
        description: 'Creator + Developer combined + DEFCON ONE security gateway.',
        type: 'sovereign',
        maxUsers: 1,
    },
    family: {
        name: 'Family Sovereign Suite',
        description: '6 user accounts, shared photos, shared passwords, family calendar.',
        type: 'sovereign',
        maxUsers: 6,
    },
    small_business: {
        name: 'Small Business Sovereign Suite',
        description: 'CRM, team chat, office suite, DEFCON ONE + Reactor AI.',
        type: 'sovereign',
        maxUsers: 25,
    },
    enterprise: {
        name: 'Enterprise Sovereign Suite',
        description: 'Unlimited users, custom integrations, dedicated support, full AI suite.',
        type: 'sovereign',
        maxUsers: -1, // unlimited
    },

    // Micro-Bundles
    meeting_room: {
        name: 'Meeting Room',
        description: 'Video calls, scheduling, collaborative notes - replace Zoom.',
        type: 'micro',
        maxUsers: 1,
    },
    privacy_pack: {
        name: 'Privacy Pack',
        description: 'Encrypted storage, password manager, private VPN - total privacy.',
        type: 'micro',
        maxUsers: 1,
    },
    writer_studio: {
        name: "Writer's Studio",
        description: 'Blog, newsletter, research archive, bookmarks - replace Substack.',
        type: 'micro',
        maxUsers: 1,
    },
    artist_storefront: {
        name: 'Artist Storefront',
        description: 'Online store, portfolio, photo galleries - replace Etsy.',
        type: 'micro',
        maxUsers: 1,
    },
    podcaster: {
        name: 'Podcaster Pack',
        description: 'Podcast hosting, show notes blog, listener analytics - own your feed.',
        type: 'micro',
        maxUsers: 1,
    },
    freelancer: {
        name: 'Freelancer Essentials',
        description: 'Invoicing, scheduling, client contacts - run your business.',
        type: 'micro',
        maxUsers: 1,
    },
    musician: {
        name: 'Musician Bundle',
        description: 'Music streaming, artist website, merch store - own your music.',
        type: 'micro',
        maxUsers: 1,
    },
    family_hub: {
        name: 'Family Hub',
        description: 'Shared drive, photos, passwords for 6 family members.',
        type: 'micro',
        maxUsers: 6,
    },
    photographer: {
        name: 'Photographer Pro',
        description: 'Photo library, client galleries, portfolio, print sales.',
        type: 'micro',
        maxUsers: 1,
    },
    bookkeeper: {
        name: 'Bookkeeper Bundle',
        description: 'Document scanner, client portal, secure messaging.',
        type: 'micro',
        maxUsers: 1,
    },
    video_creator: {
        name: 'Video Creator',
        description: 'Video hosting, community blog, paid memberships - replace YouTube.',
        type: 'micro',
        maxUsers: 1,
    },
    contractor: {
        name: 'Contractor Pro',
        description: 'Digital contracts, project management, time tracking.',
        type: 'micro',
        maxUsers: 1,
    },
    realtor: {
        name: 'Real Estate Agent',
        description: 'Lead CRM, listing photos, digital contracts.',
        type: 'micro',
        maxUsers: 1,
    },
    educator: {
        name: 'Educator Suite',
        description: 'Virtual classroom, whiteboard, file sharing for students.',
        type: 'micro',
        maxUsers: 1,
    },
    therapist: {
        name: 'Therapist/Coach',
        description: 'Secure video sessions, encrypted notes, client portal - HIPAA-ready.',
        type: 'micro',
        maxUsers: 1,
    },
    legal: {
        name: 'Legal Lite',
        description: 'Document management, e-signatures, secure client portal.',
        type: 'micro',
        maxUsers: 1,
    },
};

// Tier info
export const tierInfo = {
    t1: { name: 'Tier 1', storage: '50GB', description: '50GB storage' },
    t2: { name: 'Tier 2', storage: '200GB', description: '200GB storage' },
    t3: { name: 'Tier 3', storage: '500GB+', description: '500GB+ storage' },
};

// VPS provider options
export const providerOptions = [
    {
        id: 'hetzner',
        name: 'Hetzner Cloud',
        description: 'European data centers, excellent performance',
        priceRange: '$5-20/mo',
        recommended: true,
    },
    {
        id: 'contabo',
        name: 'Contabo',
        description: 'Budget-friendly with more storage',
        priceRange: '$5-15/mo',
    },
    {
        id: 'bring_your_own',
        name: 'Bring Your Own Server',
        description: 'Use your existing VPS or dedicated server',
        priceRange: 'Varies',
    },
];

// Derived stores for computed values
export const selectedBundle = derived(onboarding, $o => {
    if (!$o.bundle) return null;
    return {
        id: $o.bundle,
        ...bundleInfo[$o.bundle],
        pricing: bundlePricing[$o.bundle],
    };
});

export const selectedPrice = derived(onboarding, $o => {
    if (!$o.bundle || !$o.tier) return 0;
    return bundlePricing[$o.bundle]?.[$o.tier] || 0;
});

export const formattedPrice = derived(selectedPrice, $price => {
    if ($price === 0) return 'Custom';
    return `$${($price / 100).toFixed(2)}`;
});

export const yearlyPrice = derived(selectedPrice, $price => {
    if ($price === 0) return 0;
    return $price * 10; // 2 months free
});

export const formattedYearlyPrice = derived(yearlyPrice, $yearly => {
    if ($yearly === 0) return 'Custom';
    return `$${($yearly / 100).toFixed(2)}`;
});

export const needsAdditionalUsers = derived(onboarding, $o => {
    if (!$o.bundle) return false;
    const info = bundleInfo[$o.bundle];
    return info && info.maxUsers > 1;
});

export const canProceed = derived(onboarding, $o => {
    switch ($o.currentStep) {
        case 1:
            return $o.bundle && $o.tier;
        case 2:
            return $o.email && $o.name && $o.password && $o.password.length >= 8;
        case 3:
            return $o.beaconName && $o.beaconAvailable === true && $o.provider;
        case 4:
            return true; // Additional users are optional
        case 5:
            return true; // Summary step
        default:
            return false;
    }
});

// Helper functions
export function resetOnboarding() {
    onboarding.set({
        currentStep: 1,
        maxStep: 5,
        bundle: null,
        tier: 't1',
        email: '',
        name: '',
        password: '',
        beaconName: '',
        provider: 'hetzner',
        additionalUsers: [],
        beaconAvailable: null,
        emailValid: null,
    });
}

export function nextStep() {
    onboarding.update(o => ({
        ...o,
        currentStep: Math.min(o.currentStep + 1, o.maxStep),
    }));
}

export function prevStep() {
    onboarding.update(o => ({
        ...o,
        currentStep: Math.max(o.currentStep - 1, 1),
    }));
}

export function goToStep(step) {
    onboarding.update(o => ({
        ...o,
        currentStep: Math.max(1, Math.min(step, o.maxStep)),
    }));
}

export function setBundle(bundleId, tier = 't1') {
    onboarding.update(o => ({
        ...o,
        bundle: bundleId,
        tier: tier,
    }));
}

export function addUser(email, name) {
    onboarding.update(o => ({
        ...o,
        additionalUsers: [...o.additionalUsers, { email, name }],
    }));
}

export function removeUser(index) {
    onboarding.update(o => ({
        ...o,
        additionalUsers: o.additionalUsers.filter((_, i) => i !== index),
    }));
}
