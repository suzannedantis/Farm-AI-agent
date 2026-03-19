import os
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime

from database import (
    init_db, save_session, get_past_sessions, get_recurring_issues,
    register_farmer, verify_farmer,
)
from vision import diagnose_crop_image
from agent import run_agent

# ==========================================
# 0. Setup
# ==========================================
load_dotenv()
init_db()

api_key = st.secrets.get("GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")

# ==========================================
# 1. Page Config & CSS
# ==========================================
st.set_page_config(
    page_title="FarmAI — Crop Disease Agent",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@400;500&display=swap');

  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

  .stApp {
    background: linear-gradient(160deg, #0d1f0f 0%, #132a15 60%, #0a1a0c 100%);
    color: #e8ead4;
  }
  .farm-title {
    font-family: 'Playfair Display', serif;
    font-size: 3rem;
    color: #a8d5a2;
    letter-spacing: -1px;
    line-height: 1.1;
    margin-bottom: 0.2rem;
  }
  .farm-subtitle {
    font-size: 1rem;
    color: #7a9e78;
    margin-bottom: 2rem;
  }
  .card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(168,213,162,0.15);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
  }
  .card-accent { border-left: 3px solid #a8d5a2; }
  .pill {
    display: inline-block;
    background: rgba(168,213,162,0.12);
    border: 1px solid rgba(168,213,162,0.3);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.8rem;
    color: #a8d5a2;
    margin: 2px;
  }
  [data-testid="stSidebar"] {
    background: rgba(0,0,0,0.4) !important;
    border-right: 1px solid rgba(168,213,162,0.1);
  }
  .stButton > button {
    background: linear-gradient(135deg, #2d5a27, #3d7a35) !important;
    color: #e8ead4 !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.2s ease !important;
  }
  .stButton > button:hover {
    background: linear-gradient(135deg, #3d7a35, #4d9a45) !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(61,122,53,0.4) !important;
  }
  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea,
  .stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(168,213,162,0.2) !important;
    border-radius: 8px !important;
    color: #e8ead4 !important;
  }
  .stAlert { border-radius: 8px !important; }
  .history-item {
    background: rgba(255,255,255,0.03);
    border-left: 2px solid #5a8a57;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    border-radius: 0 6px 6px 0;
  }
  .history-date { font-size: 0.75rem; color: #7a9e78; }

  /* Auth form styling */
  .auth-box {
    max-width: 420px;
    margin: 4rem auto;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(168,213,162,0.2);
    border-radius: 16px;
    padding: 2.5rem;
  }
  .auth-title {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    color: #a8d5a2;
    text-align: center;
    margin-bottom: 0.25rem;
  }
  .auth-sub {
    text-align: center;
    color: #7a9e78;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
  }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Session State Init
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "farmer_id" not in st.session_state:
    st.session_state.farmer_id = ""
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"   # "login" or "register"

# ==========================================
# 3. Auth Gate — shown when not logged in
# ==========================================
if not st.session_state.authenticated:
    st.markdown("""
    <div class='auth-title'>🌿 FarmAI</div>
    <div class='auth-sub'>Autonomous Crop Disease Agent</div>
    """, unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        mode = st.radio(
            "Select action",
            ["Login", "Create Account"],
            horizontal=True,
            label_visibility="collapsed",
        )

        username = st.text_input("Username", placeholder="your_farm_id")
        password = st.text_input("Password", type="password", placeholder="••••••••")

        if mode == "Login":
            if st.button("Login →", use_container_width=True):
                if username and password:
                    ok, msg = verify_farmer(username, password)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.farmer_id = username.strip().lower()
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("Please fill in both fields.")
        else:
            if st.button("Create Account →", use_container_width=True):
                if username and password:
                    ok, msg = register_farmer(username, password)
                    if ok:
                        st.success(f"✅ {msg} You can now log in.")
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("Please fill in both fields.")

    st.stop()   # Nothing below renders until logged in

# ==========================================
# 4. Sidebar — shown only when authenticated
# ==========================================
farmer_id = st.session_state.farmer_id

with st.sidebar:
    st.markdown(f"### 👋 Welcome, `{farmer_id}`")

    language = st.selectbox(
        "Response Language",
        ["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Swahili", "Spanish", "French",
         "Tamil (தமிழ்)", "Telugu (తెలుగు)", "Kannada (ಕನ್ನಡ)"],
    )

    st.markdown("---")
    st.markdown("### 📜 Session History")

    past = get_past_sessions(farmer_id, limit=5)
    if past:
        for row in past:
            loc, crop, query, disease, conf, _, ts = row
            ts_fmt = ts[:10] if ts else "?"
            st.markdown(f"""
            <div class='history-item'>
              <div class='history-date'>📅 {ts_fmt} · {loc}</div>
              <div><b>{crop}</b> — {query[:50]}{'...' if len(query)>50 else ''}</div>
              <span class='pill'>{disease}</span>
              <span class='pill'>conf: {conf}</span>
            </div>
            """, unsafe_allow_html=True)

        recurring = get_recurring_issues(farmer_id)
        if recurring:
            st.markdown("---")
            st.markdown("### 🔁 Recurring Issues")
            for disease, count, last_seen in recurring:
                st.warning(
                    f"**{disease.upper()}** has occurred **{count}x**\n\n"
                    f"Last: {last_seen[:10] if last_seen else '?'}"
                )
    else:
        st.info("No past sessions yet.")

    st.markdown("---")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.farmer_id = ""
        st.rerun()

# ==========================================
# 5. Main Interface
# ==========================================
st.markdown("""
<div class='farm-title'>🌿 FarmAI</div>
<div class='farm-subtitle'>Autonomous Crop Disease Agent · Organic · Offline-capable · Multilingual</div>
""", unsafe_allow_html=True)

st.markdown("#### 🌾 Describe Your Crop Issue")

col1, col2 = st.columns(2)
with col1:
    location = st.text_input(
        "📍 Location (City / Region)",
        placeholder="e.g., Pune, Nairobi, Fresno",
    )
    crop_type = st.text_input(
        "🌱 Crop Type",
        placeholder="e.g., Tomato, Wheat, Maize",
    )
with col2:
    growing_stage = st.selectbox(
        "🌿 Growing Stage",
        ["Seedling", "Vegetative", "Flowering", "Fruiting / Grain Fill", "Harvest-Ready"],
    )
    uploaded_image = st.file_uploader(
        "📸 Upload Crop Photo",
        type=["jpg", "jpeg", "png", "webp"],
        help="The agent reads symptoms directly from your photo — no manual description needed",
    )

if uploaded_image:
    st.image(uploaded_image, caption="Uploaded crop photo", width=320)

# Optional manual override hint
extra_context = ""
with st.expander("✏️ Add extra context (optional)"):
    extra_context = st.text_area(
        "Any additional details the photo might not show",
        placeholder="e.g., problem started 3 days ago, only on the north side of the field",
        height=80,
    )

submit = st.button("🔬 Analyze & Generate Treatment Plan", use_container_width=True)

# ==========================================
# 6. Agent Execution
# ==========================================
if submit:
    if not api_key:
        st.error("❌ GROQ_API_KEY not set. Add it to your .env file.")
        st.stop()
    if not location:
        st.warning("⚠️ Please enter your location.")
        st.stop()
    if not uploaded_image:
        st.warning("⚠️ Please upload a crop photo — the agent reads symptoms from the image.")
        st.stop()

    # Step 1: Vision diagnosis (mandatory now)
    with st.spinner("👁️ Analyzing crop photo..."):
        vision_result = diagnose_crop_image(uploaded_image, crop_type, api_key)

    if vision_result["error"]:
        st.error(f"❌ Image analysis failed: {vision_result['error']}")
        st.stop()

    # Display visual diagnosis card
    st.markdown(f"""
    <div class='card card-accent'>
    <b>👁️ Visual Diagnosis</b><br><br>
    {vision_result['summary'].replace(chr(10), '<br>')}
    </div>
    """, unsafe_allow_html=True)

    # Build the agent query from vision output + any extra context
    issue = vision_result["query"]
    if extra_context.strip():
        issue += f" Additional context: {extra_context.strip()}"

    # Step 2: Fetch past session context
    past_rows = get_past_sessions(farmer_id, limit=3)
    past_issues_text = ""
    if past_rows:
        past_issues_text = "Previous issues reported by this farmer:\n"
        for row in past_rows:
            past_issues_text += f"- [{row[6][:10]}] {row[2]}: {row[1]} — Category: {row[3]}\n"

    # Step 3: Run the agent
    st.markdown("---")
    st.markdown("#### 🤖 Agent Execution Log")
    log_container = st.container()

    with st.spinner("Agent is working..."):
        try:
            result = run_agent(
                user_location=location,
                user_query=issue,
                crop_type=crop_type or "unspecified",
                growing_stage=growing_stage,
                language=language.split(" ")[0],
                image_diagnosis=vision_result["raw"],
                past_issues=past_issues_text,
                api_key=api_key,
                log_container=log_container,
            )
        except Exception as e:
            st.error(f"❌ Agent error: {e}")
            st.stop()

    # ==========================================
    # 7. Display Results
    # ==========================================
    st.markdown("---")
    st.markdown("### 📋 Your Treatment Plan")
    st.markdown(result["final_advice"])

    if result.get("escalate"):
        st.error("""
        🚨 **Expert Escalation Recommended**

        This issue appears potentially severe. We strongly recommend contacting your 
        **local agricultural extension officer** or calling your regional **Kisan helpline** 
        (India: 1800-180-1551 | Kenya: +254-20-2718870).
        """)

    conf = result.get("confidence", "medium")
    disease_cls = result.get("disease_class", "unknown")
    st.markdown(f"""
    <span class='pill'>🔬 Category: {disease_cls.upper()}</span>
    <span class='pill'>📊 Confidence: {conf.upper()}</span>
    <span class='pill'>🌍 {location}</span>
    <span class='pill'>🌱 {crop_type or 'Crop unspecified'}</span>
    """, unsafe_allow_html=True)

    with st.expander("🔍 Why this advice? (Explainability Panel)"):
        st.markdown(result.get("explanation", "No explanation data."))

    weather_raw = result.get("weather_raw", {})
    if weather_raw.get("risk_windows"):
        with st.expander("⚠️ 7-Day Weather Risk Windows"):
            for rw in weather_raw["risk_windows"]:
                for w in rw["warnings"]:
                    st.warning(f"**{rw['date']}:** {w}")

    save_session(
        farmer_id=farmer_id,
        location=location,
        crop_type=crop_type or "unspecified",
        query=issue,
        disease_class=result.get("disease_class", "unknown"),
        confidence=result.get("confidence", "medium"),
        advice=result.get("final_advice", ""),
    )
    st.success("✅ Session saved to your history.")

    report_text = f"""FARMAI CROP DISEASE REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Farmer ID: {farmer_id}
Location: {location}
Crop: {crop_type}
Stage: {growing_stage}
Visual Diagnosis: {vision_result['summary']}
Disease Category: {disease_cls}
Confidence: {conf}

--- TREATMENT PLAN ---

{result['final_advice']}

--- WEATHER SUMMARY ---

{result.get('weather_summary', '')}
"""
    st.download_button(
        label="📄 Download Report as TXT",
        data=report_text,
        file_name=f"farmai_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
    )