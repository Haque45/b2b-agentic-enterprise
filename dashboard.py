"""
GOD MODE RETRO DASHBOARD (dashboard.py).

Local command center for B2B Agentic Enterprise built with Streamlit & Pandas.
Aesthetic: Retro 8-bit, pixelated, "disco-techno" hacker vibe with dark background,
neon glowing borders, CRT scanlines, VT323 / Press Start 2P fonts.

Run command:
    streamlit run dashboard.py
"""

import sqlite3
import json
import os
import time
from datetime import datetime
import pandas as pd
import streamlit as st

from dotenv import load_dotenv
load_dotenv()

from database import get_db_connection, init_db, seed_database, DEFAULT_DB_PATH
from main import run_pipeline_cycle
from src.dispatcher import ResendEmailDispatcher

# Streamlit Page Config
st.set_page_config(
    page_title="GOD MODE // B2B Agentic Enterprise",
    page_icon="👾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Retro Disco-Techno CSS Injection
RETRO_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Share+Tech+Mono&family=VT323&display=swap');

/* Main Background & Fonts */
.stApp {
    background-color: #080811;
    background-image: radial-gradient(#181236 1px, transparent 0);
    background-size: 24px 24px;
    color: #00ffcc;
    font-family: 'Share Tech Mono', monospace;
}

/* CRT Scanlines Overlay */
.stApp::before {
    content: " ";
    display: block;
    position: fixed;
    top: 0; left: 0; bottom: 0; right: 0;
    background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.03), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.03));
    z-index: 9999;
    background-size: 100% 3px, 6px 100%;
    pointer-events: none;
}

