"""Transparent adaptive learning policy; no external AI or account access.

Skill prerequisites are advisory, not an assertion that an unassessed skill is weak.
All outcomes remain synthetic until genuine assessment adapters are connected.
"""
from __future__ import annotations

PREREQUISITES = {
    "dsa": (),
    "sql": (),
    "systems": ("dsa", "sql"),
    "python": (),
    "ml": ("python", "dsa"),
}

TOPICS = {
    "dsa": {"title": "Reason about algorithms and their complexity", "minutes": 15},
    "sql": {"title": "Practice relational queries and database fundamentals", "minutes": 15},
    "systems": {"title": "Explore system design trade-offs", "minutes": 20},
    "python": {"title": "Practice Python fundamentals", "minutes": 15},
    "ml": {"title": "Evaluate machine learning models", "minutes": 20},
}


def skill_graph() -> dict:
    """Return the stable skill taxonomy without personal evidence."""
    return {
        "version": "demo-v1",
        "nodes": [
            {"id": skill, "title": meta["title"], "prerequisites": list(PREREQUISITES[skill])}
            for skill, meta in TOPICS.items()
        ],
        "edges": [
            {"from": prerequisite, "to": skill}
            for skill, required in PREREQUISITES.items()
            for prerequisite in required
        ],
        "note": "Curated demo prerequisite relationships, not inferred student deficiencies.",
    }


def make_roadmap(snapshot: dict, minutes: int = 45) -> dict:
    """Build a small explainable practice plan from trustworthy server-scored results."""
    if type(minutes) is not int or not 15 <= minutes <= 120:
        raise ValueError("minutes must be an integer between 15 and 120")
    by_skill = {item["id"]: item for item in snapshot["competencies"]}
    activities: list[dict] = []
    seen: set[str] = set()
    used = 0

    def append(skill: str, *, prerequisite_for: str | None = None) -> None:
        nonlocal used
        if skill in seen:
            return
        seen.add(skill)
        c = by_skill[skill]
        count, correct = c["attempts"], c["correct"]
        if count == 0:
            activity_type, length = "baseline-assessment", 10
            why = f"No graded evidence for {c['name']} yet; run a baseline check."
        elif count < 3:
            activity_type, length = "reinforcement", 15
            why = f"Only {count} graded attempt(s) for {c['name']}; collect more evidence before judging proficiency."
        elif correct / count < 0.7:
            activity_type, length = "guided-practice", 15
            why = f"{correct}/{count} recent graded answers correct in {c['name']}; revisit the underlying concept."
        else:
            activity_type, length = "transfer-challenge", 20
            why = f"{correct}/{count} graded answers correct in {c['name']}; test transfer to a new problem."
        if prerequisite_for is not None:
            why += f" This is a prerequisite check before {by_skill[prerequisite_for]['name']}."
        if used + length > minutes:
            return
        used += length
        activities.append({
            "skill": skill, "title": TOPICS[skill]["title"], "type": activity_type,
            "minutes": length, "why": why, "content_status": "local-curated-demo",
        })

    for competency in snapshot["competencies"]:
        if len(activities) >= 4:
            break
        skill = competency["id"]
        for prerequisite in PREREQUISITES[skill]:
            if len(activities) >= 4:
                break
            parent = by_skill[prerequisite]
            if parent["attempts"] == 0 or (parent["attempts"] >= 3 and parent["correct"] / parent["attempts"] < 0.7):
                append(prerequisite, prerequisite_for=skill)
        if len(activities) < 4:
            append(skill)
    return {
        "learner_id": snapshot["id"],
        "target_role": snapshot["target_role"],
        "minutes_budget": minutes,
        "minutes_planned": used,
        "activities": activities,
        "policy": "prerequisite-aware-v1",
        "limitations": "A transparent demo practice plan, not evidence that learning outcomes improved.",
    }
