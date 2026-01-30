from __future__ import annotations

from typing import List, Set, Tuple
import json
import logging

logger = logging.getLogger(__name__)


def normalize(text: str | None) -> Set[str]:
    if not text:
        return set()
    return {word.lower() for word in str(text).split() if len(word) > 2}


def overlap_score(a: Set[str], b: Set[str]) -> float:
    """
    Lightweight overlap-based similarity.

    Returns a value in [0.0, 1.0].
    If either side is empty, returns a neutral score of 0.5.
    """
    if not a or not b:
        return 0.5
    return min(len(a & b) / len(a), 1.0)


def passes_eligibility(project, grant) -> bool:
    """
    Hard eligibility gate.

    Returns False if:
    - The grant is not open
    - The project start date is after the grant closing date
    - The applicant type is clearly ineligible
    - The minimum project budget exceeds the grant’s maximum funding by more than 20%
    """
    # Grant must be open (or missing status treated as open-ish)
    status = getattr(grant, "status", None)
    if status and str(status).lower() != "open":
        return False

    # Project start must not be after closing date
    closing_date = getattr(grant, "closing_date", None)
    start_date = getattr(project, "project_start_date", None)
    if closing_date and start_date and start_date > closing_date:
        return False

    # Applicant type clearly ineligible (very conservative, only when explicit)
    user = getattr(project, "user", None)
    profile = getattr(user, "profile", None) if user else None
    org_type = getattr(profile, "organization_type", None)
    eligibility_text = " ".join(
        str(x)
        for x in [
            getattr(grant, "eligibility_criteria", "") or "",
            getattr(grant, "description", "") or "",
        ]
    ).lower()

    # Map internal codes to simple keywords to look for in eligibility text
    ORG_TYPE_KEYWORDS = {
        "npo": ["non-profit", "non profit", "charity"],
        "social_enterprise": ["social enterprise"],
        "government": ["government agency", "public agency", "statutory board"],
        "academic": ["school", "university", "polytechnic", "ite", "academic"],
        "corporate": ["company", "business", "corporate"],
        "individual": ["individual", "person"],
    }

    NEGATIVE_PATTERNS = [
        "not eligible for",
        "not for",
        "excluding",
        "exclude",
        "no funding for",
        "ineligible for",
    ]

    if org_type and eligibility_text:
        keywords = ORG_TYPE_KEYWORDS.get(str(org_type), [])
        for kw in keywords:
            if any(pattern in eligibility_text and kw in eligibility_text for pattern in NEGATIVE_PATTERNS):
                return False

    # Budget: minimum project budget must not exceed grant max by > 20%
    budget_min = getattr(project, "budget_required_min", None)
    funding_max = getattr(grant, "funding_max", None)
    if budget_min and funding_max:
        try:
            budget_min_value = float(budget_min)
            funding_max_value = float(funding_max)
            if funding_max_value > 0 and budget_min_value > 1.2 * funding_max_value:
                return False
        except (TypeError, ValueError):
            # If conversion fails, do not block eligibility purely on this
            pass

    return True


def score_focus_and_objectives(project, grant) -> float:
    """Focus area & objectives alignment (0.0 – 1.0)."""
    project_tokens = normalize(
        f"{getattr(project, 'focus_area', '')} "
        f"{getattr(project, 'description', '')} "
        f"{getattr(project, 'need_support_for', '')}"
    )
    grant_tokens = normalize(f"{getattr(grant, 'title', '')} {getattr(grant, 'description', '')}")
    return overlap_score(project_tokens, grant_tokens)


def score_beneficiary_alignment(project, grant) -> float:
    """Beneficiary alignment (0.0 – 1.0, neutral ≈ 0.5 on missing data)."""
    beneficiary_types = getattr(project, "beneficiary_types", []) or []
    if isinstance(beneficiary_types, str):
        beneficiary_set = normalize(beneficiary_types)
    else:
        beneficiary_set = {str(x).lower() for x in beneficiary_types if str(x).strip()}

    grant_beneficiaries_tokens = normalize(getattr(grant, "description", ""))
    return overlap_score(beneficiary_set, grant_beneficiaries_tokens)


