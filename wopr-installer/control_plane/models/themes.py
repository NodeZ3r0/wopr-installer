"""
WOPR Beacon Theme Models
========================

Pydantic models for theme configuration and API requests/responses.

Updated: January 2026
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# ============================================
# THEME PRESETS (mirrored from frontend)
# ============================================

THEME_PRESETS = {
    "reactor": {
        "id": "reactor",
        "name": "Reactor",
        "description": "Default WOPR theme with teal and orange accents",
        "preview": {"primary": "#00d4aa", "accent": "#ff9b3f", "bg": "#0a0a0a"},
    },
    "midnight": {
        "id": "midnight",
        "name": "Midnight",
        "description": "Deep violet and purple tones",
        "preview": {"primary": "#818cf8", "accent": "#c084fc", "bg": "#0c0a1a"},
    },
    "solaris": {
        "id": "solaris",
        "name": "Solaris",
        "description": "Warm amber and orange sunset tones",
        "preview": {"primary": "#fbbf24", "accent": "#f97316", "bg": "#0f0a05"},
    },
    "arctic": {
        "id": "arctic",
        "name": "Arctic",
        "description": "Cool sky blue and cyan tones",
        "preview": {"primary": "#38bdf8", "accent": "#22d3ee", "bg": "#050a0f"},
    },
    "terminal": {
        "id": "terminal",
        "name": "Terminal",
        "description": "Classic hacker green on black",
        "preview": {"primary": "#4ade80", "accent": "#22c55e", "bg": "#000000"},
    },
    "ember": {
        "id": "ember",
        "name": "Ember",
        "description": "Warm rose and red tones",
        "preview": {"primary": "#fb7185", "accent": "#f43f5e", "bg": "#0f0508"},
    },
}

# WOPR-native apps that are always themed
NATIVE_THEMED_APPS = ["defcon", "brainjoos", "rag"]

DEFAULT_PRESET = "reactor"


# ============================================
# PYDANTIC MODELS
# ============================================

class ThemeColors(BaseModel):
    """Custom color overrides for a theme."""

    primary: Optional[str] = Field(
        None,
        description="Primary brand color (hex)",
        pattern=r"^#[0-9a-fA-F]{6}$",
        examples=["#00d4aa"],
    )
    primary_hover: Optional[str] = Field(
        None,
        alias="--theme-primary-hover",
        description="Primary hover color",
    )
    accent: Optional[str] = Field(
        None,
        description="Secondary accent color (hex)",
        pattern=r"^#[0-9a-fA-F]{6}$",
        examples=["#ff9b3f"],
    )
    accent_hover: Optional[str] = Field(
        None,
        alias="--theme-accent-hover",
        description="Accent hover color",
    )
    background: Optional[str] = Field(
        None,
        alias="bg",
        description="Background color (hex)",
        pattern=r"^#[0-9a-fA-F]{6}$",
    )
    surface: Optional[str] = Field(
        None,
        description="Surface/card background color (hex)",
    )
    text: Optional[str] = Field(
        None,
        description="Primary text color (hex)",
    )
    text_muted: Optional[str] = Field(
        None,
        description="Muted/secondary text color (hex)",
    )

    class Config:
        populate_by_name = True


class AppThemeOverride(BaseModel):
    """Theme override for a specific app."""

    preset: Optional[str] = Field(
        None,
        description="Preset ID to use for this app",
        examples=["midnight", "solaris"],
    )
    custom_colors: Optional[ThemeColors] = Field(
        None,
        description="Custom color overrides for this app",
    )


class ThemeConfig(BaseModel):
    """Full theme configuration for a user."""

    preset: str = Field(
        DEFAULT_PRESET,
        description="Global theme preset ID",
        examples=["reactor", "midnight"],
    )
    custom_colors: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom CSS variable overrides",
        examples=[{"--theme-primary": "#ff0000"}],
    )
    app_overrides: Dict[str, AppThemeOverride] = Field(
        default_factory=dict,
        description="Per-app theme overrides keyed by app_id",
    )
    themed_apps: List[str] = Field(
        default_factory=lambda: NATIVE_THEMED_APPS.copy(),
        description="List of app IDs that receive theme CSS injection",
    )


class ThemeUpdateRequest(BaseModel):
    """Request to update theme settings."""

    preset: Optional[str] = Field(
        None,
        description="New preset ID to apply",
        examples=["midnight"],
    )
    custom_colors: Optional[Dict[str, str]] = Field(
        None,
        description="Custom CSS variable overrides to set",
    )
    themed_apps: Optional[List[str]] = Field(
        None,
        description="Updated list of themed apps",
    )


class AppThemeUpdateRequest(BaseModel):
    """Request to update a specific app's theme."""

    preset: Optional[str] = Field(
        None,
        description="Preset ID to use for this app, or null to inherit global",
    )
    custom_colors: Optional[Dict[str, str]] = Field(
        None,
        description="Custom color overrides for this app",
    )
    enabled: Optional[bool] = Field(
        None,
        description="Whether theme injection is enabled for this app",
    )


class ThemePresetResponse(BaseModel):
    """Response model for a theme preset."""

    id: str
    name: str
    description: str
    preview: Dict[str, str] = Field(
        description="Preview colors: primary, accent, bg"
    )


class ThemeConfigResponse(BaseModel):
    """Response model for user's theme configuration."""

    preset: str
    preset_name: str
    custom_colors: Dict[str, str]
    app_overrides: Dict[str, Any]
    themed_apps: List[str]
    available_presets: List[ThemePresetResponse]


class ThemeCSSResponse(BaseModel):
    """Response model for CSS export."""

    css: str = Field(description="Raw CSS with :root variables")
    preset: str
    custom_colors: Dict[str, str]


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_preset_info(preset_id: str) -> Optional[Dict[str, Any]]:
    """Get preset metadata by ID."""
    return THEME_PRESETS.get(preset_id)


def get_all_presets() -> List[ThemePresetResponse]:
    """Get list of all available presets."""
    return [
        ThemePresetResponse(**preset)
        for preset in THEME_PRESETS.values()
    ]


def validate_preset(preset_id: str) -> bool:
    """Check if a preset ID is valid."""
    return preset_id in THEME_PRESETS


def is_native_app(app_id: str) -> bool:
    """Check if an app is WOPR-native (always themed)."""
    return app_id in NATIVE_THEMED_APPS
