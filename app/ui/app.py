"""
SetuHaul Logistics — Driver Chat & Operations Portal
Interactive UI providing Driver Chat and Operations Review Queues.
Run with: streamlit run app/ui/app.py
"""

import streamlit as st
import json
from datetime import datetime

from app.repositories.db import DatabaseRepository
from app.services.feasibility import FeasibilityService
from app.services.booking import BookingService
from app.agent.agent import SetuHaulAgent
from app.tools.schemas import ConfirmAppointmentInput, ResultCode

st.set_page_config(
    page_title="SetuHaul Logistics Portal",
    page_icon="🚚",
    layout="wide"
)

# Initialize services in session state
if "repo" not in st.session_state:
    st.session_state.repo = DatabaseRepository()
    st.session_state.feasibility = FeasibilityService(st.session_state.repo)
    st.session_state.booking = BookingService(st.session_state.repo, st.session_state.feasibility)
    st.session_state.agent = SetuHaulAgent()

repo = st.session_state.repo
feasibility = st.session_state.feasibility
booking = st.session_state.booking
agent = st.session_state.agent

st.title("🚚 SetuHaul Logistics — Exception Resolution Service")
st.caption("FDE Academy Mini Project 2 | Operational Snapshot: 4 August 2026, Asia/Kolkata (+05:30)")

tabs = st.tabs(["💬 Driver Chat Portal", "📋 Operations Review Queue", "📊 Live Facility Status"])