def score_budget_compatibility(project, grant) -> float:
    """
    Budget compatibility (0.0 – 1.0).

    - 1.0 if comfortably within funding range
    - 0.7 if slightly above but plausibly adjustable (≤ 20% above max)
    - 0.0 if incompatible
    - 0.5 if data is insufficient
    """
    budget_min = getattr(project, "budget_required_min", None)
    funding_min = getattr(grant, "funding_min", None)
    funding_max = getattr(grant, "funding_max", None)

    if not budget_min or not funding_max:
        # Not enough info – neutral
        return 0.5

    try:
        budget_min_value = float(budget_min)
        funding_min_value = float(funding_min) if funding_min is not None else None
        funding_max_value = float(funding_max)
    except (TypeError, ValueError):
        return 0.5

    if funding_max_value <= 0 or budget_min_value <= 0:
        return 0.5

    # Comfortably within range (within min/max when both present, or below max)
    if funding_min_value is not None:
        if funding_min_value <= budget_min_value <= funding_max_value:
            return 1.0
    else:
        if budget_min_value <= funding_max_value:
            return 1.0

    # Slightly above but within 20% over max
    if budget_min_value <= 1.2 * funding_max_value:
        return 0.7

    # Incompatible
    return 0.0


def _parse_duration_years(raw: str | None) -> float | None:
    """Very lightweight parser for duration strings like '2-3 years' or '1 year'."""
    if not raw:
        return None
    text = str(raw).lower()
    # Extract first number we see
    num = ""
    for ch in text:
        if ch.isdigit() or (ch == "." and "." not in num):
            num += ch
        elif num:
            break
    if not num:
        return None
    try:
        return float(num)
    except ValueError:
        return None


def score_timeline_compatibility(project, grant) -> float:
    """
    Timeline compatibility (0.0 – 1.0).

    Uses project and grant duration (years) when available:
    - 1.0 for close match
    - 0.7 for reasonable mismatch
    - 0.0 for clear mismatch
    Falls back to 0.5 when data is insufficient.
    """
    project_duration = _parse_duration_years(getattr(project, "duration_years", None))
    grant_duration = _parse_duration_years(getattr(grant, "duration_years", None))

    if project_duration is None or grant_duration is None:
        return 0.5

    diff = abs(project_duration - grant_duration)
    if diff <= 0.5:
        return 1.0
    if diff <= 1.0:
        return 0.7
    return 0.0


def score_agency_preference(project, grant) -> float:
    """Agency preference (0.0 or 1.0)."""
    agency = getattr(grant, "agency", None)
    agency_acronym = getattr(agency, "acronym", None) if agency else None
    want_support_from = getattr(project, "want_support_from", []) or []
    return 1.0 if (agency_acronym and agency_acronym in want_support_from) else 0.0


def score_project_completeness(project, grant) -> float:  # noqa: ARG001 - grant kept for future use
    """
    Project completeness (0.0 – 1.0).

    Based on presence of key fields:
    - description
    - budget (min or max)
    - duration
    - beneficiaries
    """
    total_fields = 4
    filled = 0

    if getattr(project, "description", None):
        filled += 1

    if getattr(project, "budget_required_min", None) or getattr(project, "budget_required_max", None):
        filled += 1

    if getattr(project, "duration_years", None) or (
        getattr(project, "project_start_date", None) and getattr(project, "project_end_date", None)
    ):
        filled += 1

    beneficiaries = getattr(project, "beneficiary_types", []) or []
    if beneficiaries:
        filled += 1

    return min(max(filled / total_fields, 0.0), 1.0)


