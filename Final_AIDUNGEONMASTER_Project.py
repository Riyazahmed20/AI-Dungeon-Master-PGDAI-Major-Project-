# ai_dungeon_master_with_db_and_bg.py
import streamlit as st
import os
import base64
import time
import json
import sqlite3
from openai import OpenAI
# ---------------------------
# Configuration
# ---------------------------
st.set_page_config(page_title="AI Dungeon Master", layout="wide")
# Image paths (edit if your files are elsewhere)
PARCHMENT_TEXTURE = "templates/Scroll wooden-floor background.jpg"
SCROLL_IMAGE = "static/Scroll_PNG_Clipart.png"
IMG_FOREST = "templates/forest background.jpg"
IMG_LIGHTHOUSE = "templates/lighthouse background.jpg"  # add your lighthouse image here
IMG_DEFAULT_BG = PARCHMENT_TEXTURE

# ---------------------------
# Helpers
# ---------------------------
def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

def file_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def set_page_background(image_path: str, fade: float = 0.45):
    """Embed page background with a light fade overlay."""
    if not image_path or not os.path.exists(image_path):
        return
    b64 = file_to_base64(image_path)
    css = f"""
    <style>
    [data-testid="stAppViewContainer"], .stApp {{
      background: linear-gradient(rgba(255,255,240,{fade}), rgba(255,255,240,{fade})),
                  url("data:image/jpeg;base64,{b64}") center/cover no-repeat fixed;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# Inject CSS (parchment font, parchment-box, scroll animation, choices)
def inject_css(parchment_b64: str, show_parchment_background: bool = True):
    bg_css = (f'url("data:image/jpeg;base64,{parchment_b64}") center/cover no-repeat fixed' if parchment_b64 and show_parchment_background else "linear-gradient(180deg,#fffaf0,#fffdf8)")
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"], .stApp {{
        background: linear-gradient(rgba(255,255,240,0.50), rgba(255,255,240,0.50)), {bg_css};
    }}
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');
    html, body, [class*="css"] {{
        font-family: 'MedievalSharp', serif;
        color: #3e2723;
    }}
    .intro-wrap {{
        height: 100vh;
        display:flex;
        align-items:center;
        justify-content:center;
        overflow:hidden;
        position: relative;
    }}
    .scroll-unroll {{
        width: 90%;
        max-width: 1300px;
        animation: unroll 1.8s ease-out forwards;
        transform-origin: top center;
    }}
    @keyframes unroll {{
        0% {{ transform: scaleY(0); opacity: 0; }}
        60% {{ transform: scaleY(1.02); opacity: 1; }}
        100% {{ transform: scaleY(1); opacity: 1; }}
    }}
    .scroll-text {{
        position: absolute;
        width: 70%;
        max-width: 980px;
        top: 28%;
        left: 50%;
        transform: translateX(-50%);
        text-align:center;
        color:#3e2723;
        text-shadow: 0 1px 0 rgba(255,255,255,0.6);
    }}
    .scroll-title {{ font-size:44px; font-weight:800; margin-bottom:8px; }}
    .scroll-sub {{ font-size:18px; }}
    .intro-counter {{ position: absolute; bottom: 6%; left: 50%; transform: translateX(-50%); color: #5b3e2b; font-weight:600; }}
    .parchment-box {{
        background: rgba(255,250,230,0.92);
        border: 6px solid rgba(120,85,50,0.12);
        border-radius: 12px;
        padding: 22px;
        margin: 14px 0;
        box-shadow: 0 8px 24px rgba(0,0,0,0.16);
        background-image: {('url("data:image/jpeg;base64,' + parchment_b64 + '")') if parchment_b64 else 'none'};
        background-size: cover;
        background-blend-mode: multiply;
    }}
    .dm-new {{ animation: fadeSlide 0.6s ease-out; }}
    @keyframes fadeSlide {{ from {{ opacity:0; transform:translateY(18px); }} to {{ opacity:1; transform:translateY(0); }} }}
    .choices-area {{ margin-top:12px; display:flex; flex-wrap:wrap; gap:12px; }}
    .choice-btn {{ background:#f4e1c1; border:2px solid #8d6e63; color:#3e2723; padding:10px 16px; border-radius:8px; cursor:pointer; font-weight:600; }}
    .choice-btn:hover {{ background:#e9d0a0; }}
    .meta {{ font-size:0.9em; color:#5b3e2b; margin-bottom:6px; }}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------
# OpenAI client init (OpenAI only)
# ---------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI API key loaded")  # Backend console output
    except Exception as e:
        client = None
        print(f"OpenAI init error: {e}")
else:
    print("No OpenAI key found — offline mode available")

# ---------------------------
# Offline stories with per-segment backgrounds
# ---------------------------
OFFLINE_STORIES = [
    {
        "id": "stillhollow",
        "title": "Lantern of Stillhollow",
        "segments": [
            {
                "text": "You arrive at the fog-choked town of Stillhollow...",
                "background": IMG_LIGHTHOUSE,
                "choices": [
                    {"label": "Enter Stillhollow", "result": "You step into the fog-wreathed square."},
                    {"label": "Scout the coast", "result": "On the pier you find barnacled charts."},
                    {"label": "Question the locals", "result": "A fisherwoman whispers of a drowned bell."}
                ],
            },
            {
                "text": "You approach the lighthouse atop the cliff...",
                "background": IMG_LIGHTHOUSE,
                "choices": [
                    {"label": "Pick the lock", "result": "The lock clicks softly."},
                    {"label": "Break the door", "result": "The door splinters on impact."},
                    {"label": "Circle the lighthouse", "result": "Behind the tower, a hidden cellar gapes."}
                ],
            },
            {
                "text": "Down below, a ruined jetty leads to watery graves...",
                "background": IMG_FOREST,
                "choices": [
                    {"label": "Investigate the jetty", "result": "You find a carved rune."},
                    {"label": "Call out to the sea", "result": "Your voice is swallowed by the fog."},
                    {"label": "Return to town", "result": "The lantern in a shop window flickers oddly."}
                ],
            },
        ],
    },
    {
        "id": "obsidian_crypt",
        "title": "The Obsidian Crypt",
        "segments": [
            {
                "text": "At the edge of the desert stands the Obsidian Crypt, its door sealed for centuries...",
                "background": IMG_FOREST,
                "choices": [
                    {"label": "Examine the carvings", "result": "Ancient glyphs warn of a curse."},
                    {"label": "Push open the door", "result": "The door grinds open, revealing darkness."},
                    {"label": "Circle the crypt", "result": "You find a sand-buried skeleton clutching a key."}
                ],
            },
            {
                "text": "Inside, torchlight dances across black stone walls...",
                "background": IMG_LIGHTHOUSE,
                "choices": [
                    {"label": "Take the left passage", "result": "It leads to a chamber of broken statues."},
                    {"label": "Take the right passage", "result": "You hear faint whispers ahead."},
                    {"label": "Go straight ahead", "result": "A massive door stands before you, chained shut."}
                ],
            },
            {
                "text": "Deep within, you stand before a sarcophagus of polished obsidian...",
                "background": IMG_FOREST,
                "choices": [
                    {"label": "Open the sarcophagus", "result": "Inside lies a golden dagger."},
                    {"label": "Inspect the surroundings", "result": "Symbols on the walls shift before your eyes."},
                    {"label": "Leave quietly", "result": "You retreat, the whispers fading."}
                ],
            },
        ],
    },
    {
        "id": "stormspire",
        "title": "Stormspire Keep",
        "segments": [
            {
                "text": "Lightning arcs across the sky as you reach Stormspire Keep...",
                "background": IMG_LIGHTHOUSE,
                "choices": [
                    {"label": "Enter the courtyard", "result": "You step through a gate of rusted iron."},
                    {"label": "Climb the outer wall", "result": "Rain makes the climb treacherous."},
                    {"label": "Search the stables", "result": "You find an abandoned warhorse."}
                ],
            },
            {
                "text": "Inside, the halls echo with the sound of distant footsteps...",
                "background": IMG_FOREST,
                "choices": [
                    {"label": "Head for the throne room", "result": "A shattered crown lies on the dais."},
                    {"label": "Descend into the dungeons", "result": "A prisoner begs for your help."},
                    {"label": "Search the library", "result": "You find a tome crackling with static energy."}
                ],
            },
            {
                "text": "At the highest tower, you confront the source of the storm...",
                "background": IMG_LIGHTHOUSE,
                "choices": [
                    {"label": "Attack the sorcerer", "result": "Your weapon clashes with his staff."},
                    {"label": "Offer a truce", "result": "He pauses, lightning fading in his eyes."},
                    {"label": "Flee the tower", "result": "The storm follows you down the stairs."}
                ],
            },
        ],
    },
    {
        "id": "whispering_forest",
        "title": "The Whispering Forest",
        "segments": [
            {
                "text": "The trees seem to murmur as you step into the Whispering Forest...",
                "background": IMG_FOREST,
                "choices": [
                    {"label": "Follow the whispers", "result": "They lead you to a mossy stone circle."},
                    {"label": "Climb a tree", "result": "You see smoke rising far to the east."},
                    {"label": "Search the undergrowth", "result": "You find an old leather satchel."}
                ],
            },
            {
                "text": "The deeper you go, the louder the voices become...",
                "background": IMG_FOREST,
                "choices": [
                    {"label": "Confront the voices", "result": "They belong to a council of dryads."},
                    {"label": "Ignore them", "result": "A root snags your foot, almost tripping you."},
                    {"label": "Ask for guidance", "result": "The dryads tell of a hidden glade."}
                ],
            },
            {
                "text": "In the glade, moonlight falls upon a crystal pool...",
                "background": IMG_LIGHTHOUSE,
                "choices": [
                    {"label": "Drink from the pool", "result": "You feel a strange power course through you."},
                    {"label": "Look into the water", "result": "You see visions of your future."},
                    {"label": "Leave the glade", "result": "The forest quiets as you depart."}
                ],
            },
        ],
    },
]

# ---------------------------
# Database (per-player saves)
# ---------------------------
DB_FOLDER = os.path.join(os.path.expanduser("~"), ".ai_dungeon_master")
os.makedirs(DB_FOLDER, exist_ok=True)
DB_PATH = os.path.join(DB_FOLDER, "game_data.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS saves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT,
    created_at REAL,
    mode TEXT,
    history TEXT,
    offline_story_id TEXT,
    offline_segment INTEGER
)
""")
conn.commit()