# ==============================================================================
# TAB 1: DRIVER CHAT PORTAL
# ==============================================================================
with tabs[0]:
    st.subheader("Driver Exception Resolution Assistant")

    col_side, col_chat = st.columns([1, 2])

    with col_side:
        st.markdown("### 🪪 Driver Session")
        driver_options = {
            "DRV006": "DRV006 - Manoj Sharma (SHP1006 - Standard)",
            "DRV004": "DRV004 - Sandeep Meena (Ambiguous: SHP1004 & SHP1020)",
            "DRV015": "DRV015 - Mohammed Salim (SHP1015 - Reefer Load)",
            "DRV007": "DRV007 - Nitin Patil (SHP1016 - Heavy 31T Load)",
            "DRV012": "DRV012 - Arjun Das (SHP1012 - Standard)",
            "DRV003": "DRV003 - Mukesh Yadav (SHP1003 - Early in Yard)"
        }
        selected_driver_id = st.selectbox("Select Driver Identity:", list(driver_options.keys()), format_func=lambda x: driver_options[x])
        thread_id = f"THR-{selected_driver_id}"

        # Display Driver Info
        drv_info = repo.fetch_one("SELECT * FROM drivers WHERE driver_id = ?;", (selected_driver_id,))
        if drv_info:
            st.info(f"**Driver:** {drv_info['driver_name']}\n\n**Phone:** {drv_info['phone']}\n\n**Carrier:** {drv_info['carrier_id']}")

        # Clear conversation button
        if st.button("🔄 Reset Conversation Thread"):
            st.session_state[f"messages_{thread_id}"] = []
            agent.clear_thread(thread_id)
            st.rerun()

    with col_chat:
        st.markdown("### 📱 Active Conversation")

        if f"messages_{thread_id}" not in st.session_state:
            st.session_state[f"messages_{thread_id}"] = [
                {"role": "assistant", "content": f"Hello! SetuHaul Logistics Inbound Assistant here. How can I help you with your delivery today?"}
            ]

        # Display conversation history
        for msg in st.session_state[f"messages_{thread_id}"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Quick action suggestions
        st.markdown("**Quick Prompts:**")
        qp_cols = st.columns(3)
        quick_msg = None
        if qp_cols[0].button("Delay: Traffic (~11:20 AM)"):
            quick_msg = "Traffic after Shahpura. Reaching around 11:20. Any slot after 12?"
        if qp_cols[1].button("Late by 45 Minutes"):
            quick_msg = "I will be late by 45 minutes."
        if qp_cols[2].button("Reefer ETA 6:30 PM"):
            quick_msg = "Evening traffic. ETA 6:30. Can the reefer unload tonight?"

        user_input = st.chat_input("Type your message here (e.g. 'Stuck in traffic, new ETA 11:30 AM')...")
        prompt_to_send = quick_msg or user_input

        if prompt_to_send:
            # Display user message
            st.session_state[f"messages_{thread_id}"].append({"role": "user", "content": prompt_to_send})
            with st.chat_message("user"):
                st.markdown(prompt_to_send)

            # Invoke Agent
            with st.spinner("Analyzing operational feasibility..."):
                agent_res = agent.chat(
                    user_message=prompt_to_send,
                    thread_id=thread_id,
                    driver_id=selected_driver_id
                )

            agent_response_text = agent_res["response"]
            st.session_state[f"messages_{thread_id}"].append({"role": "assistant", "content": agent_response_text})
            with st.chat_message("assistant"):
                st.markdown(agent_response_text)

            # If tool calls were made, show an expander with the trace
            if agent_res.get("tool_calls"):
                with st.expander("🔍 Operational Tool Execution Trace"):
                    st.json(agent_res["tool_calls"])


# ==============================================================================
# TAB 2: OPERATIONS REVIEW QUEUE
# ==============================================================================
with tabs[1]:
    st.subheader("Warehouse Operations Review Queue")
    st.caption("Exceptions requiring human manager approval, dock reassignment, or supervisor intervention.")

    escalations = repo.fetch_all("""
        SELECT 
            e.exception_id, e.shipment_id, e.driver_id, e.thread_id,
            e.exception_type, e.reported_at, e.severity_code,
            e.exception_status, e.description,
            d.driver_name, d.phone AS driver_phone,
            s.order_reference, s.destination_facility_id, s.priority_code
        FROM driver_exceptions e
        LEFT JOIN drivers d ON d.driver_id = e.driver_id
        LEFT JOIN shipments s ON s.shipment_id = e.shipment_id
        WHERE e.exception_status IN ('OPEN','ESCALATED','NEEDS_INFORMATION','WAITING_CONFIRMATION')
        ORDER BY e.reported_at DESC;
    """)

    st.metric("Total Active Exception Tickets", len(escalations))

    for exc in escalations:
        with st.container(border=True):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.markdown(f"#### Ticket: `{exc['exception_id']}` | Severity: **{exc['severity_code']}** | Status: `{exc['exception_status']}`")
                st.markdown(
                    f"**Shipment:** `{exc['shipment_id'] or 'N/A'}` (`{exc['order_reference'] or 'N/A'}`) | "
                    f"**Priority:** `{exc['priority_code'] or 'NORMAL'}` | "
                    f"**Facility:** `{exc['destination_facility_id'] or 'N/A'}`"
                )
                st.markdown(f"**Driver:** {exc['driver_name']} ({exc['driver_phone']})")
                st.info(f"**Disruption Description:** {exc['description']}")
                st.caption(f"Reported at: {exc['reported_at']}")

            with col_action:
                st.markdown("##### Supervisor Action")
                resolution_comment = st.text_input("Resolution Note:", key=f"res_{exc['exception_id']}", value="Approved manual override")
                if st.button("✅ Resolve & Close Ticket", key=f"btn_{exc['exception_id']}"):
                    repo.execute_write("""
                        UPDATE driver_exceptions
                        SET exception_status = 'RESOLVED',
                            description = description || ' | Supervisor: ' || ?
                        WHERE exception_id = ?;
                    """, (resolution_comment, exc['exception_id']))
                    st.success(f"Ticket {exc['exception_id']} resolved!")
                    st.rerun()


# ==============================================================================
# TAB 3: LIVE FACILITY STATUS
# ==============================================================================
with tabs[2]:
    st.subheader("Live Operational Facility Dashboard")

    fac_cols = st.columns(2)
    with fac_cols[0]:
        st.markdown("### 🏢 Jaipur Distribution Centre (`FAC-JAI-01`)")
        st.markdown("**Operating Hours:** 06:00 to 22:00 | **Curfew (Last Start):** 21:00")
        st.markdown("**Docks:** D1-D4 (Standard), D5 (Reefer), D6 (Heavy)")

    with fac_cols[1]:
        st.markdown("### 🏢 Gurugram Cross-Dock (`FAC-GGN-01`)")
        st.markdown("**Operating Hours:** 07:00 to 21:00")
        st.markdown("**Docks:** D1-D2 (Standard), D3 (Reefer)")

    st.markdown("---")
    st.markdown("### 🚛 Trucks Currently Waiting in Yard (`v_current_facility_queue`)")
    queue_rows = repo.fetch_all("SELECT * FROM v_current_facility_queue ORDER BY queue_position;")
    if queue_rows:
        st.dataframe(queue_rows, use_container_width=True)
    else:
        st.write("No trucks currently queued in the yard.")

    st.markdown("### ⚠️ Active Dock Disruption Events")
    events = repo.fetch_all("SELECT * FROM dock_status_events;")
    st.dataframe(events, use_container_width=True)
