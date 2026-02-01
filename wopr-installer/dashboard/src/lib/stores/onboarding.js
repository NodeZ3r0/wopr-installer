import { writable, derived } from 'svelte/store';

// Onboarding wizard state
export const onboarding = writable({
    // Step tracking (4 steps now)
    currentStep: 1,
    maxStep: 4,

    // Step 1: Bundle selection
    bundle: null,           // 'starter', 'creator', 'developer', etc.

    // Step 2: Plan size + region
    tier: 't1',             // 't1', 't2', 't3'
    region: 'auto',         // 'auto', 'us-east', 'eu-west'

    // Step 3: Account + beacon (merged)
    email: '',
    name: '',
    password: '',
    beaconName: '',         // subdomain (e.g., 'mybeacon' -> mybeacon.wopr.systems)
    additionalUsers: [],    // Array of { email, name }

    // Validation states
    beaconAvailable: null,  // null = unchecked, true/false = result
    emailValid: null,
});

// Bundle pricing in cents (matches stripe_catalog.py — updated Feb 2026)
export const bundlePricing = {
    // Sovereign Suites (Complete Packages)
    starter: { t1: 2999, t2: 4599, t3: 6599 },
    creator: { t1: 5599, t2: 7999, t3: 11999 },
    developer: { t1: 5599, t2: 7999, t3: 11999 },
    professional: { t1: 9999, t2: 14999, t3: 19999 },
    family: { t1: 5599, t2: 7999, t3: 11999 },
    small_business: { t1: 12999, t2: 17999, t3: 24999 },
    enterprise: { t1: 24999, t2: 34999, t3: 0 }, // t3 = custom

    // Light Micro-Bundles (4GB MEDIUM VPS)
    personal_productivity: { t1: 2999, t2: 4599, t3: 6599 },
    meeting_room: { t1: 2999, t2: 4599, t3: 6599 },
    privacy_pack: { t1: 2999, t2: 4599, t3: 6599 },
    writer_studio: { t1: 2999, t2: 4599, t3: 6599 },
    podcaster: { t1: 3599, t2: 5599, t3: 7999 },
    freelancer: { t1: 3599, t2: 5599, t3: 7999 },
    contractor: { t1: 3599, t2: 5599, t3: 7999 },
    musician: { t1: 3599, t2: 5599, t3: 7999 },
    bookkeeper: { t1: 3599, t2: 5599, t3: 7999 },

    // Medium Micro-Bundles (8GB HIGH VPS)
    artist_storefront: { t1: 4599, t2: 6599, t3: 9599 },
    family_hub: { t1: 4599, t2: 6599, t3: 9599 },
    photographer: { t1: 5599, t2: 7999, t3: 11999 },
    video_creator: { t1: 4599, t2: 6599, t3: 9599 },
    realtor: { t1: 4599, t2: 6599, t3: 9599 },
    educator: { t1: 4599, t2: 6599, t3: 9599 },
    therapist: { t1: 5599, t2: 7999, t3: 11999 },
    legal: { t1: 5599, t2: 7999, t3: 11999 },
};