def save_to_db(player_name: str):
    cur.execute("INSERT INTO saves (player_name, created_at, mode, history, offline_story_id, offline_segment) VALUES (?,?,?,?,?,?)",
                (player_name, time.time(), st.session_state.mode, json.dumps(st.session_state.online_history),
                 st.session_state.offline_story_id, st.session_state.offline_segment))
    conn.commit()

def list_saves():
    cur.execute("SELECT id, player_name, created_at FROM saves ORDER BY created_at DESC")
    return cur.fetchall()

def load_from_db(save_id: int):
    cur.execute("SELECT player_name, mode, history, offline_story_id, offline_segment FROM saves WHERE id=?", (save_id,))
    row = cur.fetchone()
    if row:
        st.session_state.character_name = row[0]
        st.session_state.mode = row[1]
        st.session_state.online_history = json.loads(row[2])
        st.session_state.offline_story_id = row[3]
        st.session_state.offline_segment = row[4]
        return True
    return False

def delete_save(save_id: int):
    cur.execute("DELETE FROM saves WHERE id=?", (save_id,))
    conn.commit()
# ---------------------------
# Parse AI output (robust)
# ---------------------------
def parse_ai_output(text):
    if not text:
        return ("", [])
    lines = [ln.rstrip() for ln in text.splitlines()]
    joined_lower = "\n".join(lines).lower()
    choices = []
    if "choices:" in joined_lower:
        story_lines = []
        in_choices = False
        for ln in lines:
            if ln.strip().lower().startswith("choices:"):
                in_choices = True
                continue
            if in_choices:
                s = ln.strip()
                if not s:
                    continue
                s = s.lstrip("0123456789.)-• \t")
                if s:
                    choices.append(s)
            else:
                story_lines.append(ln)
        return ("\n".join(story_lines).strip(), choices)
    story_lines = []
    for ln in lines:
        s = ln.strip()
        if not s:
            story_lines.append(ln)
            continue
        if (s[0].isdigit() and (s[1:2] in ('.', ')'))) or s.startswith(("-", "•")):
            candidate = s.lstrip("0123456789.)-• \t")
            if len(candidate.split()) <= 20:
                choices.append(candidate)
            else:
                story_lines.append(ln)
        else:
            story_lines.append(ln)
    if not choices:
        tail = [ln.strip() for ln in lines[-6:] if ln.strip()]
        heur = [ln for ln in tail if len(ln.split()) <= 12]
        choices = heur[-3:]
        story_lines = lines[:-len(choices)] if choices else lines
    return ("\n".join(story_lines).strip(), choices)

