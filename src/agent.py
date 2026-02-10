import os
import re
from typing import Any

from .logic import (
    detect_conflicts,
    filter_drones,
    filter_pilots,
    normalize_text,
    recommend_assignment,
    urgent_reassignment_plan,
)
from .storage import DataStore
from .llm import OllamaClient


class DroneOpsAgent:
    def __init__(self) -> None:
        self.store = DataStore()
        self.use_llm = os.getenv("USE_LLM", "true").lower() == "true"
        self.ollama = OllamaClient()

    def handle(self, message: str) -> tuple[str, dict[str, Any]]:
        text = message.strip()
        normalized = self._normalize_text(text)
        lower = normalized.lower()

        pilots = self.store.get_pilots()
        drones = self.store.get_drones()
        missions = self.store.get_missions()

        if not text:
            return "Please provide a request.", {}

        if lower in {"hi", "hello", "hey", "hii", "hola"}:
            return (
                "Hi! I can help with pilots, drones, missions, assignments, and conflicts.",
                {},
            )
        if lower in {"how are you", "how r u", "how are u"}:
            return ("I’m good, thanks for asking. How can I help you today?", {})
        if lower in {"what is your name", "what's your name", "your name"}:
            return ("I’m the Drone Operations Coordinator assistant.", {})

        if "help" in lower:
            return (
                "Try: 'find available mapping pilots in Bangalore', "
                "'assign PRJ001', 'update pilot P001 status On Leave', "
                "'find available drones with Thermal in Mumbai', "
                "'detect conflicts', or 'urgent reassignment'.",
                {},
            )

        if "add pilot" in lower:
            return self._add_pilot(text, pilots)
        if "add drone" in lower:
            return self._add_drone(text, drones)
        if "add mission" in lower or "add project" in lower:
            return self._add_mission(text, missions)

        # LLM routing (optional)
        if self.use_llm:
            routed = self.ollama.classify(text)
            if routed and isinstance(routed, dict):
                handled = self._handle_routed(routed, pilots, drones, missions, text)
                if handled[0] != "I didn't understand. Say 'help' for examples.":
                    return handled

        # Fuzzy spelling correction fallback
        corrected = self._fuzzy_correct(text, pilots, drones, missions)
        if corrected and corrected != text:
            return self.handle(corrected)

        if re.search(r"\bassign\b", lower) and "assigned" not in lower:
            proj = self._extract_project_id(text)
            if not proj:
                return "Please specify a project id like PRJ001.", {}
            rec = recommend_assignment(proj, pilots, drones, missions)
            if rec.issues:
                return self._format_assignment_issues(proj, rec.issues), {"issues": rec.issues, "project": proj}
            updated = False
            if rec.pilot:
                for p in pilots:
                    if p.get("pilot_id") == rec.pilot.get("pilot_id"):
                        p["current_assignment"] = proj
                        p["status"] = "Assigned"
                        updated = True
            if rec.drone:
                for d in drones:
                    if d.get("drone_id") == rec.drone.get("drone_id"):
                        d["current_assignment"] = proj
                        d["status"] = "Assigned"
                        updated = True
            if updated:
                self.store.update_pilots(pilots)
                self.store.update_drones(drones)
            return (
                f"Assigned pilot {rec.pilot.get('name')} and drone {rec.drone.get('drone_id')} to {proj}.",
                {"pilot": rec.pilot, "drone": rec.drone, "project": proj},
            )

        if "update pilot" in lower or "set pilot" in lower or "make" in lower:
            pilot_id = self._extract_pilot_id(text)
            status = self._extract_status(text)
            if not pilot_id:
                pilot = self._extract_pilot_by_name(text, pilots)
                if pilot:
                    pilot_id = pilot.get("pilot_id")
            if not pilot_id or not status:
                return "Usage: update pilot P001 status Available/On Leave/Unavailable/Assigned.", {}
            updated = False
            for p in pilots:
                if normalize_text(p.get("pilot_id", "")) == pilot_id.lower():
                    p["status"] = status
                    updated = True
            if updated:
                self.store.update_pilots(pilots)
                return f"Pilot {pilot_id} status updated to {status}.", {"pilot_id": pilot_id, "status": status}
            return f"Pilot {pilot_id} not found.", {}

        if "update drone" in lower or "set drone" in lower:
            drone_id = self._extract_drone_id(text)
            status = self._extract_status(text)
            if not drone_id or not status:
                return "Usage: update drone D001 status Available/Maintenance/Assigned.", {}
            updated = False
            for d in drones:
                if normalize_text(d.get("drone_id", "")) == drone_id.lower():
                    d["status"] = status
                    updated = True
            if updated:
                self.store.update_drones(drones)
                return f"Drone {drone_id} status updated to {status}.", {"drone_id": drone_id, "status": status}
            return f"Drone {drone_id} not found.", {}

        intent = self._classify_intent(lower, text, pilots, drones)

        if intent == "pilots_available":
            skill = self._extract_skill(text, pilots)
            cert = self._extract_cert(text, pilots)
            location = self._extract_location(text, pilots)
            matches = filter_pilots(pilots, skill, cert, location, available_only=True)
            if not matches:
                return "No available pilots matched.", {"pilots": []}
            names = ", ".join([p.get("name") for p in matches])
            return f"Available pilots: {names}.", {"pilots": matches}

        if intent == "drones_available":
            capability = self._extract_capability(text, drones)
            location = self._extract_location(text, drones)
            matches = filter_drones(drones, capability, location, available_only=True)
            if not matches:
                return "No available drones matched.", {"drones": []}
            ids = ", ".join([d.get("drone_id") for d in matches])
            return f"Available drones: {ids}.", {"drones": matches}

        if "drone" in lower and ("active" in lower or "assigned" in lower):
            matches = [d for d in drones if str(d.get("status", "")).lower() == "assigned"]
            if not matches:
                return "No active/assigned drones.", {"drones": []}
            ids = ", ".join([d.get("drone_id") for d in matches])
            return f"Assigned drones: {ids}.", {"drones": matches}

        # Location-only query fallback: "who are all in Mumbai"
        if intent == "pilots_in_location":
            location = self._extract_location(text, pilots)
            if location:
                matches = filter_pilots(pilots, None, None, location, available_only=False)
                if not matches:
                    return f"No pilots found in {location}.", {"pilots": []}
                names = ", ".join([p.get("name") for p in matches])
                return f"Pilots in {location}: {names}.", {"pilots": matches}
        if intent == "drones_in_location":
            location = self._extract_location(text, drones)
            if location:
                matches = filter_drones(drones, None, location, available_only=False)
                if not matches:
                    return f"No drones found in {location}.", {"drones": []}
                ids = ", ".join([d.get("drone_id") for d in matches])
                return f"Drones in {location}: {ids}.", {"drones": matches}

        if intent == "any_available":
            p_matches = filter_pilots(pilots, None, None, None, available_only=True)
            d_matches = filter_drones(drones, None, None, available_only=True)
            p_names = ", ".join([p.get("name") for p in p_matches]) or "None"
            d_ids = ", ".join([d.get("drone_id") for d in d_matches]) or "None"
            return (
                f"Available pilots: {p_names}. Available drones: {d_ids}.",
                {"pilots": p_matches, "drones": d_matches},
            )

        if "conflict" in lower:
            conflicts = detect_conflicts(pilots, drones, missions)
            if not conflicts:
                return "No conflicts detected.", {"conflicts": []}
            return "Conflicts found: " + " ".join(conflicts), {"conflicts": conflicts}

        if ("resources" in lower or "assigned to" in lower) and "prj" in lower:
            proj = self._extract_project_id(text)
            if not proj:
                return "Please specify a project id like PRJ001.", {}
            assigned_pilots = [p for p in pilots if p.get("current_assignment") == proj]
            assigned_drones = [d for d in drones if d.get("current_assignment") == proj]
            if not assigned_pilots and not assigned_drones:
                return f"No resources currently assigned to {proj}.", {"project": proj}
            names = ", ".join([p.get("name") for p in assigned_pilots]) or "None"
            ids = ", ".join([d.get("drone_id") for d in assigned_drones]) or "None"
            return (
                f"Resources assigned to {proj}: pilots {names}; drones {ids}.",
                {"project": proj, "pilots": assigned_pilots, "drones": assigned_drones},
            )

        if "which drone" in lower and "prj" in lower:
            proj = self._extract_project_id(text)
            if not proj:
                return "Please specify a project id like PRJ001.", {}
            rec = recommend_assignment(proj, pilots, drones, missions)
            if rec.drone:
                return (
                    f"Recommended drone {rec.drone.get('drone_id')} for {proj}.",
                    {"drone": rec.drone},
                )
            return "No suitable drone found for that project.", {"project": proj, "issues": rec.issues}

        if "assigned" in lower or "assignment" in lower:
            pilot = self._extract_pilot_by_name(text, pilots)
            if pilot:
                assignment = pilot.get("current_assignment")
                if not assignment or assignment in {"–", "â€–", "-"}:
                    return f"{pilot.get('name')} is not currently assigned.", {"pilot": pilot}
                return f"{pilot.get('name')} is currently assigned to {assignment}.", {"pilot": pilot}

        if "urgent" in lower and "reassign" in lower:
            plan = urgent_reassignment_plan(missions, pilots, drones)
            return "Urgent reassignment plan: " + " ".join(plan), {"plan": plan}

        # LLM fallback answer if enabled
        if self.use_llm:
            context = {
                "pilots": pilots,
                "drones": drones,
                "missions": missions,
            }
            answer = self.ollama.answer(text, context)
            if answer:
                return answer, {}

        return "I didn't understand. Say 'help' for examples.", {}

    def _handle_routed(
        self,
        routed: dict[str, Any],
        pilots: list[dict[str, Any]],
        drones: list[dict[str, Any]],
        missions: list[dict[str, Any]],
        text: str,
    ) -> tuple[str, dict[str, Any]]:
        intent = str(routed.get("intent", "unknown"))
        project_id = routed.get("project_id") or self._extract_project_id(text)
        pilot_name = routed.get("pilot_name")
        status = routed.get("status")
        location = routed.get("location")
        skill = routed.get("skill")
        cert = routed.get("certification")
        capability = routed.get("capability")

        if intent == "greeting":
            return "Hi! I can help with pilots, drones, missions, assignments, and conflicts.", {}

        if intent == "pilots_available":
            matches = filter_pilots(pilots, skill, cert, location, available_only=True)
            if not matches:
                return "No available pilots matched.", {"pilots": []}
            names = ", ".join([p.get("name") for p in matches])
            return f"Available pilots: {names}.", {"pilots": matches}

        if intent == "drones_available":
            matches = filter_drones(drones, capability, location, available_only=True)
            if not matches:
                return "No available drones matched.", {"drones": []}
            ids = ", ".join([d.get("drone_id") for d in matches])
            return f"Available drones: {ids}.", {"drones": matches}

        if intent == "any_available":
            p_matches = filter_pilots(pilots, None, None, None, available_only=True)
            d_matches = filter_drones(drones, None, None, available_only=True)
            p_names = ", ".join([p.get("name") for p in p_matches]) or "None"
            d_ids = ", ".join([d.get("drone_id") for d in d_matches]) or "None"
            return (
                f"Available pilots: {p_names}. Available drones: {d_ids}.",
                {"pilots": p_matches, "drones": d_matches},
            )

        if intent == "pilots_in_location":
            loc = location or self._extract_location(text, pilots)
            matches = filter_pilots(pilots, None, None, loc, available_only=False)
            if not matches:
                return f"No pilots found in {loc}.", {"pilots": []}
            names = ", ".join([p.get("name") for p in matches])
            return f"Pilots in {loc}: {names}.", {"pilots": matches}

        if intent == "drones_in_location":
            loc = location or self._extract_location(text, drones)
            matches = filter_drones(drones, None, loc, available_only=False)
            if not matches:
                return f"No drones found in {loc}.", {"drones": []}
            ids = ", ".join([d.get("drone_id") for d in matches])
            return f"Drones in {loc}: {ids}.", {"drones": matches}

        if intent == "assignment_recommend":
            if not project_id:
                return "Please specify a project id like PRJ001.", {}
            rec = recommend_assignment(project_id, pilots, drones, missions)
            if rec.issues:
                return self._format_assignment_issues(project_id, rec.issues), {"issues": rec.issues, "project": project_id}
            return (
                f"Recommended pilot {rec.pilot.get('name')} and drone {rec.drone.get('drone_id')} for {project_id}.",
                {"pilot": rec.pilot, "drone": rec.drone},
            )

        if intent == "assignment_update":
            if not project_id:
                return "Please specify a project id like PRJ001.", {}
            rec = recommend_assignment(project_id, pilots, drones, missions)
            if rec.issues:
                return self._format_assignment_issues(project_id, rec.issues), {"issues": rec.issues, "project": project_id}
            updated = False
            if rec.pilot:
                for p in pilots:
                    if p.get("pilot_id") == rec.pilot.get("pilot_id"):
                        p["current_assignment"] = project_id
                        p["status"] = "Assigned"
                        updated = True
            if rec.drone:
                for d in drones:
                    if d.get("drone_id") == rec.drone.get("drone_id"):
                        d["current_assignment"] = project_id
                        d["status"] = "Assigned"
                        updated = True
            if updated:
                self.store.update_pilots(pilots)
                self.store.update_drones(drones)
            return (
                f"Assigned pilot {rec.pilot.get('name')} and drone {rec.drone.get('drone_id')} to {project_id}.",
                {"pilot": rec.pilot, "drone": rec.drone, "project": project_id},
            )

        if intent == "pilot_status_update":
            pilot = self._extract_pilot_by_name(pilot_name or text, pilots)
            if not pilot:
                return "Pilot not found.", {}
            if not status:
                return "Please specify a status (Available, On Leave, Unavailable, Assigned).", {}
            for p in pilots:
                if p.get("pilot_id") == pilot.get("pilot_id"):
                    p["status"] = status
            self.store.update_pilots(pilots)
            return f"Pilot {pilot.get('pilot_id')} status updated to {status}.", {"pilot_id": pilot.get("pilot_id"), "status": status}

        if intent == "drone_status_update":
            drone_id = routed.get("drone_id") or self._extract_drone_id(text)
            if not drone_id or not status:
                return "Please specify drone id and status.", {}
            for d in drones:
                if normalize_text(d.get("drone_id", "")) == str(drone_id).lower():
                    d["status"] = status
            self.store.update_drones(drones)
            return f"Drone {drone_id} status updated to {status}.", {"drone_id": drone_id, "status": status}

        if intent == "pilot_assignment_query":
            pilot = self._extract_pilot_by_name(pilot_name or text, pilots)
            if pilot:
                assignment = pilot.get("current_assignment")
                if not assignment or assignment in {"–", "â€–", "-"}:
                    return f"{pilot.get('name')} is not currently assigned.", {"pilot": pilot}
                return f"{pilot.get('name')} is currently assigned to {assignment}.", {"pilot": pilot}

        if intent == "project_resources":
            if not project_id:
                return "Please specify a project id like PRJ001.", {}
            assigned_pilots = [p for p in pilots if p.get("current_assignment") == project_id]
            assigned_drones = [d for d in drones if d.get("current_assignment") == project_id]
            if not assigned_pilots and not assigned_drones:
                return f"No resources currently assigned to {project_id}.", {"project": project_id}
            names = ", ".join([p.get("name") for p in assigned_pilots]) or "None"
            ids = ", ".join([d.get("drone_id") for d in assigned_drones]) or "None"
            return (
                f"Resources assigned to {project_id}: pilots {names}; drones {ids}.",
                {"project": project_id, "pilots": assigned_pilots, "drones": assigned_drones},
            )

        if intent == "conflicts":
            conflicts = detect_conflicts(pilots, drones, missions)
            if not conflicts:
                return "No conflicts detected.", {"conflicts": []}
            return "Conflicts found: " + " ".join(conflicts), {"conflicts": conflicts}

        if intent == "urgent_reassignment":
            plan = urgent_reassignment_plan(missions, pilots, drones)
            return "Urgent reassignment plan: " + " ".join(plan), {"plan": plan}

        return "I didn't understand. Say 'help' for examples.", {}

    def _parse_kv(self, text: str) -> dict[str, str]:
        pairs = re.findall(r"(\w+)\s*=\s*([^,]+)", text)
        return {k.strip().lower(): v.strip() for k, v in pairs}

    def _next_id(self, prefix: str, existing: list[str]) -> str:
        nums = []
        for e in existing:
            m = re.search(rf"{prefix}(\d+)", str(e))
            if m:
                nums.append(int(m.group(1)))
        next_num = (max(nums) + 1) if nums else 1
        return f"{prefix}{next_num:03d}"

    def _add_pilot(self, text: str, pilots: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        data = self._parse_kv(text)
        if not data.get("name"):
            return "Usage: add pilot name=..., skills=..., certifications=..., location=..., status=..., available_from=YYYY-MM-DD", {}
        pilot_id = self._next_id("P", [p.get("pilot_id") for p in pilots])
        row = {
            "pilot_id": pilot_id,
            "name": data.get("name", ""),
            "skills": data.get("skills", ""),
            "certifications": data.get("certifications", ""),
            "location": data.get("location", ""),
            "status": data.get("status", "Available"),
            "current_assignment": data.get("current_assignment", "–"),
            "available_from": data.get("available_from", ""),
        }
        pilots.append(row)
        self.store.update_pilots(pilots)
        return f"Pilot {row['name']} added with id {pilot_id}.", {"pilot": row}

    def _add_drone(self, text: str, drones: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        data = self._parse_kv(text)
        if not data.get("model"):
            return "Usage: add drone model=..., capabilities=..., location=..., status=..., maintenance_due=YYYY-MM-DD", {}
        drone_id = self._next_id("D", [d.get("drone_id") for d in drones])
        row = {
            "drone_id": drone_id,
            "model": data.get("model", ""),
            "capabilities": data.get("capabilities", ""),
            "status": data.get("status", "Available"),
            "location": data.get("location", ""),
            "current_assignment": data.get("current_assignment", "–"),
            "maintenance_due": data.get("maintenance_due", ""),
        }
        drones.append(row)
        self.store.update_drones(drones)
        return f"Drone {row['drone_id']} added.", {"drone": row}

    def _add_mission(self, text: str, missions: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        data = self._parse_kv(text)
        if not data.get("client") or not data.get("location"):
            return "Usage: add mission client=..., location=..., required_skills=..., required_certs=..., start_date=YYYY-MM-DD, end_date=YYYY-MM-DD, priority=High/Standard/Urgent", {}
        project_id = self._next_id("PRJ", [m.get("project_id") for m in missions])
        row = {
            "project_id": project_id,
            "client": data.get("client", ""),
            "location": data.get("location", ""),
            "required_skills": data.get("required_skills", ""),
            "required_certs": data.get("required_certs", ""),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "priority": data.get("priority", "Standard"),
        }
        missions.append(row)
        self.store.update_missions(missions)
        return f"Mission {project_id} added.", {"mission": row}

    def _extract_project_id(self, text: str) -> str | None:
        m = re.search(r"(PRJ\d+)", text.upper())
        return m.group(1) if m else None

    def _extract_pilot_id(self, text: str) -> str | None:
        m = re.search(r"(P\d+)", text.upper())
        return m.group(1) if m else None

    def _extract_drone_id(self, text: str) -> str | None:
        m = re.search(r"(D\d+)", text.upper())
        return m.group(1) if m else None

    def _extract_status(self, text: str) -> str | None:
        for status in ["Available", "On Leave", "Unavailable", "Assigned", "Maintenance"]:
            if status.lower() in text.lower():
                return status
        return None

    def _extract_skill(self, text: str, pilots: list[dict[str, Any]]) -> str | None:
        skills = set()
        for p in pilots:
            for s in p.get("skills", "").split(","):
                skills.add(s.strip())
        for s in skills:
            if s and s.lower() in text.lower():
                return s
        return None

    def _extract_capability(self, text: str, drones: list[dict[str, Any]]) -> str | None:
        caps = set()
        for d in drones:
            for c in d.get("capabilities", "").split(","):
                caps.add(c.strip())
        for c in caps:
            if c and c.lower() in text.lower():
                return c
        return None

    def _extract_cert(self, text: str, pilots: list[dict[str, Any]]) -> str | None:
        certs = set()
        for p in pilots:
            for c in p.get("certifications", "").split(","):
                certs.add(c.strip())
        for c in certs:
            if c and c.lower() in text.lower():
                return c
        return None

    def _extract_location(self, text: str, items: list[dict[str, Any]]) -> str | None:
        locs = {i.get("location", "").strip() for i in items if i.get("location")}
        for loc in locs:
            if loc and loc.lower() in text.lower():
                return loc
        return None

    def _extract_pilot_by_name(self, text: str, pilots: list[dict[str, Any]]) -> dict[str, Any] | None:
        lower = text.lower()
        tokens = set(re.findall(r"[a-zA-Z]+", lower))
        exact_matches = []
        for p in pilots:
            name = str(p.get("name", "")).strip().lower()
            if not name:
                continue
            if name in tokens:
                exact_matches.append(p)
        if exact_matches:
            return exact_matches[0]
        # Fallback to full-name substring only if no token match exists.
        for p in pilots:
            name = str(p.get("name", "")).strip().lower()
            if name and name in lower:
                return p
        return None

    def _normalize_text(self, text: str) -> str:
        # Light typo normalization for common user input mistakes.
        replacements = {
            "availabble": "available",
            "avaiable": "available",
            "avialable": "available",
            "availble": "available",
            "avaible": "available",
            "detetcting": "detecting",
        }
        lowered = text.lower()
        for wrong, right in replacements.items():
            lowered = lowered.replace(wrong, right)
        return lowered

    def _fuzzy_correct(
        self,
        text: str,
        pilots: list[dict[str, Any]],
        drones: list[dict[str, Any]],
        missions: list[dict[str, Any]],
    ) -> str | None:
        import difflib

        tokens = re.findall(r"[A-Za-z]+", text)
        if not tokens:
            return None

        keywords = {
            "available",
            "pilot",
            "pilots",
            "drone",
            "drones",
            "assignment",
            "assigned",
            "assign",
            "conflict",
            "conflicts",
            "urgent",
            "reassign",
            "status",
            "location",
        }
        names = {str(p.get("name", "")).lower() for p in pilots if p.get("name")}
        locations = {str(p.get("location", "")).lower() for p in pilots if p.get("location")}
        locations |= {str(d.get("location", "")).lower() for d in drones if d.get("location")}
        projects = {str(m.get("project_id", "")).lower() for m in missions if m.get("project_id")}

        vocab = keywords | names | locations | projects
        if not vocab:
            return None

        corrected = text
        for tok in tokens:
            lower = tok.lower()
            if lower in vocab:
                continue
            match = difflib.get_close_matches(lower, vocab, n=1, cutoff=0.82)
            if match:
                corrected = re.sub(rf"\b{tok}\b", match[0], corrected, flags=re.IGNORECASE)
        return corrected

    def _format_assignment_issues(self, project_id: str, issues: list[str]) -> str:
        lines = [f"Could not assign resources for {project_id}."]
        for issue in issues:
            if "pilot" in issue.lower():
                lines.append("Pilot: No one is currently available who matches the required skills, certifications, and location.")
            elif "drone" in issue.lower():
                lines.append("Drone: No available drone matches the required capability and location.")
            else:
                lines.append(issue)
        lines.append("Try: make a pilot available, free a drone from maintenance, or change the mission requirements.")
        return " ".join(lines)

    def _classify_intent(
        self,
        lower: str,
        text: str,
        pilots: list[dict[str, Any]],
        drones: list[dict[str, Any]],
    ) -> str:
        tokens = set(re.findall(r"[a-zA-Z]+", lower))

        pilot_words = {"pilot", "pilots", "roster", "crew", "operator"}
        drone_words = {"drone", "drones", "fleet", "uav"}
        list_words = {"list", "show", "see", "find", "who", "all"}
        avail_words = {"available", "free", "idle"}
        phrase_any = "who all are" in lower or "who all" in lower

        has_pilot = bool(tokens & pilot_words) or self._mentions_pilot_name(text, pilots)
        has_drone = bool(tokens & drone_words)
        has_list = bool(tokens & list_words)
        has_avail = bool(tokens & avail_words)
        has_location = self._extract_location(text, pilots) or self._extract_location(text, drones)

        if has_pilot and has_avail:
            return "pilots_available"
        if has_drone and has_avail:
            return "drones_available"
        if (has_avail and not has_pilot and not has_drone and has_list) or (phrase_any and has_avail):
            return "any_available"
        if has_pilot and has_location and has_list:
            return "pilots_in_location"
        if has_drone and has_location and has_list:
            return "drones_in_location"
        if has_list and has_location and not has_drone:
            return "pilots_in_location"
        return "unknown"

    def _mentions_pilot_name(self, text: str, pilots: list[dict[str, Any]]) -> bool:
        lower = text.lower()
        for p in pilots:
            name = str(p.get("name", "")).strip().lower()
            if name and name in lower:
                return True
        return False
