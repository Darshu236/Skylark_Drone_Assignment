import streamlit as st

from src.agent import DroneOpsAgent
from src.logic import detect_conflicts, recommend_assignment
from src.storage import DataStore


st.set_page_config(page_title="Drone Ops Coordinator", page_icon="DR", layout="wide")

agent = DroneOpsAgent()
store = DataStore()

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap');
html, body, [class*="css"]  { font-family: 'Manrope', sans-serif; }
.stApp {
  background: radial-gradient(1200px 700px at 10% -10%, #fff3e6 0%, #f7f2ed 45%, #eef4f7 100%);
}
h1, h2, h3 { color: #1f2a33; }
.card {
  background: #ffffff;
  border: 1px solid #e6e1dc;
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow: 0 6px 16px rgba(32, 34, 37, 0.08);
}
.pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  background: #f1e6d9;
  color: #8a5a2b;
  font-size: 12px;
  font-weight: 600;
}
.accent { color: #b23a48; font-weight: 700; }
div[data-testid="stExpander"] > details {
  background: #ffffff;
  border: 1px solid #e6e1dc;
  border-radius: 12px;
  padding: 6px 10px;
}
div[data-testid="stExpander"] summary {
  font-size: 13px;
}
.small-text { font-size: 12px; color: #5b5b5b; }
input, textarea {
  background: #ffffff !important;
  border: 1px solid #d9cfc6 !important;
  border-radius: 8px !important;
}
label { color: #1f2a33 !important; }
</style>
    """,
    unsafe_allow_html=True,
)

st.title("Drone Operations Coordinator")

if "messages" not in st.session_state:
    st.session_state.messages = []


def _format_data(data: dict) -> str:
    if not data:
        return ""
    lines = []
    if data.get("project"):
        lines.append(f"Project: {data.get('project')}")
    if data.get("pilot"):
        p = data.get("pilot", {})
        lines.append(f"Pilot: {p.get('name')} ({p.get('pilot_id')})")
    if data.get("drone"):
        d = data.get("drone", {})
        lines.append(f"Drone: {d.get('drone_id')} ({d.get('model')})")
    if data.get("issues"):
        lines.append("Issues:")
        for i in data.get("issues", []):
            lines.append(f"- {i}")
    if data.get("pilots"):
        names = ", ".join([p.get("name") for p in data.get("pilots", [])])
        if names:
            lines.append(f"Pilots: {names}")
    if data.get("drones"):
        ids = ", ".join([d.get("drone_id") for d in data.get("drones", [])])
        if ids:
            lines.append(f"Drones: {ids}")
    if data.get("conflicts"):
        lines.append("Conflicts:")
        for c in data.get("conflicts", []):
            lines.append(f"- {c}")
    if data.get("plan"):
        lines.append("Plan:")
        for p in data.get("plan", []):
            lines.append(f"- {p}")
    return "\n".join(lines) if lines else "Details available."


pilots = store.get_pilots()
drones = store.get_drones()
missions = store.get_missions()

available_pilots = [p for p in pilots if str(p.get("status", "")).lower() == "available"]
available_drones = [d for d in drones if str(d.get("status", "")).lower() == "available"]
active_pilots = [p for p in pilots if str(p.get("status", "")).lower() == "assigned"]
active_drones = [d for d in drones if str(d.get("status", "")).lower() == "assigned"]

col_left, col_center, col_right = st.columns([0.9, 1.5, 1.1])

with col_left:
    st.subheader("Availability")
    st.markdown(
        f"""
<div class="card">
  <div style="display:flex; gap:14px; flex-wrap:wrap;">
    <div><div class="accent">{len(available_pilots)}</div><div>Available Pilots</div></div>
    <div><div class="accent">{len(available_drones)}</div><div>Available Drones</div></div>
    <div><div class="accent">{len(active_pilots)}</div><div>Active Pilots</div></div>
    <div><div class="accent">{len(active_drones)}</div><div>Active Drones</div></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Show lists", expanded=False):
        st.markdown("**Available Pilots**")
        for p in available_pilots:
            st.write(f"{p.get('name')} ({p.get('location')})")
        st.markdown("**Available Drones**")
        for d in available_drones:
            st.write(f"{d.get('drone_id')} ({d.get('location')})")
        st.markdown("**Active Assignments**")
        for p in active_pilots:
            st.write(f"{p.get('name')} -> {p.get('current_assignment')}")
        for d in active_drones:
            st.write(f"{d.get('drone_id')} -> {d.get('current_assignment')}")

with col_center:
    st.subheader("Operations")
    tabs = st.tabs(["Mission Center", "Conflict Alerts", "Pilots", "Drones", "Missions", "Add Data"])

    with tabs[0]:
        mission_ids = [m.get("project_id") for m in missions]
        selected = st.selectbox("Select a mission", mission_ids)
        mission = next((m for m in missions if m.get("project_id") == selected), None)
        if mission:
            st.markdown("**Mission Details**")
            st.write(f"Project: {mission.get('project_id')}")
            st.write(f"Client: {mission.get('client')}")
            st.write(f"Location: {mission.get('location')}")
            st.write(f"Required Skills: {mission.get('required_skills')}")
            st.write(f"Required Certifications: {mission.get('required_certs')}")
            st.write(f"Dates: {mission.get('start_date')} to {mission.get('end_date')}")
            st.write(f"Priority: {mission.get('priority')}")
            rec = recommend_assignment(selected, pilots, drones, missions)
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Recommend assignment"):
                    if rec.issues:
                        st.error(" ".join(rec.issues))
                    else:
                        st.success(
                            f"Recommended pilot {rec.pilot.get('name')} and drone {rec.drone.get('drone_id')}."
                        )
            with col_b:
                if st.button("Assign now"):
                    reply, data = agent.handle(f"assign {selected}")
                    st.info(reply)
                    if data:
                        st.write(_format_data(data))

    with tabs[1]:
        conflicts = detect_conflicts(pilots, drones, missions)
        if conflicts:
            for c in conflicts:
                st.warning(c)
        else:
            st.success("No conflicts detected.")

    with tabs[2]:
        st.dataframe(pilots, use_container_width=True, height=220)

    with tabs[3]:
        st.dataframe(drones, use_container_width=True, height=220)

    with tabs[4]:
        st.dataframe(missions, use_container_width=True, height=220)

    with tabs[5]:
        form_tab_pilot, form_tab_drone, form_tab_mission = st.tabs(
            ["Add Pilot", "Add Drone", "Add Mission"]
        )

        with form_tab_pilot:
            with st.form("add_pilot_form", clear_on_submit=True):
                name = st.text_input("Name")
                skills = st.text_input("Skills (comma-separated)")
                certs = st.text_input("Certifications (comma-separated)")
                location = st.text_input("Location")
                status = st.selectbox("Status", ["Available", "On Leave", "Unavailable", "Assigned"])
                available_from = st.date_input("Available From")
                submit = st.form_submit_button("Add Pilot")
                if submit:
                    msg = (
                        f"add pilot name={name}, skills={skills}, certifications={certs}, "
                        f"location={location}, status={status}, available_from={available_from}"
                    )
                    reply, data = agent.handle(msg)
                    st.success(reply)
                    if data:
                        st.write(_format_data(data))

        with form_tab_drone:
            with st.form("add_drone_form", clear_on_submit=True):
                model = st.text_input("Model")
                capabilities = st.text_input("Capabilities (comma-separated)")
                location = st.text_input("Location")
                status = st.selectbox("Status", ["Available", "Maintenance", "Assigned"])
                maintenance_due = st.date_input("Maintenance Due")
                submit = st.form_submit_button("Add Drone")
                if submit:
                    msg = (
                        f"add drone model={model}, capabilities={capabilities}, "
                        f"location={location}, status={status}, maintenance_due={maintenance_due}"
                    )
                    reply, data = agent.handle(msg)
                    st.success(reply)
                    if data:
                        st.write(_format_data(data))

        with form_tab_mission:
            with st.form("add_mission_form", clear_on_submit=True):
                client = st.text_input("Client")
                location = st.text_input("Location")
                required_skills = st.text_input("Required Skills")
                required_certs = st.text_input("Required Certifications")
                start_date = st.date_input("Start Date")
                end_date = st.date_input("End Date")
                priority = st.selectbox("Priority", ["Urgent", "High", "Standard", "Low"])
                submit = st.form_submit_button("Add Mission")
                if submit:
                    msg = (
                        f"add mission client={client}, location={location}, "
                        f"required_skills={required_skills}, required_certs={required_certs}, "
                        f"start_date={start_date}, end_date={end_date}, priority={priority}"
                    )
                    reply, data = agent.handle(msg)
                    st.success(reply)
                    if data:
                        st.write(_format_data(data))

with col_right:
    st.subheader("Chat")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("data"):
                with st.expander("Show details"):
                    st.write(_format_data(msg["data"]))

    prompt = st.chat_input("Ask the coordinator")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        reply, data = agent.handle(prompt)
        st.session_state.messages.append(
            {"role": "assistant", "content": reply, "data": data}
        )
        st.rerun()