# ---------------------------
# Session state init
# ---------------------------
if "intro_seen" not in st.session_state:
    st.session_state.intro_seen = False
if "intro_start" not in st.session_state:
    st.session_state.intro_start = time.time()
if "character_name" not in st.session_state:
    st.session_state.character_name = ""
if "mode" not in st.session_state:
    st.session_state.mode = None
if "online_history" not in st.session_state:
    st.session_state.online_history = []
if "offline_story_id" not in st.session_state:
    st.session_state.offline_story_id = OFFLINE_STORIES[0]["id"]
if "offline_segment" not in st.session_state:
    st.session_state.offline_segment = 0

# ---------------------------
# Inject CSS (hide parchment on intro)
# ---------------------------
parch_b64 = file_to_base64(PARCHMENT_TEXTURE) if os.path.exists(PARCHMENT_TEXTURE) else ""
inject_css(parch_b64, show_parchment_background=st.session_state.intro_seen)

# ---------------------------
# Intro (scroll) – auto advance after 8s
# ---------------------------
INTRO_DURATION = 5.0

# Initialize intro state
if "intro_seen" not in st.session_state:
    st.session_state.intro_seen = False
if "intro_page" not in st.session_state:
    st.session_state.intro_page = 1
if "intro_start" not in st.session_state:
    st.session_state.intro_start = time.time()

