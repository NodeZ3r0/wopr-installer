# WOPR Systems - Stripe Product Setup Script
# ==========================================
#
# This script creates all Stripe products and prices for WOPR Sovereign Suite bundles.
# Run this ONCE to set up your Stripe catalog.
#
# Prerequisites:
# 1. Stripe CLI installed (winget install Stripe.StripeCli)
# 2. Stripe CLI logged in (stripe login)
#
# Usage:
#   .\stripe-setup.ps1
#
# To use LIVE mode (real money):
#   .\stripe-setup.ps1 -Live

param(
    [switch]$Live
)

$StripeCLI = "C:\Users\sbink\AppData\Local\Microsoft\WinGet\Packages\Stripe.StripeCli_Microsoft.Winget.Source_8wekyb3d8bbwe\stripe.exe"

# Check if stripe CLI exists
if (-not (Test-Path $StripeCLI)) {
    Write-Host "Stripe CLI not found at expected path. Trying 'stripe' command..." -ForegroundColor Yellow
    $StripeCLI = "stripe"
}

$ModeFlag = ""
if ($Live) {
    Write-Host "=== LIVE MODE - Real money will be charged ===" -ForegroundColor Red
    $ModeFlag = "--live"
} else {
    Write-Host "=== TEST MODE - No real charges ===" -ForegroundColor Yellow
    Write-Host "Run with -Live flag for production setup" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "WOPR Systems - Stripe Product Setup" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# STEP 1: Create Products
# ============================================

Write-Host "Creating Products..." -ForegroundColor Green

# Personal Sovereign Suite
Write-Host "  Creating: Personal Sovereign Suite"
$personalProduct = & $StripeCLI products create $ModeFlag `
    --name="Personal Sovereign Suite" `
    --description="Your personal cloud. Includes Nextcloud, Vaultwarden, FreshRSS, and automated backups." `
    --metadata[bundle_id]="personal" `
    --metadata[tier]="1" `
    2>&1

# Creator Sovereign Suite
Write-Host "  Creating: Creator Sovereign Suite"
$creatorProduct = & $StripeCLI products create $ModeFlag `
    --name="Creator Sovereign Suite" `
    --description="Personal cloud + monetization. Includes Ghost blog, Saleor commerce, and portfolio tools." `
    --metadata[bundle_id]="creator" `
    --metadata[tier]="2" `
    2>&1

# Developer Sovereign Suite
Write-Host "  Creating: Developer Sovereign Suite"
$developerProduct = & $StripeCLI products create $ModeFlag `
    --name="Developer Sovereign Suite" `
    --description="Personal cloud + dev tools. Includes Forgejo Git, Woodpecker CI, VS Code Server, and Reactor AI." `
    --metadata[bundle_id]="developer" `
    --metadata[tier]="2" `
    2>&1

# Professional Sovereign Suite
Write-Host "  Creating: Professional Sovereign Suite"
$professionalProduct = & $StripeCLI products create $ModeFlag `
    --name="Professional Sovereign Suite" `
    --description="Complete sovereign workspace. Includes everything: cloud, commerce, dev tools, collaboration, and AI." `
    --metadata[bundle_id]="professional" `
    --metadata[tier]="3" `
    2>&1

Write-Host ""
Write-Host "Products created!" -ForegroundColor Green
Write-Host ""

# ============================================
# STEP 2: Get Product IDs
# ============================================

Write-Host "Fetching product IDs..." -ForegroundColor Green

$products = & $StripeCLI products list $ModeFlag --limit=10 2>&1 | ConvertFrom-Json

$productIds = @{}
foreach ($product in $products.data) {
    if ($product.metadata.bundle_id) {
        $productIds[$product.metadata.bundle_id] = $product.id
        Write-Host "  $($product.metadata.bundle_id): $($product.id)"
    }
}

Write-Host ""

# ============================================
# STEP 3: Create Prices
# ============================================

Write-Host "Creating Prices..." -ForegroundColor Green

# Personal - $9.99/month, $99/year
if ($productIds["personal"]) {
    Write-Host "  Personal Monthly: `$9.99/mo"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["personal"]) `
        --unit-amount=999 `
        --currency=usd `
        --recurring[interval]=month `
        --metadata[bundle_id]="personal" `
        --metadata[billing_period]="monthly" `
        2>&1 | Out-Null

    Write-Host "  Personal Yearly: `$99/yr (save `$20)"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["personal"]) `
        --unit-amount=9900 `
        --currency=usd `
        --recurring[interval]=year `
        --metadata[bundle_id]="personal" `
        --metadata[billing_period]="yearly" `
        2>&1 | Out-Null
}