def get_gemini_semantic_score(project, grant) -> float:
    """
    Use Gemini API to evaluate semantic/contextual fit (40% of final score).
    Returns score in [0.0, 1.0].
    Falls back gracefully to 0.5 (neutral) on error or if API key not configured.
    """
    try:
        from django.conf import settings
        import google.genai as genai  # Use new genai package

        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            logger.debug("GEMINI_API_KEY not configured, using neutral semantic score")
            return 0.5

        client = genai.Client(api_key=api_key)

        # Prepare concise project and grant summaries
        project_summary = f"""
Project Title: {getattr(project, 'title', 'N/A')}
Focus Area: {getattr(project, 'focus_area', 'N/A')}
Description: {getattr(project, 'description', '')[:300]}
Beneficiaries: {', '.join(str(b) for b in (getattr(project, 'beneficiary_types', []) or [])) or 'N/A'}
Budget: ${getattr(project, 'budget_required_min', 0)} - ${getattr(project, 'budget_required_max', 0)}
Duration: {getattr(project, 'duration_years', 'N/A')}
"""

        grant_summary = f"""
Grant Title: {getattr(grant, 'title', 'N/A')}
Agency: {getattr(grant, 'agency', None).acronym if getattr(grant, 'agency', None) else 'Unknown'}
Description: {getattr(grant, 'description', '')[:300]}
Funding: ${getattr(grant, 'funding_min', 'Unknown')} - ${getattr(grant, 'funding_max', 'Unknown')}
Duration: {getattr(grant, 'duration_years', 'N/A')}
"""

        prompt = f"""Evaluate the semantic/contextual fit between this project and grant on a scale of 0-100.
Consider:
1. Do underlying goals and values align conceptually?
2. Is the project maturity/readiness appropriate for this grant?
3. Are there hidden synergies or obvious mismatches in intent?

IMPORTANT: Respond ONLY with a JSON object like this:
{{"semantic_score": 75}}

PROJECT:
{project_summary}

GRANT:
{grant_summary}

Your response must be ONLY the JSON, nothing else."""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        response_text = response.text.strip()

        # Parse JSON response
        result = json.loads(response_text)
        semantic_score = float(result.get("semantic_score", 50)) / 100.0
        semantic_score = min(max(semantic_score, 0.0), 1.0)  # Clamp to 0-1
        logger.debug(f"Gemini semantic score: {semantic_score:.2f} for {project.title} x {grant.title}")
        return semantic_score

    except ImportError:
        logger.warning("google.genai not installed, trying google.generativeai fallback")
        try:
            import google.generativeai as genai
            from django.conf import settings
            
            api_key = getattr(settings, "GEMINI_API_KEY", "")
            if not api_key:
                return 0.5
                
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            project_summary = f"Project: {getattr(project, 'title', 'N/A')} - {getattr(project, 'description', '')[:300]}"
            grant_summary = f"Grant: {getattr(grant, 'title', 'N/A')} - {getattr(grant, 'description', '')[:300]}"
            
            prompt = f"""Rate 0-100 semantic fit. JSON only: {{"semantic_score": N}}
Project: {project_summary}
Grant: {grant_summary}"""
            
            response = model.generate_content(prompt)
            result = json.loads(response.text.strip())
            return min(max(float(result.get("semantic_score", 50)) / 100.0, 0.0), 1.0)
        except Exception as fallback_e:
            logger.warning(f"Gemini fallback failed: {fallback_e}")
            return 0.5
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Gemini JSON response: {e}")
        return 0.5
    except Exception as e:
        logger.warning(f"Gemini semantic scoring error (falling back to neutral): {e}")
        return 0.5