# ---------------- PAGE 1 ----------------
if not st.session_state.intro_seen and st.session_state.intro_page == 1:
    if os.path.exists(SCROLL_IMAGE):
        sb64 = file_to_base64(SCROLL_IMAGE)
        scroll_tag = f'<img src="data:image/png;base64,{sb64}" style="width:90%; max-width:1300px; object-fit:contain;">'
    else:
        scroll_tag = ""

    css = f"""
    <link href="https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap" rel="stylesheet">
    <style>
    @keyframes scrollUpFade {{
        0% {{ transform: translateY(0); opacity: 1; }}
        100% {{ transform: translateY(-150px); opacity: 0; }}
    }}
    .intro-wrap {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 90vh;
        animation: scrollUpFade {INTRO_DURATION}s ease-out forwards;
        text-align: center;
        font-family: 'MedievalSharp', cursive;
        background: url("data:image/png;base64,{parch_b64}") no-repeat center center;
        background-size: cover;
        padding: 20px;
    }}
    .scroll-title {{
        font-size: 3em;
        font-weight: bold;
        margin-top: 20px;
        color: #4b2e00;
        text-shadow: 2px 2px #d4b483;
    }}
    .scroll-sub {{
        font-size: 1.5em;
        margin-top: 10px;
        color: #5a3c10;
        text-shadow: 1px 1px #e6c79c;
    }}
    .intro-counter {{
        position: absolute;
        bottom: 20px;
        font-size: 18px;
        color: rgba(255, 255, 255, 0.8);
        font-family: Arial, sans-serif;
    }}
    </style>
    """

    html = f"""
       {css}
       <div class="intro-wrap">
         <div class="scroll-unroll">{scroll_tag}</div>
         <div class="scroll-text">
            <div class="scroll-title">AI DUNGEON MASTER</div>
            <div class="scroll-sub">Created by: Mohd. Riyazuddin Ahmed, Siddhant Ojha and Rudransh Singh</div>
         </div>
       </div>
       """

    elapsed = time.time() - st.session_state.intro_start
    remaining = max(0, int(INTRO_DURATION - elapsed))
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(f"<div class='intro-counter'>Page 1 ends in ~{remaining}s</div>", unsafe_allow_html=True)

    if elapsed < INTRO_DURATION:
        time.sleep(0.5)
        safe_rerun()
    else:
        st.session_state.intro_page = 2
        st.session_state.intro_start = time.time()
        safe_rerun()

