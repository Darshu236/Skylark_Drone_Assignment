from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dateutil.parser import parse as parse_date


DATE_FMT = "%Y-%m-%d"
SKILL_TO_CAPABILITY = {
    "Mapping": "RGB",
    "Survey": "RGB",
    "Inspection": "RGB",
    "Thermal": "Thermal",
}


def _split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _is_empty_assignment(value: str | None) -> bool:
    if value is None:
        return True
    cleaned = value.strip()
    return cleaned in {"", "-", "–", "â€–"}


def _date(value: str) -> datetime:
    return parse_date(value).replace(tzinfo=None)


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _date(a_start) <= _date(b_end) and _date(b_start) <= _date(a_end)


def normalize_text(value: str) -> str:
    return value.lower().strip()


@dataclass
class AssignmentRecommendation:
    pilot: dict[str, Any] | None
    drone: dict[str, Any] | None
    issues: list[str]


def filter_pilots(
    pilots: list[dict[str, Any]],
    skill: str | None,
    cert: str | None,
    location: str | None,
    available_only: bool = True,
) -> list[dict[str, Any]]:
    results = []
    for p in pilots:
        if available_only and normalize_text(p.get("status", "")) != "available":
            continue
        if skill:
            skills = [s.lower() for s in _split_list(p.get("skills", ""))]
            if skill.lower() not in skills:
                continue
        if cert:
            certs = [c.lower() for c in _split_list(p.get("certifications", ""))]
            if cert.lower() not in certs:
                continue
        if location and normalize_text(p.get("location", "")) != location.lower():
            continue
        results.append(p)
    return results


def filter_drones(
    drones: list[dict[str, Any]],
    capability: str | None,
    location: str | None,
    available_only: bool = True,
) -> list[dict[str, Any]]:
    results = []
    for d in drones:
        if available_only and normalize_text(d.get("status", "")) != "available":
            continue
        if capability:
            caps = [c.lower() for c in _split_list(d.get("capabilities", ""))]
            if capability.lower() not in caps:
                continue
        if location and normalize_text(d.get("location", "")) != location.lower():
            continue
        results.append(d)
    return results


def recommend_assignment(
    project_id: str,
    pilots: list[dict[str, Any]],
    drones: list[dict[str, Any]],
    missions: list[dict[str, Any]],
) -> AssignmentRecommendation:
    mission = next((m for m in missions if m.get("project_id") == project_id), None)
    if not mission:
        return AssignmentRecommendation(None, None, [f"Unknown project: {project_id}"])

    required_skill = mission.get("required_skills", "")
    required_cert = mission.get("required_certs", "")
    location = mission.get("location", "")
    start = mission.get("start_date", "")
    end = mission.get("end_date", "")

    eligible_pilots = []
    issues = []
    for p in pilots:
        if normalize_text(p.get("status", "")) != "available":
            continue
        if normalize_text(p.get("location", "")) != normalize_text(location):
            continue
        skills = [s.lower() for s in _split_list(p.get("skills", ""))]
        if normalize_text(required_skill) not in skills:
            continue
        certs = [c.lower() for c in _split_list(p.get("certifications", ""))]
        if normalize_text(required_cert) not in certs:
            continue
        if not _is_empty_assignment(p.get("current_assignment")):
            assigned = next((m for m in missions if m.get("project_id") == p.get("current_assignment")), None)
            if assigned and _overlaps(start, end, assigned["start_date"], assigned["end_date"]):
                continue
        eligible_pilots.append(p)

    required_capability = SKILL_TO_CAPABILITY.get(required_skill, "RGB")
    eligible_drones = filter_drones(drones, required_capability, location, available_only=True)

    if not eligible_pilots:
        issues.append("No available pilot meets skill, cert, and location requirements.")
    if not eligible_drones:
        issues.append("No available drone matches capability and location requirements.")

    pilot = eligible_pilots[0] if eligible_pilots else None
    drone = eligible_drones[0] if eligible_drones else None
    return AssignmentRecommendation(pilot, drone, issues)