// Bundle metadata
export const bundleInfo = {
    // Complete Packages (Sovereign Suites)
    starter: {
        name: 'Starter',
        description: 'Cloud drive, calendar, notes, tasks, and passwords — everything you need to get off Big Tech.',
        type: 'sovereign',
        maxUsers: 5,
    },
    creator: {
        name: 'Creator',
        description: 'Blog, portfolio, online store, and newsletter — share your work and get paid for it.',
        type: 'sovereign',
        maxUsers: 5,
    },
    developer: {
        name: 'Developer',
        description: 'Your own Git server, CI/CD pipeline, code editor, and AI coding assistant.',
        type: 'sovereign',
        maxUsers: 5,
    },
    professional: {
        name: 'Professional',
        description: 'Everything from Creator and Developer combined, plus a security gateway.',
        type: 'sovereign',
        maxUsers: 5,
    },
    family: {
        name: 'Family',
        description: 'Shared photos, passwords, calendars, and cloud drive for up to 6 family members.',
        type: 'sovereign',
        maxUsers: 6,
    },
    small_business: {
        name: 'Small Business',
        description: 'CRM, team chat, office apps, security gateway, and AI assistant for your team.',
        type: 'sovereign',
        maxUsers: 25,
    },
    enterprise: {
        name: 'Enterprise',
        description: 'Unlimited users, custom integrations, dedicated support, and the full AI suite.',
        type: 'sovereign',
        maxUsers: -1, // unlimited
    },

    // Built for You (Micro-Bundles)
    personal_productivity: {
        name: 'Personal Productivity',
        description: 'Drive, calendar, notes, tasks — the basics to replace Google.',
        type: 'micro',
        maxUsers: 5,
    },
    meeting_room: {
        name: 'Meeting Room',
        description: 'Video calls, scheduling, and shared notes — replace Zoom.',
        type: 'micro',
        maxUsers: 5,
    },
    privacy_pack: {
        name: 'Privacy Pack',
        description: 'Encrypted storage, password manager, and private VPN — total privacy.',
        type: 'micro',
        maxUsers: 5,
    },
    writer_studio: {
        name: "Writer's Studio",
        description: 'Blog, newsletter, research archive — replace Substack and own your words.',
        type: 'micro',
        maxUsers: 5,
    },
    artist_storefront: {
        name: 'Artist Storefront',
        description: 'Online store, portfolio, and photo galleries — replace Etsy.',
        type: 'micro',
        maxUsers: 5,
    },
    podcaster: {
        name: 'Podcaster',
        description: 'Podcast hosting, show notes blog, and listener stats — own your feed.',
        type: 'micro',
        maxUsers: 5,
    },
    freelancer: {
        name: 'Freelancer',
        description: 'Invoicing, scheduling, and client contacts — run your business.',
        type: 'micro',
        maxUsers: 5,
    },
    musician: {
        name: 'Musician',
        description: 'Music streaming, artist website, and merch store — own your music.',
        type: 'micro',
        maxUsers: 5,
    },
    family_hub: {
        name: 'Family Hub',
        description: 'Shared drive, photos, and passwords for up to 6 family members.',
        type: 'micro',
        maxUsers: 6,
    },
    photographer: {
        name: 'Photographer',
        description: 'Photo library, client galleries, portfolio, and print sales.',
        type: 'micro',
        maxUsers: 5,
    },
    bookkeeper: {
        name: 'Bookkeeper',
        description: 'Document scanner, client portal, and secure messaging.',
        type: 'micro',
        maxUsers: 5,
    },
    video_creator: {
        name: 'Video Creator',
        description: 'Video hosting, community blog, and paid memberships — replace YouTube.',
        type: 'micro',
        maxUsers: 5,
    },
    contractor: {
        name: 'Contractor',
        description: 'Digital contracts, project management, and time tracking.',
        type: 'micro',
        maxUsers: 5,
    },
    realtor: {
        name: 'Real Estate Agent',
        description: 'Lead CRM, listing photos, and digital contracts.',
        type: 'micro',
        maxUsers: 5,
    },
    educator: {
        name: 'Educator',
        description: 'Virtual classroom, whiteboard, and file sharing for students.',
        type: 'micro',
        maxUsers: 5,
    },
    therapist: {
        name: 'Therapist / Coach',
        description: 'Secure video sessions, encrypted notes, and client portal — HIPAA-ready.',
        type: 'micro',
        maxUsers: 5,
    },
    legal: {
        name: 'Legal Lite',
        description: 'Document management, e-signatures, and secure client portal.',
        type: 'micro',
        maxUsers: 5,
    },
};

// Plan size labels (customer-facing names for tiers)
export const tierLabels = {
    t1: 'Basic',
    t2: 'Plus',
    t3: 'Max',
};

// Plan size details (6th grade reading level)
export const tierDetails = {
    t1: {
        name: 'Basic',
        storage: '50 GB',
        storageContext: 'About 10,000 photos',
        users: 'Up to 5 users',
        backups: 'Weekly backups',
        description: 'Great for getting started',
    },
    t2: {
        name: 'Plus',
        storage: '200 GB',
        storageContext: 'About 40,000 photos',
        users: 'Up to 25 users',
        backups: 'Daily backups',
        description: 'Room to grow — most popular',
        popular: true,
    },
    t3: {
        name: 'Max',
        storage: '500 GB+',
        storageContext: 'About 100,000 photos',
        users: 'Up to 100 users',
        backups: 'Daily backups, 90 days of history',
        description: 'Power user — no limits',
    },
};

// Region options (user-facing)
export const regionOptions = [
    {
        id: 'auto',
        name: 'Automatic',
        description: "We'll pick the closest server to you",
        flag: '🌐',
    },
    {
        id: 'us-east',
        name: 'US East',
        description: 'Virginia, USA',
        flag: '🇺🇸',
    },
    {
        id: 'eu-west',
        name: 'Europe',
        description: 'Falkenstein, Germany',
        flag: '🇪🇺',
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
            return !!$o.bundle;
        case 2:
            return !!$o.tier && !!$o.region;
        case 3:
            return $o.email && $o.name && $o.password && $o.password.length >= 8
                && $o.beaconName && $o.beaconAvailable === true;
        case 4:
            return true; // Review step
        default:
            return false;
    }
});

// Helper functions
export function resetOnboarding() {
    onboarding.set({
        currentStep: 1,
        maxStep: 4,
        bundle: null,
        tier: 't1',
        region: 'auto',
        email: '',
        name: '',
        password: '',
        beaconName: '',
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

export function setRegion(regionId) {
    onboarding.update(o => ({
        ...o,
        region: regionId,
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

export function formatPrice(cents) {
    if (cents === 0) return 'Custom';
    return `$${(cents / 100).toFixed(2)}`;
}
