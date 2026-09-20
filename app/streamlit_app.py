"""
League of Legends RAG Knowledge Bot — Google Gemini Style Web Interface
File: app/streamlit_app.py

Modern conversational UI inspired by Google Gemini:
- Dynamic Theme: Gemini Dark (#131314) and Gemini Light (#ffffff)
- Gemini Hero Greeting and 4 Quick Prompt Cards
- Clean Chat Message Stream with Gemini Sparkle Avatar
- Integrated RAG Sources and Reasoning Accordion (Neo4j Graph + FAISS LoRA)
- Sticky Floating Pill Chat Input Bar
- PostgreSQL Chat History Persistence: Sessions, Message History and Multi-turn Memory
"""

import base64
import os
import sys
import time
import uuid
from pathlib import Path

import streamlit as st

# Ensure project root and src/ are in sys.path
app_dir = Path(__file__).resolve().parent
project_root = app_dir.parent
src_dir = project_root / "src"

for p in [str(project_root), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chatbot.history_db import get_history_db

# Streamlit Page Configuration
st.set_page_config(
    page_title = "League of Legends RAG Assistant",
    layout = "wide",
    initial_sidebar_state = "expanded",
)

# Database and Bot Singletons
@st.cache_resource(show_spinner=False)
def load_db():
    """Load PostgreSQL history database manager."""
    return get_history_db()


@st.cache_resource(show_spinner=False)
def load_bot():
    """Load singleton bot instance with full RAG Pipeline and stores."""
    from chatbot.bot import get_bot
    return get_bot()


db = load_db()
db_online = db.is_available()

try:
    with st.spinner("Connecting to League of Legends Knowledge Engine (Graph + Vector)..."):
        bot = load_bot()
except Exception as e:
    st.error(f"Bot Initialization Error: {e}")
    bot = None

# Session State Initialization
if "theme" not in st.session_state:
    st.session_state.theme = "light"

if "current_session_id" not in st.session_state:
    # Fresh conversation initialized in-memory (saved to DB upon first user query)
    st.session_state.current_session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# Synchronize bot multi-turn conversation memory with current session
if bot and st.session_state.messages:
    bot.conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]


def switch_session(target_session_id):
    """Switch active session and load its history."""
    st.session_state.current_session_id = target_session_id
    if db_online:
        msgs = db.get_session_messages(target_session_id)
        st.session_state.messages = msgs
        if bot:
            bot.conversation_history = [
                {"role": m["role"], "content": m["content"]}
                for m in msgs
            ]
    else:
        st.session_state.messages = []
        if bot:
            bot.reset_conversation()
    st.rerun()


def create_new_chat():
    """Create a new chat session."""
    st.session_state.current_session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.pending_prompt = None
    if bot:
        bot.reset_conversation()
    st.rerun()


def delete_chat(session_id_to_delete):
    """Delete a session and handle switching."""
    if db_online:
        db.delete_session(session_id_to_delete)
    if st.session_state.current_session_id == session_id_to_delete:
        sessions = db.list_sessions() if db_online else []
        if sessions:
            switch_session(sessions[0]["session_id"])
        else:
            create_new_chat()
    else:
        st.rerun()


