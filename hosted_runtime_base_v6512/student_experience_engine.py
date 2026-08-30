"""ScoreMax V6.2.3 student-experience helpers.

This module intentionally contains no Flask dependencies.  It keeps the pathway
catalogue and workload calculations deterministic and easy to test.
"""
from __future__ import annotations

from datetime import date
from typing import Any

MATRIC_COMMON_SUBJECTS = (
    "English",
    "Urdu",
    "Mathematics",
    "Islamiyat",
    "Pakistan Studies",
    "Physics",
    "Chemistry",
    "Biology",
    "Computer Science",
)

PATHWAY_CATALOGUE: tuple[dict[str, Any], ...] = (
    {
        "code": "PRE_MEDICAL",
        "title": "FSc / HSSC Pre-Medical",
        "summary": "Biology, Chemistry and Physics with a route towards health and life-science study.",
        "subjects": ["Biology", "Chemistry", "Physics"],
        "future_assessments": ["MDCAT", "University admission tests"],
        "icon": "🧬",
    },
    {
        "code": "PRE_ENGINEERING",
        "title": "FSc / HSSC Pre-Engineering",
        "summary": "Mathematics, Chemistry and Physics with a route towards engineering and physical sciences.",
        "subjects": ["Mathematics", "Chemistry", "Physics"],
        "future_assessments": ["ECAT", "University admission tests"],
        "icon": "⚙",
    },
    {
        "code": "COMPUTER_SCIENCE",
        "title": "ICS / Computer Science",
        "summary": "A computing-focused route combining Computer Science with Mathematics and related subjects.",
        "subjects": ["Computer Science", "Mathematics", "Physics"],
        "future_assessments": ["University admission tests"],
        "icon": "💻",
    },
    {
        "code": "COMMERCE",
        "title": "ICom / Commerce",
        "summary": "A route towards accounting, finance, business and commerce-related study.",
        "subjects": ["Accounting", "Commerce", "Economics"],
        "future_assessments": ["University admission tests"],
        "icon": "📊",
    },
    {
        "code": "HUMANITIES",
        "title": "FA / Humanities",
        "summary": "A flexible route across humanities, languages and social-science subjects.",
        "subjects": ["Humanities", "Languages", "Social Sciences"],
        "future_assessments": ["University admission tests"],
        "icon": "📚",
    },
    {
        "code": "UNDECIDED",
        "title": "I am still deciding",
        "summary": "Explore routes, compare subjects and save a direction later without locking yourself in.",
        "subjects": [],
        "future_assessments": [],
        "icon": "🧭",
    },
)

PATHWAY_BY_CODE = {row["code"]: row for row in PATHWAY_CATALOGUE}


def is_matric_level(value: object) -> bool:
    text = str(value or "").casefold()
    return "matric" in text or "ssc" in text or "class 9" in text or "class 10" in text


def pathway(code: object) -> dict[str, Any] | None:
    return PATHWAY_BY_CODE.get(str(code or "").strip().upper())


def workload_range(
    pathway_name: str,
    *,
    days_to_exam: int | None = None,
    starting_coverage: float | None = None,
    target_percentage: float | None = None,
) -> dict[str, Any]:
    """Return a weekly recommendation range rather than a rigid daily promise.

    The result is guidance only.  The student's stated availability remains a
    separate input and the plan engine reports whether the route is realistic.
    """
    base = {
        "Core": (300, 480),      # 5-8 hours/week
        "Stretch": (420, 660),   # 7-11 hours/week
        "Peak": (540, 840),      # 9-14 hours/week
        "Custom": (300, 720),
    }.get(pathway_name, (300, 480))
    low, high = base

    if days_to_exam is not None:
        if days_to_exam <= 45:
            low += 120
            high += 180
        elif days_to_exam <= 90:
            low += 60
            high += 120
        elif days_to_exam >= 240:
            low = max(180, low - 60)
            high = max(low + 120, high - 60)

    if starting_coverage is not None:
        coverage = float(starting_coverage)
        if coverage < 25:
            low += 60
            high += 120
        elif coverage >= 75:
            low = max(180, low - 30)

    if target_percentage is not None and float(target_percentage) >= 90:
        low += 60
        high += 90

    return {
        "minimum_minutes": int(low),
        "maximum_minutes": int(high),
        "minimum_hours": round(low / 60, 1),
        "maximum_hours": round(high / 60, 1),
        "label": f"{round(low / 60, 1):g}–{round(high / 60, 1):g} focused hours/week",
    }


def workload_fit(available_weekly_minutes: int, recommendation: dict[str, Any]) -> dict[str, str]:
    available = max(0, int(available_weekly_minutes or 0))
    low = int(recommendation["minimum_minutes"])
    high = int(recommendation["maximum_minutes"])
    if not available:
        return {"status": "Not set", "tone": "neutral", "message": "Tell ScoreMax how much time you can realistically protect each week."}
    if available < low:
        gap = max(1, round((low - available) / 60, 1))
        return {"status": "Needs prioritisation", "tone": "warning", "message": f"Your available time is about {gap:g} hour(s) below this route's recommended weekly range. ScoreMax will prioritise the highest-value work."}
    if available > high:
        return {"status": "Comfortable capacity", "tone": "good", "message": "Your available time is above the recommended range; ScoreMax will protect recovery and rest rather than fill every minute."}
    return {"status": "Realistic", "tone": "good", "message": "Your available time sits inside the recommended weekly range for this route."}


def minutes_per_study_day(weekly_minutes: int, days_per_week: int) -> int:
    days = max(1, min(7, int(days_per_week or 1)))
    return max(20, min(480, round(max(0, int(weekly_minutes or 0)) / days)))