def detect_conflicts(
    pilots: list[dict[str, Any]],
    drones: list[dict[str, Any]],
    missions: list[dict[str, Any]],
) -> list[str]:
    conflicts: list[str] = []
    mission_map = {m["project_id"]: m for m in missions}

    # Pilot assignment conflicts
    for p in pilots:
        assignment = p.get("current_assignment")
        if not _is_empty_assignment(assignment):
            mission = mission_map.get(assignment)
            if not mission:
                conflicts.append(f"Pilot {p.get('name')} assigned to unknown mission {assignment}.")
                continue
            skills = [s.lower() for s in _split_list(p.get("skills", ""))]
            if normalize_text(mission.get("required_skills", "")) not in skills:
                conflicts.append(f"Pilot {p.get('name')} lacks required skill for {assignment}.")
            certs = [c.lower() for c in _split_list(p.get("certifications", ""))]
            if normalize_text(mission.get("required_certs", "")) not in certs:
                conflicts.append(f"Pilot {p.get('name')} lacks required certs for {assignment}.")
            if normalize_text(p.get("location", "")) != normalize_text(mission.get("location", "")):
                conflicts.append(f"Pilot {p.get('name')} location mismatch for {assignment}.")

    # Drone assignment conflicts
    for d in drones:
        assignment = d.get("current_assignment")
        if not _is_empty_assignment(assignment):
            mission = mission_map.get(assignment)
            if not mission:
                conflicts.append(f"Drone {d.get('drone_id')} assigned to unknown mission {assignment}.")
                continue
            if normalize_text(d.get("status", "")) == "maintenance":
                conflicts.append(f"Drone {d.get('drone_id')} is in maintenance but assigned to {assignment}.")
            if normalize_text(d.get("location", "")) != normalize_text(mission.get("location", "")):
                conflicts.append(f"Drone {d.get('drone_id')} location mismatch for {assignment}.")
            required_skill = mission.get("required_skills", "")
            required_cap = SKILL_TO_CAPABILITY.get(required_skill, "RGB").lower()
            caps = [c.lower() for c in _split_list(d.get("capabilities", ""))]
            if required_cap not in caps:
                conflicts.append(f"Drone {d.get('drone_id')} lacks capability for {assignment}.")

    # Overlapping pilot assignments (based on mission dates)
    for p in pilots:
        assignment = p.get("current_assignment")
        if _is_empty_assignment(assignment):
            continue
        m1 = mission_map.get(assignment)
        if not m1:
            continue
        for m2 in missions:
            if m2["project_id"] == m1["project_id"]:
                continue
            if _overlaps(m1["start_date"], m1["end_date"], m2["start_date"], m2["end_date"]):
                if assignment == m1["project_id"]:
                    conflicts.append(
                        f"Pilot {p.get('name')} assigned to {assignment} overlaps with {m2['project_id']}."
                    )
                break

    # Pilot-drone location mismatch for same assignment
    drone_by_assignment = {d.get("current_assignment"): d for d in drones if d.get("current_assignment")}
    for p in pilots:
        assignment = p.get("current_assignment")
        if not _is_empty_assignment(assignment) and assignment in drone_by_assignment:
            d = drone_by_assignment[assignment]
            if normalize_text(p.get("location", "")) != normalize_text(d.get("location", "")):
                conflicts.append(
                    f"Pilot {p.get('name')} and drone {d.get('drone_id')} are in different locations for {assignment}."
                )

    return conflicts


def urgent_reassignment_plan(
    missions: list[dict[str, Any]],
    pilots: list[dict[str, Any]],
    drones: list[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []
    urgent = [m for m in missions if normalize_text(m.get("priority", "")) in ("urgent", "high")]
    if not urgent:
        return ["No urgent or high-priority missions found."]

    for m in urgent:
        rec = recommend_assignment(m["project_id"], pilots, drones, missions)
        if rec.pilot and rec.drone and not rec.issues:
            continue
        # Find a pilot from a lower priority mission
        lower = [x for x in missions if normalize_text(x.get("priority", "")) in ("standard", "low")]
        candidate = None
        for lm in lower:
            for p in pilots:
                if p.get("current_assignment") == lm["project_id"]:
                    candidate = p
                    break
            if candidate:
                break
        if candidate:
            recommendations.append(
                f"Consider reassigning pilot {candidate.get('name')} from {candidate.get('current_assignment')} "
                f"to urgent mission {m['project_id']}."
            )
        else:
            recommendations.append(
                f"No reassignable pilots found for urgent mission {m['project_id']}."
            )

    return recommendations
