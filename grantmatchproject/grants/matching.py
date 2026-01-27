from __future__ import annotations

from typing import List, Set, Tuple


def normalize(text: str | None) -> Set[str]:
    if not text:
        return set()
    return {word.lower() for word in str(text).split() if len(word) > 2}


def overlap_score(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.5
    return min(len(a & b) / len(a), 1.0)


def compute_match_score(project, grant) -> Tuple[int, List[str]]:
    """Return (score_0_to_100, reasons[])."""
    if getattr(grant, "status", None) == "closed":
        return 0, []

    scores: dict[str, float] = {}
    reasons: List[str] = []

    project_tokens = normalize(
        f"{getattr(project, 'focus_area', '')} "
        f"{getattr(project, 'description', '')} "
        f"{getattr(project, 'need_support_for', '')}"
    )
    grant_tokens = normalize(f"{getattr(grant, 'title', '')} {getattr(grant, 'description', '')}")
    scores["focus"] = overlap_score(project_tokens, grant_tokens)

    beneficiary_types = getattr(project, "beneficiary_types", []) or []
    if isinstance(beneficiary_types, str):
        beneficiary_set = normalize(beneficiary_types)
    else:
        beneficiary_set = {str(x).lower() for x in beneficiary_types if str(x).strip()}
    scores["beneficiaries"] = overlap_score(beneficiary_set, normalize(getattr(grant, "description", "")))

    budget_min = getattr(project, "budget_required_min", None)
    funding_max = getattr(grant, "funding_max", None)
    scores["budget"] = 1.0 if (budget_min and funding_max and budget_min <= funding_max) else 0.5

    closing_date = getattr(grant, "closing_date", None)
    start_date = getattr(project, "project_start_date", None)
    if closing_date and start_date:
        scores["timeline"] = 1.0 if start_date <= closing_date else 0.0
    else:
        scores["timeline"] = 0.5

    agency = getattr(grant, "agency", None)
    agency_acronym = getattr(agency, "acronym", None) if agency else None
    want_support_from = getattr(project, "want_support_from", []) or []
    scores["agency"] = 1.0 if (agency_acronym and agency_acronym in want_support_from) else 0.0

    final_score = round(
        100
        * (
            0.20 * scores["focus"]
            + 0.15 * scores["beneficiaries"]
            + 0.15 * scores["budget"]
            + 0.10 * scores["timeline"]
            + 0.05 * scores["agency"]
        )
    )

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for key, _ in ranked[:3]:
        if key == "focus":
            reasons.append("Project focus aligns with grant objectives.")
        elif key == "beneficiaries":
            reasons.append("Target beneficiaries match grant priorities.")
        elif key == "budget":
            reasons.append("Requested budget fits the grant funding range.")
        elif key == "timeline":
            reasons.append("Project timeline fits the grant deadline.")
        elif key == "agency":
            reasons.append("Preferred agency is offering this grant.")

    return int(final_score), reasons