@st.cache_data
def get_background_base64():
    """Load background image 1409911.jpg and return as base64 data URI."""
    candidates = [
        project_root / "1409911.jpg",
        app_dir / "1409911.jpg",
        Path("1409911.jpg"),
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/jpeg;base64,{encoded}"
            except Exception:
                pass
    return ""


# Void Glassmorphism Theme CSS (Subtle Background with 1409911.jpg)
def get_custom_css():
    bg_uri = get_background_base64()
    if bg_uri:
        bg_style = f'background: linear-gradient(rgba(11, 9, 21, 0.85), rgba(13, 10, 25, 0.90)), url("{bg_uri}") center/cover no-repeat fixed !important;'
    else:
        bg_style = "background-color: #0d0a19 !important;"

    text_primary = "#f1f5f9"
    text_secondary = "#94a3b8"
    sidebar_bg = "rgba(13, 10, 24, 0.82)"
    sidebar_border = "rgba(168, 85, 247, 0.18)"
    card_bg = "rgba(22, 18, 38, 0.68)"
    card_border = "rgba(168, 85, 247, 0.22)"
    card_hover = "rgba(36, 28, 62, 0.85)"
    user_bubble_bg = "rgba(44, 32, 74, 0.75)"
    user_bubble_border = "rgba(192, 132, 252, 0.3)"
    input_bg = "rgba(20, 16, 36, 0.82)"
    input_border = "rgba(168, 85, 247, 0.35)"
    input_focus = "#c084fc"
    session_active_bg = "rgba(168, 85, 247, 0.22)"

    return f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

        /* App Base Background and Canvas */
        .stApp {{
            {bg_style}
            color: {text_primary} !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        }}

        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}

        div[data-testid="stBottom"],
        div[data-testid="stBottom"] > div {{
            background: transparent !important;
        }}

        /* Center conversation layout */
        .main .block-container {{
            max-width: 820px !important;
            padding-top: 1.5rem !important;
            padding-bottom: 5.5rem !important;
            margin: 0 auto !important;
        }}

        /* Typography */
        h1, h2, h3, h4 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            letter-spacing: -0.02em;
            color: {text_primary} !important;
        }}

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
            backdrop-filter: blur(16px) !important;
            -webkit-backdrop-filter: blur(16px) !important;
            border-right: 1px solid {sidebar_border} !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: {text_primary} !important;
        }}

        /* Sidebar Session Buttons */
        section[data-testid="stSidebar"] div.stButton > button,
        section[data-testid="stSidebar"] div[data-testid="stColumn"] div.stButton > button,
        section[data-testid="stSidebar"] button {{
            background-color: rgba(22, 18, 38, 0.75) !important;
            color: #ffffff !important;
            border: 1px solid rgba(168, 85, 247, 0.25) !important;
            border-radius: 12px !important;
            font-size: 0.88rem !important;
            padding: 8px 12px !important;
            transition: all 0.2s ease !important;
        }}
        section[data-testid="stSidebar"] button * {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }}
        section[data-testid="stSidebar"] button:hover {{
            background-color: rgba(45, 32, 75, 0.95) !important;
            border-color: {input_focus} !important;
        }}
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {{
            background-color: {session_active_bg} !important;
            border-color: {input_focus} !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }}

        /* Gemini + New Chat Button */
        .gemini-new-chat-btn button {{
            background-color: rgba(32, 25, 54, 0.8) !important;
            color: {text_primary} !important;
            border: 1px solid {card_border} !important;
            border-radius: 28px !important;
            padding: 10px 18px !important;
            font-weight: 600 !important;
            font-size: 0.92rem !important;
            box-shadow: 0 4px 14px rgba(0,0,0,0.25) !important;
            transition: all 0.2s ease !important;
        }}
        .gemini-new-chat-btn button:hover {{
            background-color: {card_hover} !important;
            border-color: {input_focus} !important;
            color: #ffffff !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 18px rgba(168, 85, 247, 0.3) !important;
        }}

        /* Session Item in Sidebar */
        .session-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            border-radius: 12px;
            margin-bottom: 4px;
            background: transparent;
            transition: all 0.15s ease;
            font-size: 0.88rem;
        }}
        .session-item.active {{
            background-color: {session_active_bg};
            font-weight: 600;
        }}
        .session-item:hover {{
            background-color: {card_hover};
        }}

        /* Gemini Hero Header (Empty State) */
        .gemini-hero {{
            text-align: center;
            padding: 40px 10px 30px 10px;
        }}
        /* Hide all chat avatars and icons */
        div[data-testid="stChatMessageAvatarUser"],
        div[data-testid="stChatMessageAvatarAssistant"],
        div[data-testid="chatAvatarIcon-user"],
        div[data-testid="chatAvatarIcon-assistant"],
        div[data-testid="stChatMessage"] [data-testid="stIconMaterial"] {{
            display: none !important;
        }}
        .gemini-title {{
            font-size: 2.8rem !important;
            font-weight: 800 !important;
            background: linear-gradient(90deg, #c084fc 0%, #e879f9 50%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0 0 10px 0 !important;
            letter-spacing: -0.03em;
        }}
        .gemini-subtitle {{
            font-size: 1.15rem !important;
            color: {text_secondary} !important;
            font-weight: 400 !important;
            margin: 0 !important;
        }}

        /* Quick Suggestion Prompt Buttons */
        div[data-testid="stColumn"] div[data-testid="stButton"] > button,
        div[data-testid="column"] div[data-testid="stButton"] > button,
        .main div[data-testid="stButton"] > button {{
            height: auto !important;
            min-height: 84px !important;
            white-space: pre-wrap !important;
            text-align: left !important;
            border-radius: 16px !important;
            border: 1px solid rgba(168, 85, 247, 0.35) !important;
            background: rgba(22, 18, 38, 0.85) !important;
            background-color: rgba(22, 18, 38, 0.85) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            padding: 16px 20px !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }}
        div[data-testid="stColumn"] div[data-testid="stButton"] > button *,
        div[data-testid="column"] div[data-testid="stButton"] > button *,
        .main div[data-testid="stButton"] > button * {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            line-height: 1.45 !important;
        }}
        div[data-testid="stColumn"] div[data-testid="stButton"] > button:hover,
        div[data-testid="column"] div[data-testid="stButton"] > button:hover,
        .main div[data-testid="stButton"] > button:hover {{
            border-color: #c084fc !important;
            background: rgba(45, 32, 75, 0.95) !important;
            background-color: rgba(45, 32, 75, 0.95) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(168, 85, 247, 0.35) !important;
        }}
        div[data-testid="stColumn"] div[data-testid="stButton"] > button:hover *,
        div[data-testid="column"] div[data-testid="stButton"] > button:hover *,
        .main div[data-testid="stButton"] > button:hover * {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }}

        /* Streamlit Chat Messages */
        [data-testid="stChatMessage"] {{
            background-color: transparent !important;
            border: none !important;
            padding: 12px 2px !important;
            margin-bottom: 8px !important;
            color: {text_primary} !important;
        }}
        [data-testid="stChatMessage"] p, 
        [data-testid="stChatMessage"] li, 
        [data-testid="stChatMessage"] span {{
            color: #e2e8f0 !important;
            font-size: 1rem !important;
            line-height: 1.7 !important;
        }}
        [data-testid="stChatMessage"] strong {{
            color: #ffffff !important;
            font-weight: 600 !important;
        }}

        /* User Message Bubble */
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
            background-color: {user_bubble_bg} !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
            border: 1px solid {user_bubble_border} !important;
            border-radius: 24px !important;
            padding: 14px 22px !important;
            margin-left: 10%;
            margin-bottom: 20px !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
        }}

        /* Floating Pill Chat Input */
        div[data-testid="stChatInput"] {{
            background: rgba(20, 16, 36, 0.92) !important;
            background-color: rgba(20, 16, 36, 0.92) !important;
            backdrop-filter: blur(16px) !important;
            -webkit-backdrop-filter: blur(16px) !important;
            border: 1.5px solid rgba(168, 85, 247, 0.45) !important;
            border-radius: 32px !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4) !important;
            padding: 4px 14px !important;
            transition: all 0.2s ease !important;
        }}
        div[data-testid="stChatInput"]:focus-within {{
            border-color: #c084fc !important;
            box-shadow: 0 8px 32px rgba(168, 85, 247, 0.35) !important;
        }}
        div[data-testid="stChatInput"] > div,
        div[data-testid="stChatInput"] > div > div,
        div[data-testid="stChatInput"] [data-baseweb="base-input"] {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInputTextArea"],
        [data-testid="stChatInput"] textarea,
        [data-testid="stChatInputTextArea"],
        div[data-testid="stChatInput"] input {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            background: transparent !important;
            background-color: transparent !important;
            font-size: 1rem !important;
            font-weight: 500 !important;
            line-height: 1.5 !important;
            caret-color: #c084fc !important;
        }}
        div[data-testid="stChatInput"] textarea::placeholder,
        div[data-testid="stChatInputTextArea"]::placeholder,
        [data-testid="stChatInput"] textarea::placeholder,
        textarea::placeholder {{
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            opacity: 1 !important;
        }}
        div[data-testid="stChatInput"] textarea::-webkit-input-placeholder,
        div[data-testid="stChatInputTextArea"]::-webkit-input-placeholder {{
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            opacity: 1 !important;
        }}
        div[data-testid="stChatInput"] textarea::-moz-placeholder,
        div[data-testid="stChatInputTextArea"]::-moz-placeholder {{
            color: #94a3b8 !important;
            opacity: 1 !important;
        }}
        div[data-testid="stChatInput"] button {{
            color: #ffffff !important;
            background: linear-gradient(135deg, #9333ea 0%, #7e22ce 100%) !important;
            border-radius: 50% !important;
            width: 36px !important;
            height: 36px !important;
            border: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: all 0.2s ease !important;
        }}
        div[data-testid="stChatInput"] button:hover {{
            transform: scale(1.08);
            box-shadow: 0 2px 14px rgba(192, 132, 252, 0.5);
        }}

        /* RAG Sources Accordion / Expander */
        .streamlit-expanderHeader {{
            background-color: {card_bg} !important;
            border: 1px solid {card_border} !important;
            border-radius: 12px !important;
            color: #cbd5e1 !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            padding: 6px 12px !important;
        }}
        .streamlit-expanderContent {{
            background-color: rgba(16, 12, 28, 0.85) !important;
            backdrop-filter: blur(12px) !important;
            border: 1px solid {card_border} !important;
            border-top: none !important;
            border-radius: 0 0 12px 12px !important;
            padding: 12px !important;
        }}

        /* Badges */
        .badge-graph {{
            background: rgba(34, 197, 94, 0.15) !important;
            color: #4ade80 !important;
            border: 1px solid rgba(74, 222, 128, 0.3) !important;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.74rem;
            font-weight: 600;
            display: inline-block;
            margin-right: 6px;
        }}
        .badge-vector {{
            background: rgba(168, 85, 247, 0.18) !important;
            color: #c084fc !important;
            border: 1px solid rgba(192, 132, 252, 0.3) !important;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.74rem;
            font-weight: 600;
            display: inline-block;
            margin-right: 6px;
        }}
        .badge-meta {{
            background: rgba(234, 179, 8, 0.15) !important;
            color: #facc15 !important;
            border: 1px solid rgba(250, 204, 21, 0.3) !important;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.74rem;
            font-weight: 600;
            display: inline-block;
            margin-right: 6px;
        }}

        /* Code and Pre */
        code {{
            background-color: rgba(32, 25, 54, 0.75) !important;
            color: #e879f9 !important;
            border-radius: 6px !important;
            padding: 2px 6px !important;
        }}
        pre {{
            background-color: rgba(16, 12, 28, 0.85) !important;
            border: 1px solid rgba(168, 85, 247, 0.2) !important;
            border-radius: 12px !important;
        }}
        hr {{
            border-color: rgba(168, 85, 247, 0.18) !important;
        }}

        /* Disclaimer footer text */
        .chat-disclaimer {{
            text-align: center;
            color: {text_secondary};
            font-size: 0.76rem;
            margin-top: 14px;
            letter-spacing: 0.01em;
        }}
    </style>
    """

# Inject Theme CSS
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Sidebar: Gemini Style Navigation and Chat History
with st.sidebar:
    st.markdown(
        """
        <div style='margin-bottom: 6px;'>
            <div style='font-weight: 800; font-size: 1.25rem; line-height: 1.2; color: #f1f5f9;'>LoL RAG Assistant</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # + New Chat
    st.markdown("<div class='gemini-new-chat-btn'>", unsafe_allow_html=True)
    if st.button("New Chat", key = "btn_new_chat", use_container_width = True):
        create_new_chat()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Chat history from PostgreSQL
    st.markdown("<div style='font-size: 0.82rem; font-weight: 700; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase;'>Recent Chats</div>", unsafe_allow_html=True)

    if db_online:
        sessions_list = db.list_sessions()
        if sessions_list:
            for s in sessions_list[:12]:
                sid = s["session_id"]
                title = s.get("title", "Conversation")
                if len(title) > 28:
                    title = title[:28] + "..."
                is_active = sid == st.session_state.current_session_id

                col_btn, col_del = st.columns([5, 1])
                with col_btn:
                    btn_type = "primary" if is_active else "secondary"
                    if st.button(title, key = f"session_{sid}", use_container_width = True, type = btn_type):
                        if not is_active:
                            switch_session(sid)
                with col_del:
                    if st.button("X", key = f"del_{sid}", help = "Delete this chat"):
                        delete_chat(sid)
        else:
            st.caption("No chat history yet.")
    else:
        st.warning("PostgreSQL offline. Session stored in-memory.")

# Main Chat Area

# Handle prompt triggered from suggested cards
prompt_to_send = None
if st.session_state.pending_prompt:
    prompt_to_send = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

# 1. EMPTY STATE HERO (When current session has no messages)
if len(st.session_state.messages) == 0 and not prompt_to_send:
    st.markdown(
        """
        <div class='gemini-hero'>
            <h1 class='gemini-title'>Welcome, Summoner</h1>
            <p class='gemini-subtitle'>How can I assist your tactical gameplay on Summoner's Rift today?</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4 Quick Action Prompt Cards
    c1, c2 = st.columns(2)
    with c1:
        if st.button("How should we draft an effective wombo combo team comp?", key = "card_1", use_container_width = True):
            st.session_state.pending_prompt = "How should we draft an effective teamfight wombo combo composition?"
            st.rerun()
        if st.button("What is the lore conflict between Zed and Shen?", key = "card_2", use_container_width = True):
            st.session_state.pending_prompt = "Explain the lore conflict between Zed and Shen in Ionia."
            st.rerun()

    with c2:
        if st.button("What are the core items and runes for Aatrox?", key = "card_3", use_container_width = True):
            st.session_state.pending_prompt = "What is the best build and keystone rune for Aatrox?"
            st.rerun()
        if st.button("How many skins does Yasuo have, and what are his iconic lines?", key = "card_4", use_container_width = True):
            st.session_state.pending_prompt = "How many total skins does Yasuo have, and what are his most iconic skin lines like PROJECT, Nightbringer, and Spirit Blossom?"
            st.rerun()

# 2. RENDER MESSAGE STREAM
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]

    with st.chat_message(role, avatar = None):
        st.markdown(content)


# 3. CHAT INPUT and EXECUTION
user_input = st.chat_input("Ask about Champions, Items, Counters, Builds, Runes, Abilities...")
if prompt_to_send:
    user_input = prompt_to_send

if user_input and bot:
    curr_sid = st.session_state.current_session_id

    # If first message in session, create session in DB with prompt title
    if len(st.session_state.messages) == 0 and db_online:
        title_snippet = user_input.strip()
        if len(title_snippet) > 35:
            title_snippet = title_snippet[:35] + "..."
        db.create_session(curr_sid, title = title_snippet)

    # A. Display and record user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    if db_online:
        db.add_message(curr_sid, "user", user_input)

    with st.chat_message("user", avatar = None):
        st.markdown(user_input)

    # B. Generate response from LoLBot
    with st.chat_message("assistant", avatar = None):
        response_placeholder = st.empty()
        with st.spinner("Synthesizing tactical insights from Knowledge Base..."):
            t_start = time.time()
            result = bot.answer(user_input)
            elapsed_ms = (time.time() - t_start) * 1000

        raw_response = result.get("response", "")

        # Structured JSON-payload beautifier
        if isinstance(raw_response, str) and raw_response.strip().startswith("{") and "structured_data" in raw_response:
            try:
                import json
                parsed = json.loads(raw_response)
                final_text = bot.generator.format_fallback(parsed)
            except Exception:
                final_text = raw_response
        else:
            final_text = raw_response

        response_placeholder.markdown(final_text)

        intent = result.get("intent", "UNKNOWN")
        rag_contexts = result.get("rag_contexts", [])

        # Save assistant message in session and PostgreSQL
        rag_meta_payload = {
            "intent": intent,
            "latency_ms": elapsed_ms,
            "rag_contexts": rag_contexts,
        }
        st.session_state.messages.append({
            "role": "assistant",
            "content": final_text,
            "rag_meta": rag_meta_payload,
        })
        if db_online:
            db.add_message(curr_sid, "assistant", final_text, rag_meta_payload)

# 4. BOTTOM DISCLAIMER (Gemini standard)
st.markdown(
    "<div class='chat-disclaimer'>LoL RAG AI can make mistakes. Verify critical game mechanics before entering your match.</div>",
    unsafe_allow_html=True,
)