# ---------------------------
# Character / Home screen
# ---------------------------
if st.session_state.mode is None:
    # show parchment background now
    set_page_background(PARCHMENT_TEXTURE, fade=0.45)
    st.markdown("<div style='display:flex; gap:20px; align-items:center;'>", unsafe_allow_html=True)
    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
    st.markdown(f"""<div style='width:720px; background: rgba(255,250,230,0.95); border-radius:14px; padding:30px; box-shadow:0 10px 30px rgba(0,0,0,0.14);'>
                    <h1 style='margin:0; font-size:36px; color:#3e2723;'>Create your character</h1>
                    <p style='color:#5b3e2b; margin-top:8px;'>Name your hero, pick a class and difficulty, then begin your adventure.</p>""", unsafe_allow_html=True)

    # Character name and options
    st.session_state.character_name = st.text_input("Character Name", value=st.session_state.character_name, key="ui_name")
    cols = st.columns([1,1,1])
    with cols[0]:
        difficulty = st.selectbox("Difficulty", ["Normal","Hard","Story Mode"])
    with cols[1]:
        cls = st.selectbox("Class", ["Ranger","Sorcerer","Warrior","Rogue"])
    with cols[2]:
        show_tips = st.checkbox("Show tips", value=True)

    # Save/load area (list saves)
    st.markdown("<div style='margin-top:12px; display:flex; gap:12px;'>", unsafe_allow_html=True)
    if st.button("Start Online (AI)"):
        if not st.session_state.character_name.strip():
            st.warning("Please enter a character name.")
        else:
            st.session_state.mode = "online"
            st.session_state.online_history = []
            safe_rerun()
    if st.button("Start Offline"):
        if not st.session_state.character_name.strip():
            st.warning("Please enter a character name.")
        else:
            st.session_state.mode = "offline"
            st.session_state.offline_segment = 0
            st.session_state.online_history = []
            safe_rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Saved games")
    saves = list_saves()
    if saves:
        for sid, pname, ctime in saves:
            col1, col2, col3 = st.columns([3,1,1])
            with col1:
                st.write(f"{pname}** — {time.ctime(ctime)}")
            with col2:
                if st.button("Load", key=f"load_{sid}"):
                    loaded = load_from_db(sid)
                    if loaded:
                        st.success("Loaded save.")
                        safe_rerun()
                    else:
                        st.error("Failed to load.")
            with col3:
                if st.button("Delete", key=f"del_{sid}"):
                    delete_save(sid)
                    st.success("Deleted save.")
                    safe_rerun()
    else:
        st.write("No saves yet. Your gameplay will appear here after you save.")

    st.markdown("</div><div style='flex:1'></div>", unsafe_allow_html=True)
    st.stop()

