# WOPR Systems - Stripe Product Setup Script
# ==========================================
#
# Creates all 69 Stripe products for WOPR bundles:
# - 7 Sovereign Suites × 3 tiers = 21 products
# - 16 Micro-Bundles × 3 tiers = 48 products
#
# Prerequisites:
# 1. Stripe CLI installed (winget install Stripe.StripeCli)
# 2. Stripe CLI logged in (stripe login)
#
# Usage:
#   .\stripe-setup.ps1           # Test mode
#   .\stripe-setup.ps1 -Live     # Live mode (real money!)
#   .\stripe-setup.ps1 -ExportCatalog  # Export price IDs to Python file

param(
    [switch]$Live,
    [switch]$ExportCatalog
)

$StripeCLI = "C:\Users\sbink\AppData\Local\Microsoft\WinGet\Packages\Stripe.StripeCli_Microsoft.Winget.Source_8wekyb3d8bbwe\stripe.exe"

if (-not (Test-Path $StripeCLI)) {
    Write-Host "Stripe CLI not found at expected path. Trying 'stripe' command..." -ForegroundColor Yellow
    $StripeCLI = "stripe"
}

$ModeFlag = ""
if ($Live) {
    Write-Host "=== LIVE MODE - Real money will be charged ===" -ForegroundColor Red
    $confirm = Read-Host "Type 'CONFIRM' to proceed"
    if ($confirm -ne "CONFIRM") {
        Write-Host "Aborted." -ForegroundColor Yellow
        exit
    }
    $ModeFlag = "--live"
} else {
    Write-Host "=== TEST MODE - No real charges ===" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "WOPR Systems - Stripe Product Setup (69 Products)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# PRODUCT DEFINITIONS
# ============================================

# Sovereign Suites (7 bundles)
$SovereignSuites = @(
    @{
        id = "starter"
        name = "Starter Sovereign Suite"
        description = "Drive, calendar, notes, tasks, passwords - the essentials to ditch Big Tech."
        prices = @{ t1 = 1599; t2 = 2599; t3 = 3599 }
    },
    @{
        id = "creator"
        name = "Creator Sovereign Suite"
        description = "Blog, portfolio, online store, newsletter - monetize your work."
        prices = @{ t1 = 3599; t2 = 5599; t3 = 9599 }
    },
    @{
        id = "developer"
        name = "Developer Sovereign Suite"
        description = "Git hosting, CI/CD, code editor, Reactor AI coding assistant."
        prices = @{ t1 = 3599; t2 = 5599; t3 = 9599 }
    },
    @{
        id = "professional"
        name = "Professional Sovereign Suite"
        description = "Creator + Developer combined + DEFCON ONE security gateway."
        prices = @{ t1 = 6599; t2 = 9599; t3 = 14999 }
    },
    @{
        id = "family"
        name = "Family Sovereign Suite"
        description = "6 user accounts, shared photos, shared passwords, family calendar."
        prices = @{ t1 = 4599; t2 = 6599; t3 = 9599 }
    },
    @{
        id = "small_business"
        name = "Small Business Sovereign Suite"
        description = "CRM, team chat, office suite, DEFCON ONE + Reactor AI."
        prices = @{ t1 = 9599; t2 = 14999; t3 = 19999 }
    },
    @{
        id = "enterprise"
        name = "Enterprise Sovereign Suite"
        description = "Unlimited users, custom integrations, dedicated support, full AI suite."
        prices = @{ t1 = 19999; t2 = 29999; t3 = 0 }  # t3 = custom
    }
)

# Micro-Bundles (16 bundles)
$MicroBundles = @(
    @{
        id = "meeting_room"
        name = "Meeting Room"
        description = "Video calls, scheduling, collaborative notes - replace Zoom."
        prices = @{ t1 = 1599; t2 = 2599; t3 = 3599 }
    },
    @{
        id = "privacy_pack"
        name = "Privacy Pack"
        description = "Encrypted storage, password manager, private VPN - total privacy."
        prices = @{ t1 = 1599; t2 = 2599; t3 = 3599 }
    },
    @{
        id = "writer_studio"
        name = "Writer's Studio"
        description = "Blog, newsletter, research archive, bookmarks - replace Substack."
        prices = @{ t1 = 1999; t2 = 2999; t3 = 4599 }
    },
    @{
        id = "artist_storefront"
        name = "Artist Storefront"
        description = "Online store, portfolio, photo galleries - replace Etsy."
        prices = @{ t1 = 1999; t2 = 2999; t3 = 4599 }
    },
    @{
        id = "podcaster"
        name = "Podcaster Pack"
        description = "Podcast hosting, show notes blog, listener analytics - own your feed."
        prices = @{ t1 = 2599; t2 = 3599; t3 = 5599 }
    },
    @{
        id = "freelancer"
        name = "Freelancer Essentials"
        description = "Invoicing, scheduling, client contacts - run your business."
        prices = @{ t1 = 2599; t2 = 3599; t3 = 5599 }
    },
    @{
        id = "musician"
        name = "Musician Bundle"
        description = "Music streaming, artist website, merch store - own your music."
        prices = @{ t1 = 2599; t2 = 3599; t3 = 5599 }
    },
    @{
        id = "family_hub"
        name = "Family Hub"
        description = "Shared drive, photos, passwords for 6 family members."
        prices = @{ t1 = 2999; t2 = 4599; t3 = 6599 }
    },
    @{
        id = "photographer"
        name = "Photographer Pro"
        description = "Photo library, client galleries, portfolio, print sales."
        prices = @{ t1 = 2999; t2 = 4599; t3 = 6599 }
    },
    @{
        id = "bookkeeper"
        name = "Bookkeeper Bundle"
        description = "Document scanner, client portal, secure messaging."
        prices = @{ t1 = 2999; t2 = 4599; t3 = 6599 }
    },
    @{
        id = "video_creator"
        name = "Video Creator"
        description = "Video hosting, community blog, paid memberships - replace YouTube."
        prices = @{ t1 = 3599; t2 = 5599; t3 = 9599 }
    },
    @{
        id = "contractor"
        name = "Contractor Pro"
        description = "Digital contracts, project management, time tracking."
        prices = @{ t1 = 3599; t2 = 5599; t3 = 9599 }
    },
    @{
        id = "realtor"
        name = "Real Estate Agent"
        description = "Lead CRM, listing photos, digital contracts."
        prices = @{ t1 = 3599; t2 = 5599; t3 = 9599 }
    },
    @{
        id = "educator"
        name = "Educator Suite"
        description = "Virtual classroom, whiteboard, file sharing for students."
        prices = @{ t1 = 3599; t2 = 5599; t3 = 9599 }
    },
    @{
        id = "therapist"
        name = "Therapist/Coach"
        description = "Secure video sessions, encrypted notes, client portal - HIPAA-ready."
        prices = @{ t1 = 4599; t2 = 6599; t3 = 12599 }
    },
    @{
        id = "legal"
        name = "Legal Lite"
        description = "Document management, e-signatures, secure client portal."
        prices = @{ t1 = 4599; t2 = 6599; t3 = 12599 }
    }
)

# Combine all bundles
$AllBundles = $SovereignSuites + $MicroBundles

# Storage tier descriptions
$TierDescriptions = @{
    t1 = "50GB storage"
    t2 = "200GB storage"
    t3 = "500GB+ storage"
}

# Track created products and prices for export
$CreatedProducts = @{}
$CreatedPrices = @{}

# ============================================
# CREATE PRODUCTS AND PRICES
# ============================================

$totalProducts = $AllBundles.Count * 3
$currentProduct = 0

foreach ($bundle in $AllBundles) {
    Write-Host ""
    Write-Host "Creating: $($bundle.name)" -ForegroundColor Green

    foreach ($tier in @("t1", "t2", "t3")) {
        $currentProduct++
        $priceAmount = $bundle.prices[$tier]

        # Skip custom pricing (enterprise t3)
        if ($priceAmount -eq 0) {
            Write-Host "  [$currentProduct/$totalProducts] $tier - Custom pricing (skipped)" -ForegroundColor Gray
            continue
        }

        $productName = "$($bundle.name) - Tier $($tier.Substring(1)) ($($TierDescriptions[$tier]))"
        $productId = "$($bundle.id)_$tier"
        $priceDisplay = [math]::Round($priceAmount / 100, 2)

        Write-Host "  [$currentProduct/$totalProducts] $tier - `$$priceDisplay/mo" -ForegroundColor White

        # Create product
        try {
            $productResult = & $StripeCLI products create $ModeFlag `
                --name="$productName" `
                --description="$($bundle.description) $($TierDescriptions[$tier])." `
                --metadata[bundle_id]="$($bundle.id)" `
                --metadata[tier]="$tier" `
                --metadata[storage]="$($TierDescriptions[$tier])" `
                2>&1 | ConvertFrom-Json

            $stripeProductId = $productResult.id
            $CreatedProducts[$productId] = $stripeProductId

            # Create monthly price
            $monthlyPriceResult = & $StripeCLI prices create $ModeFlag `
                --product="$stripeProductId" `
                --unit-amount=$priceAmount `
                --currency=usd `
                --recurring[interval]=month `
                --metadata[bundle_id]="$($bundle.id)" `
                --metadata[tier]="$tier" `
                --metadata[billing_period]="monthly" `
                2>&1 | ConvertFrom-Json

            $CreatedPrices["${productId}_monthly"] = $monthlyPriceResult.id

            # Create yearly price (2 months free = 10 months price)
            $yearlyAmount = [math]::Floor($priceAmount * 10)
            $yearlyPriceResult = & $StripeCLI prices create $ModeFlag `
                --product="$stripeProductId" `
                --unit-amount=$yearlyAmount `
                --currency=usd `
                --recurring[interval]=year `
                --metadata[bundle_id]="$($bundle.id)" `
                --metadata[tier]="$tier" `
                --metadata[billing_period]="yearly" `
                2>&1 | ConvertFrom-Json

            $CreatedPrices["${productId}_yearly"] = $yearlyPriceResult.id

        } catch {
            Write-Host "    ERROR: $_" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Created:" -ForegroundColor Cyan
Write-Host "  - $($CreatedProducts.Count) products"
Write-Host "  - $($CreatedPrices.Count) prices (monthly + yearly)"
Write-Host ""

# ============================================
# EXPORT CATALOG TO PYTHON
# ============================================

if ($ExportCatalog -or $true) {
    $catalogPath = "C:\Users\sbink\WOPR\wopr-installer\control_plane\stripe_catalog.py"

    Write-Host "Exporting catalog to: $catalogPath" -ForegroundColor Cyan

    $pythonContent = @"
# WOPR Stripe Product Catalog
# Auto-generated by stripe-setup.ps1
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Mode: $(if ($Live) { "LIVE" } else { "TEST" })

from typing import Dict, Any

# Stripe Product IDs
STRIPE_PRODUCTS: Dict[str, str] = {

"@

    foreach ($key in $CreatedProducts.Keys | Sort-Object) {
        $pythonContent += "    `"$key`": `"$($CreatedProducts[$key])`",`n"
    }

    $pythonContent += @"
}

# Stripe Price IDs (monthly and yearly)
STRIPE_PRICES: Dict[str, str] = {

"@

    foreach ($key in $CreatedPrices.Keys | Sort-Object) {
        $pythonContent += "    `"$key`": `"$($CreatedPrices[$key])`",`n"
    }

    $pythonContent += @"
}

# Bundle pricing in cents (for validation)
BUNDLE_PRICING: Dict[str, Dict[str, int]] = {

"@

    foreach ($bundle in $AllBundles) {
        $pythonContent += "    `"$($bundle.id)`": {`n"
        $pythonContent += "        `"t1`": $($bundle.prices.t1),`n"
        $pythonContent += "        `"t2`": $($bundle.prices.t2),`n"
        $pythonContent += "        `"t3`": $($bundle.prices.t3),`n"
        $pythonContent += "    },`n"
    }

    $pythonContent += @"
}

# Helper functions
def get_price_id(bundle_id: str, tier: str, period: str = "monthly") -> str:
    """Get Stripe price ID for a bundle/tier/period combination."""
    key = f"{bundle_id}_{tier}_{period}"
    return STRIPE_PRICES.get(key)

def get_product_id(bundle_id: str, tier: str) -> str:
    """Get Stripe product ID for a bundle/tier combination."""
    key = f"{bundle_id}_{tier}"
    return STRIPE_PRODUCTS.get(key)

def get_price_cents(bundle_id: str, tier: str) -> int:
    """Get price in cents for a bundle/tier."""
    bundle = BUNDLE_PRICING.get(bundle_id, {})
    return bundle.get(tier, 0)

def get_all_bundles() -> list:
    """Get list of all bundle IDs."""
    return list(BUNDLE_PRICING.keys())

def get_sovereign_suites() -> list:
    """Get list of Sovereign Suite bundle IDs."""
    return ["starter", "creator", "developer", "professional", "family", "small_business", "enterprise"]

def get_micro_bundles() -> list:
    """Get list of Micro-Bundle IDs."""
    sovereign = set(get_sovereign_suites())
    return [b for b in get_all_bundles() if b not in sovereign]
"@

    $pythonContent | Out-File -FilePath $catalogPath -Encoding utf8

    Write-Host "Catalog exported!" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Verify products in Stripe Dashboard"
Write-Host "2. stripe_catalog.py has been generated with all price IDs"
Write-Host "3. Update billing.py to use the new catalog"
Write-Host "4. Configure webhooks at: https://dashboard.stripe.com/webhooks"
Write-Host ""