/* Typography Headers */
h1, h2, h3, .pixel-font {
    font-family: 'Press Start 2P', cursive !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

h1 {
    color: #00f3ff;
    text-shadow: 0 0 10px #00f3ff, 0 0 20px #00f3ff, 0 0 30px #ff007f;
    font-size: 1.8rem !important;
    margin-bottom: 20px;
}

h2 {
    color: #ff007f;
    text-shadow: 0 0 8px #ff007f, 0 0 15px #00ff66;
    font-size: 1.2rem !important;
    border-bottom: 2px dashed #ff007f;
    padding-bottom: 8px;
}

h3 {
    color: #00ff66;
    font-size: 0.9rem !important;
}

/* Retro Glass Cards */
.retro-card {
    background: rgba(13, 10, 31, 0.85);
    border: 2px solid #00f3ff;
    box-shadow: 0 0 15px rgba(0, 243, 255, 0.4), inset 0 0 10px rgba(0, 243, 255, 0.2);
    border-radius: 4px;
    padding: 16px;
    margin-bottom: 20px;
    position: relative;
}

.retro-card-magenta {
    border-color: #ff007f;
    box-shadow: 0 0 15px rgba(255, 0, 127, 0.4), inset 0 0 10px rgba(255, 0, 127, 0.2);
}

.retro-card-lime {
    border-color: #00ff66;
    box-shadow: 0 0 15px rgba(0, 255, 102, 0.4), inset 0 0 10px rgba(0, 255, 102, 0.2);
}

.retro-card-gold {
    border-color: #ffcc00;
    box-shadow: 0 0 15px rgba(255, 204, 0, 0.4), inset 0 0 10px rgba(255, 204, 0, 0.2);
}

/* Metric Display Boxes */
.metric-box {
    text-align: center;
    background: #0d061f;
    border: 1px solid #ff007f;
    padding: 12px;
    border-radius: 4px;
}

.metric-val {
    font-family: 'VT323', monospace;
    font-size: 2.8rem;
    color: #00ff66;
    text-shadow: 0 0 8px #00ff66;
    line-height: 1;
}

.metric-lbl {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.8rem;
    color: #ffaa00;
    text-transform: uppercase;
}

/* Streamlit Buttons Retro Styling */
.stButton>button {
    background: linear-gradient(135deg, #ff007f 0%, #7928ca 100%);
    color: #ffffff !important;
    font-family: 'Press Start 2P', cursive !important;
    font-size: 0.65rem !important;
    border: 2px solid #00f3ff !important;
    box-shadow: 0 0 12px #ff007f, 0 0 20px #00f3ff !important;
    border-radius: 0px !important;
    padding: 12px 20px !important;
    text-transform: uppercase;
    transition: all 0.2s ease-in-out;
    width: 100%;
}

.stButton>button:hover {
    background: linear-gradient(135deg, #00f3ff 0%, #00ff66 100%) !important;
    color: #000000 !important;
    box-shadow: 0 0 20px #00ff66, 0 0 30px #00f3ff !important;
    transform: scale(1.02);
}

/* Dataframe & Tables */
.stDataFrame {
    border: 1px solid #00f3ff;
    box-shadow: 0 0 10px rgba(0, 243, 255, 0.3);
}

/* Badges */
.badge-status {
    padding: 4px 8px;
    border-radius: 2px;
    font-size: 0.75rem;
    font-weight: bold;
    text-transform: uppercase;
}
.badge-approved { background: #00ff66; color: #000; }
.badge-dispatched { background: #00f3ff; color: #000; }
.badge-replied { background: #ffaa00; color: #000; }
.badge-bounced { background: #ff0055; color: #fff; }
.badge-scouted { background: #7928ca; color: #fff; }
.badge-drafted { background: #0099ff; color: #fff; }

</style>
"""
st.markdown(RETRO_CSS, unsafe_allow_html=True)


def load_db_data(db_path: str = DEFAULT_DB_PATH):
    """Safely reads dataframes from pipeline.db."""
    init_db(db_path)
    conn = get_db_connection(db_path)

    leads_df = pd.read_sql_query("SELECT * FROM leads ORDER BY id DESC;", conn)
    directives_df = pd.read_sql_query("SELECT * FROM campaign_directives ORDER BY id DESC;", conn)
    replies_df = pd.read_sql_query("SELECT * FROM replies ORDER BY id DESC;", conn)
    analytics_df = pd.read_sql_query("SELECT * FROM analytics_logs ORDER BY id DESC;", conn)

    conn.close()
    return leads_df, directives_df, replies_df, analytics_df


# Header Section
st.markdown("<h1>👾 GOD MODE // COMMAND CENTER</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #00ff66; font-size: 1.1rem; margin-top: -15px;'>B2B AGENTIC ENTERPRISE HARDWARE INTELLIGENCE LAYER</p>", unsafe_allow_html=True)

# Load Database State
try:
    leads_df, directives_df, replies_df, analytics_df = load_db_data()
except Exception as e:
    st.error(f"Failed to load pipeline.db: {e}")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR CONTROLS & MANUAL OVERRIDES
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛 SYSTEM OVERRIDES", unsafe_allow_html=True)
    st.write("Manual Trigger Controls:")

    if st.button("🚀 RUN 6-AGENT PIPELINE"):
        with st.spinner("Executing 6-Agent Autonomous Pass..."):
            res = run_pipeline_cycle()
            st.success("Pipeline Pass Complete!")
            time.sleep(1)
            st.rerun()

    if st.button("⚡ DISPATCH APPROVED (RESEND)"):
        with st.spinner("Transmitting emails via Resend API..."):
            dispatcher = ResendEmailDispatcher()
            res = dispatcher.dispatch_pending_leads()
            st.success(f"Dispatched {res.get('dispatched_count', 0)} leads!")
            time.sleep(1)
            st.rerun()

    if st.button("🧹 SEED HISTORIC PIPELINE"):
        seed_database()
        st.success("Database Seeded Successfully!")
        st.rerun()

    if st.button("🔄 REFRESH SYSTEM MATRIX"):
        st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ ENVIRONMENT STATUS")

    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        st.markdown("<span style='color: #00ff66;'>✔ RESEND API ACTIVE</span>", unsafe_allow_html=True)
        st.caption(f"Key: `{resend_key[:6]}...{resend_key[-4:] if len(resend_key)>10 else ''}`")
    else:
        st.markdown("<span style='color: #ff0055;'>✖ RESEND API MOCK MODE</span>", unsafe_allow_html=True)

    imap_user = os.environ.get("IMAP_USER", "")
    if imap_user:
        st.markdown(f"<span style='color: #00f3ff;'>✔ IMAP GMAIL: B2B_Pipeline</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='color: #ffaa00;'>⚠ IMAP UNCONFIGURED</span>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<p style='font-size: 0.7rem; color: #888;'>UET Faisalabad Mechatronics Grounded Copywriting Engine</p>", unsafe_allow_html=True)


# ---------------------------------------------------------
# SECTION 1: SYSTEM STATUS ARRAY (KPI MATRIX & CEO DIRECTIVE)
# ---------------------------------------------------------
col_left, col_right = st.columns([1.4, 1.0])

with col_left:
    st.markdown("## 🧠 CEO STRATEGY DIRECTIVE", unsafe_allow_html=True)
    if not directives_df.empty:
        active_dir = directives_df[directives_df["status"] == "active"]
        if active_dir.empty:
            active_dir = directives_df.iloc[[0]]
        
        row = active_dir.iloc[0]
        st.markdown(f"""
        <div class="retro-card retro-card-gold">
            <h3 style="color: #ffcc00; margin-top:0;">FOCUS LANE: {row.get('focus_service_lane', 'SolidWorks DFM')} ({row.get('allocation_percentage', 80)}% ALLOCATION)</h3>
            <p style="font-size: 1.1rem; color: #ffffff;"><b>DIRECTIVE:</b> {row.get('directive_text', 'N/A')}</p>
            <p style="font-size: 0.9rem; color: #00ff66;"><b>CEO REASONING:</b> {row.get('reasoning', 'N/A')}</p>
            <p style="font-size: 0.8rem; color: #00f3ff;"><b>TARGET SECTORS:</b> {row.get('target_sectors', 'N/A')}</p>
            <p style="font-size: 0.75rem; color: #888;">TIMESTAMP: {row.get('created_at', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No active CEO Directive recorded.")

with col_right:
    st.markdown("## 📊 PIPELINE KPI MATRIX", unsafe_allow_html=True)

    total_leads = len(leads_df)
    scouted_cnt = len(leads_df[leads_df["status"] == "scouted"])
    drafted_cnt = len(leads_df[leads_df["status"] == "drafted"])
    approved_cnt = len(leads_df[leads_df["status"] == "approved_for_dispatch"])
    dispatched_cnt = len(leads_df[leads_df["status"].isin(["dispatched", "sent"])])
    replied_cnt = len(leads_df[leads_df["status"] == "replied"])
    bounced_cnt = len(leads_df[leads_df["status"] == "bounced"])

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f"""<div class="metric-box"><div class="metric-val">{total_leads}</div><div class="metric-lbl">TOTAL LEADS</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="metric-box"><div class="metric-val">{approved_cnt}</div><div class="metric-lbl">APPROVED QUEUE</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="metric-box"><div class="metric-val">{dispatched_cnt}</div><div class="metric-lbl">DISPATCHED</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    k4, k5, k6 = st.columns(3)
    with k4:
        st.markdown(f"""<div class="metric-box"><div class="metric-val">{scouted_cnt}</div><div class="metric-lbl">SCOUTED</div></div>""", unsafe_allow_html=True)
    with k5:
        st.markdown(f"""<div class="metric-box"><div class="metric-val">{replied_cnt}</div><div class="metric-lbl">REPLIED</div></div>""", unsafe_allow_html=True)
    with k6:
        st.markdown(f"""<div class="metric-box"><div class="metric-val" style="color:#ff0055;">{bounced_cnt}</div><div class="metric-lbl">BOUNCED</div></div>""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------
# SECTION 2: THE PIPELINE MATRIX (MASTER LEADS TABLE)
# ---------------------------------------------------------
st.markdown("## 🔍 THE PIPELINE MATRIX", unsafe_allow_html=True)

filter_col1, filter_col2 = st.columns([1, 2])
with filter_col1:
    status_filter = st.selectbox(
        "FILTER BY PIPELINE STATUS:",
        ["ALL", "approved_for_dispatch", "dispatched", "replied", "bounced", "drafted", "scouted"]
    )
with filter_col2:
    search_query = st.text_input("SEARCH COMPANY OR URL:", "")

display_df = leads_df.copy()
if status_filter != "ALL":
    if status_filter == "dispatched":
        display_df = display_df[display_df["status"].isin(["dispatched", "sent"])]
    else:
        display_df = display_df[display_df["status"] == status_filter]

if search_query:
    display_df = display_df[
        display_df["company_name"].str.contains(search_query, case=False, na=False) |
        display_df["url"].str.contains(search_query, case=False, na=False)
    ]

if not display_df.empty:
    cols_to_show = ["id", "company_name", "status", "service_lane", "decision_maker", "subject", "updated_at"]
    st.dataframe(
        display_df[cols_to_show],
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "company_name": "Target Company",
            "status": "Pipeline Status",
            "service_lane": "Service Lane",
            "decision_maker": "Decision Maker",
            "subject": "Pitch Subject",
            "updated_at": "Last Updated"
        }
    )
else:
    st.info("No leads match the selected filter.")

st.markdown("---")

# ---------------------------------------------------------
# SECTION 3: DRAFT INSPECTOR (PRE-DISPATCH COPY READER)
# ---------------------------------------------------------
st.markdown("## 📜 DRAFT INSPECTOR & GROUNDING PROOF", unsafe_allow_html=True)
st.caption("Inspect generated mechatronics pitches and compliance notes before or after dispatch.")

if not leads_df.empty:
    lead_options = {
        f"ID #{row['id']} - {row['company_name']} [{row['status']}]": row["id"]
        for _, row in leads_df.iterrows()
    }
    selected_option = st.selectbox("SELECT A LEAD TO INSPECT:", list(lead_options.keys()))
    selected_id = lead_options[selected_option]

    selected_lead = leads_df[leads_df["id"] == selected_id].iloc[0]

    insp_c1, insp_c2 = st.columns([1.2, 1.0])

    with insp_c1:
        st.markdown(f"""
        <div class="retro-card retro-card-lime">
            <h3 style="color: #00ff66;">TARGET: {selected_lead['company_name']}</h3>
            <p><b>URL:</b> <a href="{selected_lead['url']}" target="_blank" style="color:#00f3ff;">{selected_lead['url']}</a></p>
            <p><b>DECISION MAKER:</b> {selected_lead.get('decision_maker', 'Engineering Manager')}</p>
            <p><b>SERVICE LANE:</b> {selected_lead.get('service_lane', 'SolidWorks DFM')}</p>
            <p><b>SUBJECT:</b> <span style="color:#ffcc00;">{selected_lead.get('subject', 'N/A')}</span></p>
            <hr style="border: 1px dashed #00ff66;">
            <p><b>EMAIL BODY PITCH:</b></p>
            <div style="background: #000; padding: 12px; border-left: 3px solid #00ff66; font-family: monospace; white-space: pre-wrap; color: #00ff66;">{selected_lead.get('email_body', 'No draft generated yet.')}</div>
        </div>
        """, unsafe_allow_html=True)

    with insp_c2:
        st.markdown(f"""
        <div class="retro-card retro-card-magenta">
            <h3 style="color: #ff007f;">COMPLIANCE & GROUNDING AUDIT</h3>
            <p><b>STATUS:</b> <span class="badge-status badge-{selected_lead['status']}">{selected_lead['status']}</span></p>
            <p><b>WORD COUNT:</b> {len((selected_lead.get('email_body') or '').split())} words (Max limit: 75)</p>
            <p><b>FOUNDER GROUNDING:</b> UET Faisalabad Mechatronics Engineering (SolidWorks DFM, ROS 2, TinyML, Pneumatics)</p>
            <p><b>COMPLIANCE NOTES:</b></p>
            <div style="background: #12031a; padding: 10px; border: 1px solid #ff007f; color: #ff99dd;">{selected_lead.get('compliance_notes', 'Passed standard compliance checks.')}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------
# SECTION 4: HISTORY & AUDIT LOGS
# ---------------------------------------------------------
st.markdown("## 📜 AUDIT TRAIL & SENTIMENT LOGS", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["INBOX REPLIES & SENTIMENT", "CEO ANALYTICS HISTORY"])

with tab1:
    if not replies_df.empty:
        st.dataframe(
            replies_df,
            use_container_width=True,
            column_config={
                "id": "Reply ID",
                "sender_email": "Sender Email",
                "subject": "Subject",
                "body": "Reply Body",
                "sentiment": "Sentiment",
                "service_lane": "Service Lane",
                "received_at": "Received At"
            }
        )
    else:
        st.info("No replies recorded yet.")

with tab2:
    if not analytics_df.empty:
        for _, a_row in analytics_df.head(5).iterrows():
            st.markdown(f"**Analytics Snapshot #{a_row['id']}** ({a_row['created_at']})")
            try:
                parsed_json = json.loads(a_row["summary_json"])
                st.json(parsed_json)
            except Exception:
                st.code(a_row["summary_json"])
    else:
        st.info("No analytics logs recorded yet.")