# ---------------------------
# AI helper
# ---------------------------
def ask_ai_and_update(choice_label=None, free_text=None):
    history = st.session_state.online_history[-8:]
    prompt = "You are a consistent Dungeon Master running a long-form interactive fantasy adventure. Maintain continuity and character.\n\n"
    prompt += "History:\n"
    for h in history:
        prompt += h + "\n"
    if choice_label:
        prompt += f"Player chooses: {choice_label}\n"
    elif free_text:
        prompt += f"Player says: {free_text}\n"
    prompt += "Now continue the story in vivid detail (a few paragraphs) and then provide exactly 3 clear choices for the player (either numbered or under 'Choices:')."

    if not client:
        raise RuntimeError("OpenAI client not configured")
    try:
        # Try Responses API
        try:
            resp = client.responses.create(model="gpt-4o-mini", input=prompt, max_output_tokens=400, temperature=0.8)
            text = ""
            if getattr(resp, "output_text", None):
                text = resp.output_text
            else:
                outputs = resp.output if hasattr(resp, "output") else resp.get("output", [])
                if isinstance(outputs, list) and outputs:
                    parts = []
                    for o in outputs:
                        if isinstance(o, dict) and "content" in o:
                            for c in o["content"]:
                                if c.get("type") == "output_text":
                                    parts.append(c.get("text",""))
                    text = "\n".join(parts).strip()
                else:
                    text = str(resp)
        except Exception:
            # fallback to old chat completion (SDK specific)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":"You are a helpful Dungeon Master."},
                          {"role":"user","content":prompt}],
                max_tokens=400,
                temperature=0.8
            )
            text = resp.choices[0].message.content
        story_text, choices = parse_ai_output(text)
        dm_block = "DM: " + story_text.strip()
        if choices:
            dm_block += "\n\nChoices:\n" + "\n".join([f"{i+1}. {c}" for i,c in enumerate(choices)])
        st.session_state.online_history.append(dm_block)
        return story_text, choices
    except Exception as e:
        raise
# ---------------------------
# Utility: choose background for a block based on keywords (online)
# ---------------------------
def pick_bg_for_text(text: str):
    t = text.lower()
    if "forest" in t or "trees" in t or "wood" in t:
        return IMG_FOREST if os.path.exists(IMG_FOREST) else IMG_DEFAULT_BG
    if "lighthouse" in t or "sea" in t or "pier" in t or "coast" in t:
        return IMG_LIGHTHOUSE if os.path.exists(IMG_LIGHTHOUSE) else IMG_DEFAULT_BG
    return IMG_DEFAULT_BG