def compute_match_score(project, grant) -> Tuple[int, List[str], List[str]]:
    """
    Hybrid matching: 60% rule-based + 40% Gemini semantic.
    
    Rule-based breakdown (60% of final score):
    - Focus area & objectives: 30%
    - Beneficiary alignment: 25%
    - Budget compatibility: 15%
    - Timeline compatibility: 15%
    - Agency preference: 5%
    - Project completeness: 10%
    
    Gemini semantic (40% of final score):
    - Conceptual alignment, maturity fit, intent alignment
    
    Returns (score_0_to_100, positive_reasons[], negative_reasons[])
    """
    if not passes_eligibility(project, grant):
        return 0, [], ["Does not meet basic eligibility criteria."]

    scores: dict[str, float] = {}
    reasons: List[str] = []
    negative_reasons: List[str] = []

    # ========== RULE-BASED SCORING (60% of final) ==========
    scores["focus"] = score_focus_and_objectives(project, grant)
    scores["beneficiaries"] = score_beneficiary_alignment(project, grant)
    scores["budget"] = score_budget_compatibility(project, grant)
    scores["timeline"] = score_timeline_compatibility(project, grant)
    scores["agency"] = score_agency_preference(project, grant)
    scores["completeness"] = score_project_completeness(project, grant)

    # Calculate rule-based score (60% component)
    rule_based_score = (
        0.30 * scores["focus"]
        + 0.25 * scores["beneficiaries"]
        + 0.15 * scores["budget"]
        + 0.15 * scores["timeline"]
        + 0.05 * scores["agency"]
        + 0.10 * scores["completeness"]
    )

    # ========== GEMINI SEMANTIC SCORING (40% of final) ==========
    gemini_semantic_score = get_gemini_semantic_score(project, grant)

    # ========== HYBRID FINAL SCORE ==========
    # 60% rules + 40% Gemini semantic
    final_score_normalized = 0.6 * rule_based_score + 0.4 * gemini_semantic_score
    final_score = round(100 * final_score_normalized)

    # ========== GENERATE POSITIVE REASONS ==========
    # Top reasons based on the highest contributing component scores (up to 5)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for key, score_value in ranked[:5]:
        if score_value > 0.5:  # Only include strong scores
            if key == "focus":
                reasons.append("Project focus aligns with grant objectives.")
            elif key == "beneficiaries":
                reasons.append("Target beneficiaries match grant priorities.")
            elif key == "budget":
                reasons.append("Requested budget fits the grant funding range.")
            elif key == "timeline":
                reasons.append("Project timeline fits the grant support duration.")
            elif key == "agency":
                reasons.append("Preferred agency is offering this grant.")
            elif key == "completeness":
                reasons.append("Project details are well-specified and complete.")

    # Add semantic intelligence note if score boosted significantly
    if gemini_semantic_score > 0.7 and final_score >= 70:
        reasons.append("Strong contextual and semantic alignment detected.")

    # ========== GENERATE NEGATIVE REASONS ==========
    # Identify areas where match is weak
    for key, score_value in ranked:
        if score_value < 0.5:  # Identify weak areas
            if key == "focus":
                negative_reasons.append("Project focus may differ from grant objectives.")
            elif key == "beneficiaries":
                negative_reasons.append("Target beneficiaries may not align with grant priorities.")
            elif key == "budget":
                negative_reasons.append("Project budget requirements may exceed grant limits.")
            elif key == "timeline":
                negative_reasons.append("Project timeline may not match grant support duration.")
            elif key == "agency":
                negative_reasons.append("Different agency than project preference.")
            elif key == "completeness":
                negative_reasons.append("Project details need more specification.")

    # Add timeline-specific warnings
    closing_date = getattr(grant, "closing_date", None)
    start_date = getattr(project, "project_start_date", None)
    if closing_date and start_date:
        if start_date > closing_date:
            negative_reasons.append("Project start date is after grant closing date.")

    # Add budget-specific warnings
    budget_min = getattr(project, "budget_required_min", None)
    funding_max = getattr(grant, "funding_max", None)
    if budget_min and funding_max:
        try:
            budget_min_value = float(budget_min)
            funding_max_value = float(funding_max)
            if funding_max_value > 0 and budget_min_value > 1.2 * funding_max_value:
                negative_reasons.append("Project minimum budget exceeds grant's maximum funding.")
        except (TypeError, ValueError):
            pass

    # Check project completeness
    completeness = score_project_completeness(project, grant)
    if completeness < 0.5:
        negative_reasons.append("Project description and details should be more comprehensive.")

    # Limit to 5 most relevant per card for display
    reasons = reasons[:5]
    negative_reasons = negative_reasons[:5]

    return int(final_score), reasons, negative_reasons

