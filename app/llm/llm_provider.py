"""
LLM provider — Cerebras only.

Two modes:
  1. explain_known   — DB has severity; LLM simplifies it for the user
  2. assess_unknown  — DB has no answer; LLM reasons from pharmacology context

Both return { "risk_estimate": str, "reasoning": str }
"""
import logging
from app.config import CEREBRAS_API_KEY, CEREBRAS_MODEL, LLM_TIMEOUT

log = logging.getLogger(__name__)

try:
    from cerebras.cloud.sdk import Cerebras
    _client = Cerebras(api_key=CEREBRAS_API_KEY) if CEREBRAS_API_KEY else None
except ImportError:
    _client = None
    log.warning("cerebras SDK not installed — LLM disabled")


_SYSTEM_PROMPT = (
    "You are a clinical pharmacology assistant helping patients and caregivers "
    "understand drug information in plain English. "
    "Always ground your explanation in the provided medical context. "
    "Never invent drug names, mechanisms, or interactions. "
    "If context is insufficient, say so explicitly and recommend consulting a doctor."
)

# ── Prompt for KNOWN severity (DB has the answer) ──────────────────────────────
_EXPLAIN_KNOWN_TEMPLATE = """\
A patient is asking about taking these two drugs together:
Drug A: {drug1}
Drug B: {drug2}

Our medical database has found the following:
Severity: {severity}
Database description: {description}

Additional pharmacology context:
{context}

Please explain this interaction in simple, clear language that a non-medical person can understand.
Cover:
1. What this severity level means for them practically
2. Why this interaction happens (in plain English)
3. What they should do about it

Respond in this exact JSON format:
{{
  "risk_estimate": "{severity}",
  "reasoning": "your plain-English explanation here"
}}"""

# ── Prompt for UNKNOWN severity (agent fallback) ────────────────────────────────
_ASSESS_UNKNOWN_TEMPLATE = """\
A patient is asking about taking these two drugs together:
Drug A: {drug1}
Drug B: {drug2}

Our database does not have a labeled severity for this combination.
Use the following pharmacology context to assess the risk:

{context}

Based ONLY on the context above:
1. Estimate the interaction risk: HIGH / MODERATE / LOW / INSUFFICIENT_DATA
2. Explain the pharmacological mechanism in plain English (1-2 sentences)
3. Give a clear clinical recommendation (1 sentence)
4. Explicitly state this is an AI estimate, not a confirmed database result

Respond in this exact JSON format:
{{
  "risk_estimate": "HIGH|MODERATE|LOW|INSUFFICIENT_DATA",
  "reasoning": "your explanation + recommendation + disclaimer"
}}"""


def explain_known_interaction(
    drug1: str,
    drug2: str,
    severity: str,
    description: str,
    context: str,
) -> dict:
    """Called when DB has a known severity. LLM simplifies it for the user."""
    prompt = _EXPLAIN_KNOWN_TEMPLATE.format(
        drug1=drug1,
        drug2=drug2,
        severity=severity,
        description=description or "No additional description in database.",
        context=context or "No additional pharmacology context available.",
    )
    return _call_llm(prompt, severity_hint=severity)


def assess_unknown_interaction(
    drug1: str,
    drug2: str,
    context: str,
) -> dict:
    """Called when DB severity is UNKNOWN. LLM reasons from full context."""
    prompt = _ASSESS_UNKNOWN_TEMPLATE.format(
        drug1=drug1,
        drug2=drug2,
        context=context or "No pharmacology context available in database.",
    )
    return _call_llm(prompt, severity_hint=None)


# ── Shared LLM call ────────────────────────────────────────────────────────────

def _call_llm(prompt: str, severity_hint: str | None) -> dict:
    if not _client:
        return _no_llm_fallback()

    try:
        response = _client.chat.completions.create(
            model=CEREBRAS_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=400,
            temperature=0.15,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_llm_json(raw, severity_hint)

    except Exception as e:
        log.error(f"Cerebras error: {e}")
        return _error_fallback()


# ── Parsers & fallbacks ────────────────────────────────────────────────────────

def _parse_llm_json(raw: str, severity_hint: str | None) -> dict:
    import json, re
    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
    try:
        data = json.loads(raw)
        return {
            "risk_estimate": str(data.get("risk_estimate", severity_hint or "INSUFFICIENT_DATA")),
            "reasoning":     str(data.get("reasoning", "No reasoning provided.")),
        }
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"(HIGH|MODERATE|LOW|INSUFFICIENT_DATA)", raw, re.I)
        risk = match.group(1).upper() if match else (severity_hint or "INSUFFICIENT_DATA")
        return {"risk_estimate": risk, "reasoning": raw[:600]}


def _no_llm_fallback() -> dict:
    return {
        "risk_estimate": "UNAVAILABLE",
        "reasoning": "LLM provider not configured. Set CEREBRAS_API_KEY in your .env file.",
    }


def _error_fallback() -> dict:
    return {
        "risk_estimate": "UNAVAILABLE",
        "reasoning": "LLM explanation unavailable. Please consult a pharmacist or physician.",
    }


# ── Drug info simplification ───────────────────────────────────────────────────

_SIMPLIFY_DRUG_TEMPLATE = """\
A patient wants to understand information about this drug:
Drug: {drug_name}

Here is the raw medical database information:
Indication (what it's used for): {indication}
Mechanism of action: {mechanism}
Side effects / toxicity: {side_effects}

Please rewrite this in simple, friendly language that a non-medical person can easily understand.
Avoid medical jargon. Be reassuring but honest about risks.
Keep each section brief — 2-3 sentences max.

Respond in this exact JSON format:
{{
  "what_its_for": "simple explanation of what the drug treats",
  "how_it_works": "simple explanation of the mechanism",
  "side_effects": "plain-English side effects a patient should know about",
  "safety_tip": "one practical safety tip for taking this drug"
}}"""


def simplify_drug_info(
    drug_name: str,
    indication: str,
    mechanism: str,
    side_effects: str,
) -> dict | None:
    """
    Rewrites raw DrugBank clinical text into plain English for patients.
    Returns dict with keys: what_its_for, how_it_works, side_effects, safety_tip
    Returns None if LLM unavailable.
    """
    if not _client:
        return None

    prompt = _SIMPLIFY_DRUG_TEMPLATE.format(
        drug_name=drug_name,
        indication=indication[:600] if indication else "Not available.",
        mechanism=mechanism[:600] if mechanism else "Not available.",
        side_effects=side_effects[:600] if side_effects else "Not available.",
    )

    try:
        response = _client.chat.completions.create(
            model=CEREBRAS_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=400,
            temperature=0.15,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_drug_info_json(raw)

    except Exception as e:
        log.error(f"Cerebras drug info error: {e}")
        return None


def _parse_drug_info_json(raw: str) -> dict | None:
    import json, re
    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
    try:
        data = json.loads(raw)
        return {
            "what_its_for": str(data.get("what_its_for", "")),
            "how_it_works":  str(data.get("how_it_works", "")),
            "side_effects":  str(data.get("side_effects", "")),
            "safety_tip":    str(data.get("safety_tip", "")),
        }
    except (json.JSONDecodeError, ValueError):
        return None