# ---------------------------
# Online Mode UI & Flow
# ---------------------------
if st.session_state.mode == "online":
    st.header(f"🌐 Online Adventure — {st.session_state.character_name}")

    # If no DM intro exists, ask AI
    if not st.session_state.online_history:
        try:
            ask_ai_and_update()
        except Exception:
            st.warning("AI not available — switching to offline mode.")
            st.session_state.mode = "offline"
            safe_rerun()

    # Find last DM block and adjust background accordingly
    last_dm_block = next((b for b in reversed(st.session_state.online_history) if b.startswith("DM:")), None)
    if last_dm_block:
        # pick background by heuristics
        bg = pick_bg_for_text(last_dm_block)
        set_page_background(bg, fade=0.5)

    # Render full history. Animate latest DM.
    last_dm_index = None
    for i, entry in enumerate(st.session_state.online_history):
        if entry.startswith("DM:"):
            last_dm_index = i
    for idx, entry in enumerate(st.session_state.online_history):
        if entry.startswith("DM:"):
            is_new = (idx == last_dm_index)
            cls = "parchment-box dm-new" if is_new else "parchment-box"
            html = f"<div class='{cls}'><div class='meta'>Dungeon Master</div><div style='white-space:pre-wrap; font-size:1.05em;'>{entry[3:].replace(chr(10),'<br>')}</div></div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='margin:8px 0; color:#2f2f2f;'><b>Player:</b> {entry.replace('PLAYER: ','')}</div>", unsafe_allow_html=True)

    # Choices at bottom (after DM)
    last_dm = last_dm_block or ""
    story_text, choices = parse_ai_output(last_dm[3:] if last_dm else "")
    if choices:
        st.markdown("<div class='choices-area'>", unsafe_allow_html=True)
        for i, c in enumerate(choices):
            key = f"online_choice_{i}_{len(st.session_state.online_history)}"
            if st.button(c, key=key):
                st.session_state.online_history.append("PLAYER: " + c)
                try:
                    ask_ai_and_update(choice_label=c)
                except Exception:
                    st.warning("AI error — switching to offline mode.")
                    st.session_state.mode = "offline"
                safe_rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        txt = st.text_input("Your action (free text):", key="free_action")
        if st.button("Submit action (free)"):
            if txt.strip():
                st.session_state.online_history.append("PLAYER: " + txt.strip())
                try:
                    ask_ai_and_update(free_text=txt.strip())
                except Exception:
                    st.warning("AI error — switching to offline mode.")
                    st.session_state.mode = "offline"
                safe_rerun()

    # Save/load controls for online mode
    st.markdown("---")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Save Game (to DB)"):
            if not st.session_state.character_name.strip():
                st.warning("Please enter a character name on the home screen before saving.")
            else:
                save_to_db(st.session_state.character_name.strip())
                st.success("Saved to DB.")
    with col2:
        if st.button("Return to Home"):
            st.session_state.mode = None
            safe_rerun()

# ---------------------------
# Offline Mode UI & Flow
# ---------------------------
elif st.session_state.mode == "offline":
    # show selection of offline story and segment background
    titles = [s["title"] for s in OFFLINE_STORIES]
    title_map = {s["title"]: s for s in OFFLINE_STORIES}
    sel_title = st.selectbox("Choose an offline adventure:", titles, index=0)
    story = title_map[sel_title]
    seg_idx = st.session_state.offline_segment
    if seg_idx >= len(story["segments"]):
        st.success("🎉 You completed this offline adventure!")
        if st.button("Return to home"):
            st.session_state.mode = None
            safe_rerun()
    else:
        seg = story["segments"][seg_idx]
        # set segment background if provided
        seg_bg = seg.get("background", IMG_DEFAULT_BG)
        if seg_bg and os.path.exists(seg_bg):
            set_page_background(seg_bg, fade=0.45)
        else:
            set_page_background(PARCHMENT_TEXTURE, fade=0.45)

        st.markdown(f"<div class='parchment-box'><h2 style='margin-top:0'>{story['title']}</h2><div style='white-space:pre-wrap; font-size:1.05em;'>{seg['text']}</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='choices-area'>", unsafe_allow_html=True)
        for i, ch in enumerate(seg["choices"]):
            key = f"off_choice_{seg_idx}_{i}"
            if st.button(ch["label"], key=key):
                st.session_state.online_history.append("OFFLINE: " + ch["result"])
                st.session_state.offline_segment += 1
                safe_rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # Save / Return controls
        st.markdown("---")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("Save Game (to DB)"):
                if not st.session_state.character_name.strip():
                    st.warning("Please enter a character name on the home screen before saving.")
                else:
                    save_to_db(st.session_state.character_name.strip())
                    st.success("Saved to DB.")
        with col2:
            if st.button("Restart Story"):
                st.session_state.offline_segment = 0
                st.session_state.online_history = []
                safe_rerun()
        with col3:
            if st.button("Return to Home"):
                st.session_state.mode = None
                safe_rerun()

        # Adventure log
        if st.session_state.online_history:
            st.markdown("<div style='margin-top:18px;' class='parchment-box'><h3>Adventure Log</h3>" + "".join(f"<div>- {e}</div>" for e in st.session_state.online_history) + "</div>", unsafe_allow_html=True)