# Creator - $19.99/month, $199/year
if ($productIds["creator"]) {
    Write-Host "  Creator Monthly: `$19.99/mo"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["creator"]) `
        --unit-amount=1999 `
        --currency=usd `
        --recurring[interval]=month `
        --metadata[bundle_id]="creator" `
        --metadata[billing_period]="monthly" `
        2>&1 | Out-Null

    Write-Host "  Creator Yearly: `$199/yr (save `$40)"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["creator"]) `
        --unit-amount=19900 `
        --currency=usd `
        --recurring[interval]=year `
        --metadata[bundle_id]="creator" `
        --metadata[billing_period]="yearly" `
        2>&1 | Out-Null
}

# Developer - $29.99/month, $299/year
if ($productIds["developer"]) {
    Write-Host "  Developer Monthly: `$29.99/mo"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["developer"]) `
        --unit-amount=2999 `
        --currency=usd `
        --recurring[interval]=month `
        --metadata[bundle_id]="developer" `
        --metadata[billing_period]="monthly" `
        2>&1 | Out-Null

    Write-Host "  Developer Yearly: `$299/yr (save `$60)"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["developer"]) `
        --unit-amount=29900 `
        --currency=usd `
        --recurring[interval]=year `
        --metadata[bundle_id]="developer" `
        --metadata[billing_period]="yearly" `
        2>&1 | Out-Null
}

# Professional - $49.99/month, $499/year
if ($productIds["professional"]) {
    Write-Host "  Professional Monthly: `$49.99/mo"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["professional"]) `
        --unit-amount=4999 `
        --currency=usd `
        --recurring[interval]=month `
        --metadata[bundle_id]="professional" `
        --metadata[billing_period]="monthly" `
        2>&1 | Out-Null

    Write-Host "  Professional Yearly: `$499/yr (save `$100)"
    & $StripeCLI prices create $ModeFlag `
        --product=$($productIds["professional"]) `
        --unit-amount=49900 `
        --currency=usd `
        --recurring[interval]=year `
        --metadata[bundle_id]="professional" `
        --metadata[billing_period]="yearly" `
        2>&1 | Out-Null
}

Write-Host ""
Write-Host "Prices created!" -ForegroundColor Green
Write-Host ""

# ============================================
# STEP 4: Create Payment Links
# ============================================

Write-Host "Creating Payment Links..." -ForegroundColor Green

$prices = & $StripeCLI prices list $ModeFlag --limit=20 2>&1 | ConvertFrom-Json

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PAYMENT LINKS (for wopr.systems/join)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

foreach ($price in $prices.data) {
    if ($price.metadata.bundle_id) {
        $link = & $StripeCLI payment_links create $ModeFlag `
            --line-items[0][price]=$($price.id) `
            --line-items[0][quantity]=1 `
            2>&1 | ConvertFrom-Json

        $bundle = $price.metadata.bundle_id
        $period = $price.metadata.billing_period
        $amount = [math]::Round($price.unit_amount / 100, 2)

        Write-Host "$bundle ($period) - `$$amount" -ForegroundColor Yellow
        Write-Host "  URL: $($link.url)" -ForegroundColor White
        Write-Host "  Price ID: $($price.id)" -ForegroundColor Gray
        Write-Host ""
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Copy the payment links above to your join page"
Write-Host "2. Or use the Price IDs with Stripe Checkout in your code"
Write-Host "3. Configure webhooks at: https://dashboard.stripe.com/webhooks"
Write-Host ""
