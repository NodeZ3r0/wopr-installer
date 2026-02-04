import json
import httpx
from api.config import OLLAMA_URL, OLLAMA_MODEL, COMMAND_BLOCKLIST, TIER1_ALLOWED_ACTIONS, MIN_CONFIDENCE_FOR_AUTO
from api.models import AIDecision, SafetyTier
from api.prompts import SYSTEM_PROMPT, ANALYSIS_PROMPT_TEMPLATE
from api.log_analyzer import match_known_pattern


def _validate_safety(decision: dict) -> dict:
    """Hard safety validator — override LLM decisions if they violate rules."""
    action = decision.get("action", "")

    # Check blocklist
    for blocked in COMMAND_BLOCKLIST:
        if blocked.lower() in action.lower():
            decision["tier"] = SafetyTier.ESCALATE.value
            decision["confidence"] = 0.0
            decision["reasoning"] += " [BLOCKED: contains prohibited command]"
            return decision

    # Tier 1 must be in allowlist
    if decision.get("tier") == SafetyTier.AUTO_FIX.value:
        base_action = action.split(":")[0].split(" ")[0] if action else ""
        if base_action not in TIER1_ALLOWED_ACTIONS:
            decision["tier"] = SafetyTier.SUGGEST.value
            decision["reasoning"] += f" [UPGRADED: '{base_action}' not in tier1 allowlist]"

    # Confidence check for auto-fix
    if decision.get("tier") == SafetyTier.AUTO_FIX.value:
        if decision.get("confidence", 0) < MIN_CONFIDENCE_FOR_AUTO:
            decision["tier"] = SafetyTier.SUGGEST.value
            decision["reasoning"] += f" [UPGRADED: confidence {decision['confidence']:.2f} below threshold {MIN_CONFIDENCE_FOR_AUTO}]"

    return decision


async def analyze_with_llm(service: str, errors: list[dict]) -> AIDecision | None:
    """Send errors to Ollama for analysis."""
    error_text = "\n".join(
        f"[{e.get('timestamp', 'N/A')}] {e.get('severity', 'error')}: "
        f"{e.get('action', e.get('message', 'unknown'))}"
        for e in errors[:10]  # limit context
    )

    # Try known patterns first
    for e in errors:
        text = e.get("action", "") + " " + e.get("message", "")
        match = match_known_pattern(text)
        if match:
            match["service"] = service
            validated = _validate_safety(match)
            return AIDecision(**validated)

    # Fall back to LLM
    prompt = ANALYSIS_PROMPT_TEMPLATE.format(service=service, errors=error_text)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "system": SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = json.loads(data.get("response", "{}"))

            # Ensure required fields
            raw.setdefault("service", service)
            raw.setdefault("tier", SafetyTier.ESCALATE.value)
            raw.setdefault("action", "investigate")
            raw.setdefault("confidence", 0.5)
            raw.setdefault("reasoning", "LLM analysis")
            raw.setdefault("error_pattern", "unknown")

            validated = _validate_safety(raw)
            return AIDecision(**validated)

    except Exception:
        return None
