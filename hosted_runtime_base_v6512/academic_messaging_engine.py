"""Governed teacher-discovery and academic-messaging helpers for ScoreMax V6.1.

This module is deliberately framework-light so policy behaviour can be tested without
running the Flask application. It does not award mastery or academically endorse tutors.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

ALLOWED_MEETING_HOSTS = {
    "meet.google.com",
    "zoom.us",
    "www.zoom.us",
    "teams.microsoft.com",
    "teams.live.com",
}

CONTACT_PATTERNS = [
    ("phone_number", re.compile(r"(?<!\w)(?:\+?92|0)?[\s.-]?(?:3\d{2}|\d{2,4})[\s.-]?\d{6,8}(?!\w)")),
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("whatsapp_reference", re.compile(r"\b(?:whats\s*app|wa\.me|w\.me)\b", re.I)),
]

RISK_PATTERNS = [
    ("abusive_language", re.compile(r"\b(?:idiot|stupid|shut\s+up|hate\s+you)\b", re.I)),
    ("payment_scam", re.compile(r"\b(?:send\s+money|bank\s+transfer|easypaisa|jazzcash)\b", re.I)),
    ("off_platform_pressure", re.compile(r"\b(?:delete\s+this\s+chat|keep\s+this\s+secret|do\s+not\s+tell)\b", re.I)),
]


def clean_text(value: object, limit: int = 4000) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def parse_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        raw = str(value).strip()
        if not raw:
            return []
        try:
            loaded = json.loads(raw)
            items = loaded if isinstance(loaded, list) else re.split(r"[,|]", raw)
        except Exception:
            items = re.split(r"[,|]", raw)
    out: list[str] = []
    seen = set()
    for item in items:
        text = clean_text(item, 80)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out[:30]


def profile_completeness(profile: dict) -> int:
    weighted = {
        "headline": 10,
        "bio": 15,
        "subjects_json": 15,
        "frameworks_json": 10,
        "qualifications_text": 15,
        "experience_years": 5,
        "languages_json": 5,
        "delivery_modes_json": 5,
        "platforms_json": 5,
        "availability_text": 5,
        "response_expectation_hours": 5,
        "office_hours": 5,
    }
    score = 0
    for field, points in weighted.items():
        value = profile.get(field)
        if field.endswith("_json"):
            value = parse_list(value)
        if value not in (None, "", [], 0, "0"):
            score += points
    return min(100, score)


def detect_message_policy(body: object, sender_role: str = "student", message_type: str = "TEXT") -> dict:
    text = clean_text(body, 6000)
    flags: list[str] = []
    for label, pattern in CONTACT_PATTERNS:
        if pattern.search(text):
            flags.append(label)
    for label, pattern in RISK_PATTERNS:
        if pattern.search(text):
            flags.append(label)

    urls = re.findall(r"https?://[^\s<>()]+", text, flags=re.I)
    meeting_hosts: list[str] = []
    unapproved_hosts: list[str] = []
    for url in urls:
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        if host in ALLOWED_MEETING_HOSTS or any(host.endswith("." + allowed) for allowed in ALLOWED_MEETING_HOSTS):
            meeting_hosts.append(host)
        else:
            unapproved_hosts.append(host or "invalid_url")

    if message_type == "MEETING_LINK":
        if sender_role != "teacher":
            flags.append("meeting_link_teacher_only")
        if not meeting_hosts:
            flags.append("unapproved_meeting_link")
    elif urls and unapproved_hosts:
        flags.append("external_link")

    blocking = {
        "phone_number",
        "email_address",
        "whatsapp_reference",
        "payment_scam",
        "off_platform_pressure",
        "meeting_link_teacher_only",
        "unapproved_meeting_link",
        "external_link",
    }
    moderation_status = "HELD" if any(flag in blocking for flag in flags) else "VISIBLE"
    if "abusive_language" in flags:
        moderation_status = "HELD"
    return {
        "clean_body": text,
        "flags": sorted(set(flags)),
        "moderation_status": moderation_status,
        "meeting_hosts": sorted(set(meeting_hosts)),
        "unapproved_hosts": sorted(set(unapproved_hosts)),
    }


def validate_teacher_listing(data: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    service_type = clean_text(data.get("service_type"), 20).upper()
    if service_type not in {"ONE_TO_ONE", "GROUP"}:
        errors.append("Service type must be one-to-one or group.")
    if not clean_text(data.get("title"), 120):
        errors.append("Listing title is required.")
    if not clean_text(data.get("subject"), 80):
        errors.append("Subject is required.")
    try:
        price_minor = int(data.get("price_minor") or 0)
    except Exception:
        price_minor = -1
    if price_minor < 0:
        errors.append("Price cannot be negative.")
    if service_type == "GROUP":
        try:
            capacity = int(data.get("capacity") or 0)
        except Exception:
            capacity = 0
        if capacity < 2:
            errors.append("A group listing needs capacity for at least two students.")
    platforms = parse_list(data.get("platform_options_json") or data.get("platforms"))
    if not platforms:
        warnings.append("Add at least one teaching platform or local delivery method.")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "service_type": service_type, "price_minor": max(price_minor, 0), "platforms": platforms}


def teacher_match_score(profile: dict, listing: dict, filters: dict) -> int:
    score = 0
    subject = clean_text(filters.get("subject"), 80).casefold()
    framework = clean_text(filters.get("framework"), 80).casefold()
    service = clean_text(filters.get("service_type"), 20).upper()
    mode = clean_text(filters.get("delivery_mode"), 20).upper()
    subjects = [x.casefold() for x in parse_list(profile.get("subjects_json"))]
    frameworks = [x.casefold() for x in parse_list(profile.get("frameworks_json"))]
    if subject:
        score += 40 if subject in subjects or subject == clean_text(listing.get("subject"), 80).casefold() else 0
    else:
        score += 10
    if framework:
        score += 20 if framework in frameworks or framework == clean_text(listing.get("framework"), 80).casefold() else 0
    else:
        score += 5
    if service:
        score += 15 if service == clean_text(listing.get("service_type"), 20).upper() else 0
    if mode:
        score += 10 if mode == clean_text(listing.get("delivery_mode"), 20).upper() else 0
    score += min(10, int(profile.get("average_rating_x10") or 0) // 5)
    score += 5 if profile.get("identity_verification_status") == "VERIFIED" else 0
    return min(100, score)
