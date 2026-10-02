# ============================================================
# FORTNITE BOOTH V0.2
# Continuous vision + sports broadcast prototype
# ============================================================

import os
import io
import json
import time
import wave
import random
import base64
import tempfile
import threading
import winsound

from collections import deque
from datetime import datetime
from pathlib import Path

import mss
from PIL import Image
from openai import OpenAI

# keyboard is now OPTIONAL. The Booth no longer depends on hotkeys.
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except Exception:
    keyboard = None
    KEYBOARD_AVAILABLE = False


# ============================================================
# CONFIGURATION
# ============================================================

# Monitor containing Fortnite.
# 1 = first monitor, 2 = second monitor, etc.
MONITOR_NUMBER = 1

# Models
VISION_MODEL = "gpt-5.6-luna"
COMMENTARY_MODEL = "gpt-5.6-luna"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "cedar"

# Continuous local capture
CAPTURE_INTERVAL = 1.0        # one local screenshot per second
BUFFER_SECONDS = 15          # retain recent visual history in RAM

# Vision analysis cadence
ANALYSIS_INTERVAL = 8.0      # attempt a new analysis every 8 seconds
FRAME_OFFSETS = [8, 6, 4, 2, 0]

# Speaking cadence
MIN_COMMENTARY_GAP = 16.0
MAJOR_EVENT_MIN_GAP = 10.0
NORMAL_COMMENTARY_MIN = 30.0
NORMAL_COMMENTARY_MAX = 45.0
MAX_SILENCE = 55.0

# Image preparation
TEMPORAL_MAX_SIZE = (960, 540)
TEMPORAL_JPEG_QUALITY = 70
CROP_JPEG_QUALITY = 82

# Current duo partner.
# Change ONLY these three values when you switch partners.
TEAMMATE_NAME = "Lars"
TEAMMATE_GAMER_TAG = "LarsFoReal"
TEAMMATE_REAL_NAME = "Lars"

# For Lars weekends, use:
# TEAMMATE_NAME = "Lars"
# TEAMMATE_GAMER_TAG = "LarsFoReal"
# TEAMMATE_REAL_NAME = "Lars"

# Log folder stays out of your source code.
PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

SESSION_STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"booth_{SESSION_STAMP}.jsonl"

speech_file = Path(tempfile.gettempdir()) / "fortnite_booth.wav"


# ============================================================
# PLAYER / SEASON CONTEXT
# ============================================================

PLAYER_CONTEXT = f"""
BROADCAST PLAYERS

NEWB:
- Scot.
- The gameplay camera belongs to Newb by default.
- Most people call him Newb.
- Talks plenty of smack about enemies.
- Frequently worries about or runs low on ammunition.
- Can make strong plays and can also make questionable decisions.

{TEAMMATE_NAME.upper()}:
- {TEAMMATE_REAL_NAME}.
- Gamer tag: {TEAMMATE_GAMER_TAG}.
- Newb's duo teammate.
- Treat {TEAMMATE_NAME} as an independent competitor, not a sidekick.

CAMERA RULE:
The camera is Newb's POV unless EXPLICIT spectator-interface evidence proves
Newb has been eliminated and the game is spectating {TEAMMATE_NAME}.

Seeing {TEAMMATE_NAME}, the gamer tag {TEAMMATE_GAMER_TAG}, a teammate marker,
or a teammate silhouette in the world is evidence that the visible player is
Newb's teammate. It does NOT mean the camera belongs to {TEAMMATE_NAME}.
"""

SEASON_CONTEXT = """
CURRENT FORTNITE CONTEXT:
- Chapter 7, Season 4: Override.
- Zero Build.
- Use exact POI names when they are visibly shown by the game.
- Current-season locations include places such as Shaken Sanctuary,
  Cluster Coast, Sinister Strip, Reality's Reign, Geno's Machine,
  Green Hill Zone, Golden Grove, Wonkeeland, Pixel Polys,
  Stone Sanctum, The Battlewoods, Lifty Lodge, Heatwave Harbor,
  Sunken Shores and other named current-season locations.
- Do not identify an exact POI from scenery alone unless confidence is high.
"""


# ============================================================
# VISION RULES DISTILLED FROM THE REFERENCE SCREENSHOTS
# ============================================================

VISION_RULES = f"""
FORTNITE VISUAL / HUD RULES

GENERAL:
- Prefer UNKNOWN/null over guessing.
- Distinguish direct visual observations from inference.
- Use the chronological image sequence to infer motion and events.
- The newest frame is the authoritative frame for current HUD state.

POV / TEAMMATES:
- Default camera owner = NEWB.
- {TEAMMATE_NAME} visible in-world means the camera is NOT {TEAMMATE_NAME}'s.
- Teammates may appear as nameplates, colored markers, silhouettes/outlines
  through terrain, or normal player models.
- Only use camera_owner=TEAMMATE if explicit spectating UI proves it.

TOP-RIGHT HUD:
- Do not confuse Newb's personal eliminations with team eliminations.
- Personal eliminations, team eliminations and players remaining are separate.
- A storm countdown is not a match timer.
- The minimap can show storm, safe-zone boundary, player arrow and markers.

HEALTH / SHIELD:
- Newb's large bottom-left bars are Newb's state.
- The smaller teammate row above belongs to the teammate.
- Green = health.
- Blue = shield.
- Zero Build overshield is a separate temporary shield value.
- Storm damage reduces HEALTH, not normal shield.
- If exact values are unreadable, return null rather than inventing them.

STORM:
- Strong purple screen tint/rain plus storm effects is strong evidence of
  being inside the storm.
- "YOU ARE IN THE STORM RUN!" is direct confirmation.
- A bright storm boundary line separates storm from safe area.
- Purple minimap territory represents storm.
- Being near the boundary is not the same thing as being inside the storm.

AMMO / INVENTORY:
- Magazine ammo is NOT total ammunition.
- For the selected gun, distinguish:
  magazine_ammo = rounds currently loaded
  reserve_ammo = additional ammunition available
- Inventory tile ammo totals can differ from the magazine readout.
- Never say "only X bullets left" when X is merely magazine capacity.
- Five ordinary inventory slots are distinct from the pickaxe.
- Medkits, shield items and utility items should be identified only when clear.

HEALING:
- Holding/using a medkit with a countdown means medkit use.
- Medkits restore health.
- Small shield potions / minis and shield potions restore shield.
- Healing can be interrupted by combat or movement.
- Slurp-type splash/barrel effects may heal nearby teammates as well.

COMBAT:
- A floating damage number near an enemy is evidence of a confirmed hit.
- Muzzle flash plus falling magazine ammo indicates firing.
- A visibly ejecting magazine / reload animation indicates reloading.
- Red directional damage indicator, incoming tracer/beam, and falling health
  are evidence Newb is taking fire.
- Scoped circular sight = aiming down sights with a scoped weapon.
- A red/pink world ping may indicate an enemy marker; use surrounding UI/context.
- Kill-feed lines can directly identify knocks/eliminations by player name.
  Read them carefully; do not attribute another player's event to Newb.

DBNO / ELIMINATION / REZ:
- Red/downed health state plus crawling/downed posture indicates DBNO.
- A teammate red-cross/downed marker indicates teammate DBNO.
- A revive interaction displays a countdown while one teammate revives another.
- Fully eliminated players may require a reboot card / reboot van.
- Do not call DBNO a full elimination unless evidence supports elimination.

MATCH PHASE:
- Battle Bus: visible Battle Bus and "Space to Jump" / last-stop style UI.
- Dropping/gliding: airborne descent and prompts such as SKYDIVE / FREE FALL.
- Active match: normal ground gameplay HUD.
- DBNO: Newb downed but not fully eliminated.
- Spectating: explicit spectator UI after Newb is eliminated.
- Lobby / loading / match over should be classified separately.

WORLD INTERACTIONS:
- Blue/glowing special chest may be a rare chest.
- Loot burst after an opened chest indicates looting.
- Harvest weak-point target appears while striking harvestable objects.
- Waypoints show colored markers and distance.
- Exact POI entry text such as "ENTERED SHAKEN SANCTUARY" is high-confidence
  location evidence.

IMPORTANT:
Do not overfit to cosmetic skins, backpack appearance, weapon colors,
or season-specific effects unless the UI makes the meaning clear.
"""


# ============================================================
# COMMENTATOR PERSONA
# ============================================================

COMMENTATOR_INSTRUCTIONS = f"""
You are THE BOOTH, a fictional live television sports announcer covering
a Fortnite Zero Build duo match featuring Newb and {TEAMMATE_NAME}.

You combine:
1. PLAY-BY-PLAY when meaningful action is occurring.
2. COLOR COMMENTARY when the match is quieter.

The broadcast should feel like football/baseball/basketball-style coverage
applied seriously to Fortnite.

STYLE:
- Natural live sports-broadcast rhythm.
- Describe the meaningful action, not every visual detail.
- When combat changes quickly, lead with what just happened.
- Add former-player-style tactical insight when useful.
- Humor is occasional seasoning, never a requirement.
- Do not force a roast or punchline.
- Praise genuinely strong play.
- Criticize questionable decisions naturally when warranted.
- Build continuity and recurring storylines over the match.
- Sound engaged, knowledgeable and specific.
- Never imitate or claim to be a real announcer, actor or character.

IMPORTANT:
- Refer to Newb and {TEAMMATE_NAME} in third person.
- Never speak as though either player is talking directly to you.
- Never mention AI, models, screenshots, prompts, JSON or instructions.
- Never say "I can see".
- Never fabricate a kill, knock, damage value, ammo problem or tactical event.
- If the state is uncertain, talk about what is actually supported.
- Do not simply read every HUD number.
- Keep it suitable for a live gaming broadcast.

LENGTH:
Usually 1-2 sentences, about 10-40 words.
A major play may justify a slightly longer call, but stay concise.
"""

TTS_INSTRUCTIONS = """
Perform this as a veteran American television sports announcer covering
live action.

Use a confident, natural broadcast cadence.
During major action, increase urgency and energy without screaming.
During quieter color commentary, sound analytical and conversational.
Humor should sound incidental rather than like stand-up comedy.
Do not imitate any specific real person.
"""


# ============================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================

STATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "camera_owner": {
            "type": "string",
            "enum": ["NEWB", "TEAMMATE", "UNKNOWN"]
        },
        "match_phase": {
            "type": "string",
            "enum": [
                "LOBBY", "BATTLE_BUS", "DROPPING", "ACTIVE",
                "DBNO", "SPECTATING", "MATCH_OVER", "UNKNOWN"
            ]
        },
        "location_name": {
            "type": ["string", "null"]
        },
        "inside_storm": {
            "type": ["boolean", "null"]
        },
        "storm_edge_visible": {
            "type": ["boolean", "null"]
        },
        "activity": {
            "type": "string",
            "enum": [
                "QUIET", "ROTATING", "LOOTING", "HEALING", "COMBAT",
                "TAKING_FIRE", "REVIVING", "DBNO", "DROPPING",
                "HARVESTING", "UNKNOWN"
            ]
        },
        "newb_health": {
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 100
        },
        "newb_shield": {
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 100
        },
        "newb_overshield": {
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 50
        },
        "teammate_status": {
            "type": "string",
            "enum": ["ALIVE", "DBNO", "ELIMINATED", "UNKNOWN"]
        },
        "teammate_visible": {
            "type": ["boolean", "null"]
        },
        "personal_eliminations": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "team_eliminations": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "players_remaining": {
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": 100
        },
        "selected_weapon": {
            "type": ["string", "null"]
        },
        "magazine_ammo": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "reserve_ammo": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "healing_action": {
            "type": ["string", "null"]
        },
        "confirmed_damage_dealt": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "newb_took_damage": {
            "type": ["boolean", "null"]
        },
        "enemies_visible": {
            "type": ["integer", "null"],
            "minimum": 0
        },
        "sequence_summary": {
            "type": "string"
        },
        "major_event": {
            "type": ["string", "null"]
        },
        "importance": {
            "type": "integer",
            "minimum": 0,
            "maximum": 5
        },
        "confidence": {
            "type": "string",
            "enum": ["LOW", "MEDIUM", "HIGH"]
        }
    },
    "required": [
        "camera_owner",
        "match_phase",
        "location_name",
        "inside_storm",
        "storm_edge_visible",
        "activity",
        "newb_health",
        "newb_shield",
        "newb_overshield",
        "teammate_status",
        "teammate_visible",
        "personal_eliminations",
        "team_eliminations",
        "players_remaining",
        "selected_weapon",
        "magazine_ammo",
        "reserve_ammo",
        "healing_action",
        "confirmed_damage_dealt",
        "newb_took_damage",
        "enemies_visible",
        "sequence_summary",
        "major_event",
        "importance",
        "confidence"
    ]
}


# ============================================================
# OPENAI SETUP
# ============================================================

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print()
    print("ERROR: OPENAI_API_KEY was not found in this PowerShell session.")
    print("Open a NEW PowerShell window after setting the Windows variable.")
    print()
    raise SystemExit(1)

client = OpenAI()

print("[STARTUP] OpenAI API key found.")


# ============================================================
# SHARED STATE
# ============================================================

# Each buffer entry = (monotonic_timestamp, PIL_image)
frame_buffer = deque(maxlen=BUFFER_SECONDS + 5)
frame_lock = threading.Lock()

latest_state = None
previous_state = None
state_lock = threading.Lock()

recent_comments = deque(maxlen=6)
comment_lock = threading.Lock()

analysis_lock = threading.Lock()
commentary_lock = threading.Lock()

stop_event = threading.Event()

session_start = time.monotonic()
last_commentary_time = session_start - 20.0
next_normal_commentary_gap = random.uniform(
    NORMAL_COMMENTARY_MIN,
    NORMAL_COMMENTARY_MAX
)


# ============================================================
# LOGGING
# ============================================================

def log_event(event_type, payload):
    record = {
        "wall_time": datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        "payload": payload
    }

    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as error:
        print(f"[LOG] Could not write log: {error}")


# ============================================================
# IMAGE HELPERS
# ============================================================

def pil_to_data_uri(image, max_size=None, quality=75):
    img = image.copy()

    if max_size is not None:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True
    )

    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def crop_by_fraction(image, left, top, right, bottom):
    w, h = image.size

    box = (
        int(left * w),
        int(top * h),
        int(right * w),
        int(bottom * h)
    )

    return image.crop(box)


# ============================================================
# CONTINUOUS SCREEN CAPTURE
# ============================================================

def capture_loop():
    print(
        f"[CAPTURE] Starting continuous capture: "
        f"1 frame every {CAPTURE_INTERVAL:.1f}s"
    )

    try:
        with mss.MSS() as sct:
            if MONITOR_NUMBER >= len(sct.monitors):
                raise ValueError(
                    f"Monitor {MONITOR_NUMBER} does not exist. "
                    f"Available monitors: 1 through {len(sct.monitors) - 1}."
                )

            monitor = sct.monitors[MONITOR_NUMBER]
            next_capture = time.monotonic()

            while not stop_event.is_set():
                now = time.monotonic()

                if now < next_capture:
                    time.sleep(min(0.05, next_capture - now))
                    continue

                shot = sct.grab(monitor)

                image = Image.frombytes(
                    "RGB",
                    shot.size,
                    shot.rgb
                )

                with frame_lock:
                    frame_buffer.append((now, image))

                next_capture += CAPTURE_INTERVAL

                # If Windows was busy for a long time, don't attempt to
                # "catch up" by taking many screenshots instantly.
                if next_capture < now - CAPTURE_INTERVAL:
                    next_capture = now + CAPTURE_INTERVAL

    except Exception as error:
        print(f"[CAPTURE ERROR] {error}")
        log_event("capture_error", {"error": str(error)})
        stop_event.set()


# ============================================================
# SELECT TEMPORAL FRAMES FROM ROLLING BUFFER
# ============================================================

def get_analysis_frames():
    with frame_lock:
        snapshot = list(frame_buffer)

    if not snapshot:
        return None

    newest_time = snapshot[-1][0]

    # Need enough temporal history for the oldest requested frame.
    oldest_required = max(FRAME_OFFSETS)

    if newest_time - snapshot[0][0] < oldest_required - 0.5:
        return None

    selected = []

    for offset in FRAME_OFFSETS:
        target = newest_time - offset
        timestamp, image = min(
            snapshot,
            key=lambda entry: abs(entry[0] - target)
        )
        selected.append((offset, timestamp, image.copy()))

    return selected


# ============================================================
# BUILD VISION INPUT
# ============================================================

def build_vision_content(selected_frames, prior_state):
    content = []

    prior_state_text = (
        json.dumps(prior_state, indent=2)
        if prior_state is not None
        else "No prior state. This is the first analysis."
    )

    prompt = f"""
{PLAYER_CONTEXT}

{SEASON_CONTEXT}

{VISION_RULES}

TASK:
You are the visual state extractor for a live sports broadcast.

You receive FIVE chronological full gameplay frames covering approximately
the last eight seconds, followed by high-detail crops from the newest frame.

FRAME ORDER:
T-8 seconds
T-6 seconds
T-4 seconds
T-2 seconds
NOW

PREVIOUS EXTRACTED STATE:
{prior_state_text}

Determine:
1. What happened across the sequence.
2. The most reliable current game state in the newest frame.
3. Whether a meaningful event occurred.
4. How important it would be to a live sports announcer.

IMPORTANCE:
0 = nothing useful changed
1 = quiet/background state
2 = mildly interesting development
3 = meaningful tactical development
4 = major action/event worth prompt commentary
5 = exceptional/clutch/knock/elimination/high-danger event

Return null for numeric or factual fields that cannot be read reliably.
Do not invent values merely because a nearby number exists.
"""

    content.append({
        "type": "input_text",
        "text": prompt
    })

    # Chronological full frames.
    for offset, _, image in selected_frames:
        content.append({
            "type": "input_text",
            "text": f"FULL FRAME: T-{offset} seconds"
        })
        content.append({
            "type": "input_image",
            "image_url": pil_to_data_uri(
                image,
                max_size=TEMPORAL_MAX_SIZE,
                quality=TEMPORAL_JPEG_QUALITY
            ),
            "detail": "low"
        })

    newest = selected_frames[-1][2]

    # HUD / context crops from NOW.
    crops = [
        (
            "NOW - TOP RIGHT HUD / MINIMAP",
            crop_by_fraction(newest, 0.77, 0.00, 1.00, 0.31)
        ),
        (
            "NOW - BOTTOM LEFT PLAYER / TEAM HUD",
            crop_by_fraction(newest, 0.00, 0.69, 0.35, 1.00)
        ),
        (
            "NOW - BOTTOM RIGHT INVENTORY / AMMO / RESOURCES",
            crop_by_fraction(newest, 0.56, 0.66, 1.00, 1.00)
        )
    ]

    for label, crop in crops:
        content.append({
            "type": "input_text",
            "text": label
        })
        content.append({
            "type": "input_image",
            "image_url": pil_to_data_uri(
                crop,
                max_size=(1200, 800),
                quality=CROP_JPEG_QUALITY
            ),
            "detail": "high"
        })

    return content


# ============================================================
# VISION ANALYSIS
# ============================================================

def analyze_once():
    global latest_state, previous_state

    if not analysis_lock.acquire(blocking=False):
        print("[ANALYSIS] Previous analysis still busy; skipping this cycle.")
        log_event("analysis_skipped_busy", {})
        return

    try:
        selected_frames = get_analysis_frames()

        if selected_frames is None:
            print("[ANALYSIS] Buffer warming up...")
            return

        with state_lock:
            prior = latest_state.copy() if latest_state else None

        print()
        print("==================================================")
        print("                VISION ANALYSIS")
        print("==================================================")

        start = time.perf_counter()

        content = build_vision_content(selected_frames, prior)

        response = client.responses.create(
            model=VISION_MODEL,
            reasoning={"effort": "none"},
            input=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "fortnite_game_state",
                    "schema": STATE_SCHEMA,
                    "strict": True
                }
            },
            max_output_tokens=900
        )

        elapsed = time.perf_counter() - start
        state = json.loads(response.output_text)

        with state_lock:
            previous_state = latest_state
            latest_state = state

        print(
            f"[ANALYSIS] Complete in {elapsed:.1f}s | "
            f"phase={state['match_phase']} | "
            f"activity={state['activity']} | "
            f"importance={state['importance']} | "
            f"confidence={state['confidence']}"
        )
        print(f"[ANALYSIS] {state['sequence_summary']}")

        if state["major_event"]:
            print(f"[EVENT] {state['major_event']}")

        log_event(
            "analysis",
            {
                "latency_seconds": round(elapsed, 3),
                "state": state
            }
        )

        maybe_request_commentary(state)

    except Exception as error:
        print()
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("VISION ANALYSIS ERROR")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(error)
        print()
        log_event("analysis_error", {"error": str(error)})

    finally:
        analysis_lock.release()


# ============================================================
# COMMENTARY SCHEDULER
# ============================================================

def phase_allows_commentary(state):
    return state["match_phase"] in {
        "BATTLE_BUS",
        "DROPPING",
        "ACTIVE",
        "DBNO",
        "SPECTATING"
    }


def maybe_request_commentary(state):
    global next_normal_commentary_gap

    if not phase_allows_commentary(state):
        return

    now = time.monotonic()
    since_last = now - last_commentary_time
    importance = state["importance"]

    mode = None
    reason = None

    # High-value event override.
    if importance >= 4 and since_last >= MAJOR_EVENT_MIN_GAP:
        mode = "PLAY_BY_PLAY"
        reason = "major_event"

    # Normal sports-broadcast cadence.
    elif (
        since_last >= next_normal_commentary_gap
        and since_last >= MIN_COMMENTARY_GAP
    ):
        if importance >= 3 or state["activity"] in {
            "COMBAT", "TAKING_FIRE", "DBNO", "REVIVING"
        }:
            mode = "PLAY_BY_PLAY"
        else:
            mode = "COLOR"

        reason = "normal_cadence"

    # Prevent dead air from becoming excessive.
    elif (
        since_last >= MAX_SILENCE
        and since_last >= MIN_COMMENTARY_GAP
    ):
        mode = "COLOR"
        reason = "max_silence"

    if mode is None:
        return

    request_commentary(
        state=state,
        mode=mode,
        reason=reason,
        focus_hint=None,
        forced=False
    )


# ============================================================
# COMMENTARY GENERATION
# ============================================================

def request_commentary(
    state,
    mode,
    reason,
    focus_hint=None,
    forced=False
):
    if not commentary_lock.acquire(blocking=False):
        print("[BOOTH] Commentary channel busy; not queuing stale speech.")
        log_event(
            "commentary_skipped_busy",
            {
                "mode": mode,
                "reason": reason,
                "forced": forced
            }
        )
        return

    thread = threading.Thread(
        target=commentary_worker,
        args=(state, mode, reason, focus_hint, forced),
        daemon=True
    )
    thread.start()


def commentary_worker(
    state,
    mode,
    reason,
    focus_hint,
    forced
):
    global last_commentary_time, next_normal_commentary_gap

    try:
        with state_lock:
            prior = previous_state.copy() if previous_state else None

        with comment_lock:
            recent = list(recent_comments)

        recent_text = (
            "\n".join(f"- {x}" for x in recent)
            if recent
            else "None yet."
        )

        focus_text = (
            focus_hint
            if focus_hint
            else "No special producer focus. Cover the most broadcast-worthy point."
        )

        prompt = f"""
{PLAYER_CONTEXT}

CURRENT STRUCTURED GAME STATE:
{json.dumps(state, indent=2)}

PREVIOUS STRUCTURED GAME STATE:
{json.dumps(prior, indent=2) if prior else "None"}

RECENT BOOTH LINES:
{recent_text}

BROADCAST MODE:
{mode}

PRODUCER FOCUS:
{focus_text}

Write the next live broadcast line.

PLAY_BY_PLAY:
Lead with the meaningful immediate action or change. Tactical analysis may
follow briefly.

COLOR:
Use the current situation to make a concise tactical observation, assess
positioning/resources/risk, or develop a player storyline. Humor is optional.

Do not repeat a recent line.
Do not invent events that are absent from the structured state.
Return ONLY the spoken commentary text.
"""

        print()
        print("--------------------------------------------------")
        print(f"[BOOTH] Generating {mode} commentary...")
        print("--------------------------------------------------")

        start = time.perf_counter()

        response = client.responses.create(
            model=COMMENTARY_MODEL,
            reasoning={"effort": "none"},
            instructions=COMMENTATOR_INSTRUCTIONS,
            input=prompt,
            max_output_tokens=140
        )

        commentary = response.output_text.strip()
        generation_elapsed = time.perf_counter() - start

        if not commentary:
            print("[BOOTH] Empty commentary response.")
            return

        print(f"THE BOOTH: {commentary}")
        print(
            f"[BOOTH] Text ready in {generation_elapsed:.1f}s "
            f"(reason={reason})."
        )

        with comment_lock:
            recent_comments.append(commentary)

        # Count cadence from the moment commentary is committed to speech.
        last_commentary_time = time.monotonic()
        next_normal_commentary_gap = random.uniform(
            NORMAL_COMMENTARY_MIN,
            NORMAL_COMMENTARY_MAX
        )

        log_event(
            "commentary",
            {
                "mode": mode,
                "reason": reason,
                "forced": forced,
                "focus_hint": focus_hint,
                "text_generation_seconds": round(generation_elapsed, 3),
                "text": commentary
            }
        )

        speak_commentary(commentary)

    except Exception as error:
        print()
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("COMMENTARY ERROR")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(error)
        print()
        log_event("commentary_error", {"error": str(error)})

    finally:
        commentary_lock.release()


# ============================================================
# TEXT TO SPEECH
# Proven V0 PCM -> WAV path
# ============================================================

def speak_commentary(text):
    print("[BOOTH] Announcer is heading to microphone...")

    start = time.perf_counter()

    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        instructions=TTS_INSTRUCTIONS,
        response_format="pcm",
        stream_format="audio"
    )

    pcm_bytes = response.content

    with wave.open(str(speech_file), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(pcm_bytes)

    audio_ready_elapsed = time.perf_counter() - start

    print(
        f"[BOOTH] Audio ready in {audio_ready_elapsed:.1f}s | "
        f"PCM bytes={len(pcm_bytes):,}"
    )

    log_event(
        "audio_ready",
        {
            "seconds": round(audio_ready_elapsed, 3),
            "pcm_bytes": len(pcm_bytes)
        }
    )

    # This blocks ONLY the commentary thread.
    # Continuous capture and vision analysis continue in parallel.
    winsound.PlaySound(
        str(speech_file),
        winsound.SND_FILENAME
    )


# ============================================================
# OPTIONAL MANUAL PRODUCER OVERRIDES
# ============================================================

def get_current_state_copy():
    with state_lock:
        return latest_state.copy() if latest_state else None


def manual_commentary(focus_hint, mode="COLOR"):
    state = get_current_state_copy()

    if state is None:
        print("[HOTKEY] No extracted state yet. Wait for first analysis.")
        return

    request_commentary(
        state=state,
        mode=mode,
        reason="manual_hotkey",
        focus_hint=focus_hint,
        forced=True
    )


def setup_hotkeys():
    if not KEYBOARD_AVAILABLE:
        print("[HOTKEYS] keyboard package unavailable; continuous mode still works.")
        return

    try:
        keyboard.add_hotkey(
            "f8",
            lambda: manual_commentary(
                "Producer requests commentary on the current situation.",
                "COLOR"
            )
        )

        keyboard.add_hotkey(
            "f9",
            lambda: manual_commentary(
                "Focus on Newb's current play or decision.",
                "COLOR"
            )
        )

        keyboard.add_hotkey(
            "f10",
            lambda: manual_commentary(
                f"Focus on {TEAMMATE_NAME}. This does NOT change camera ownership.",
                "COLOR"
            )
        )

        keyboard.add_hotkey(
            "f11",
            lambda: manual_commentary(
                "Treat this as an important/clutch moment. Call the immediate action.",
                "PLAY_BY_PLAY"
            )
        )

        keyboard.add_hotkey(
            "ctrl+shift+q",
            stop_event.set
        )

        print("[HOTKEYS] Optional producer overrides registered.")

    except Exception as error:
        print(f"[HOTKEYS] Could not register hotkeys: {error}")
        print("[HOTKEYS] Continuous Booth mode will still operate normally.")


# ============================================================
# ANALYSIS SCHEDULER
# No backlog: if a model call is still busy, that cycle is skipped.
# ============================================================

def analysis_scheduler_loop():
    next_analysis = time.monotonic() + max(FRAME_OFFSETS) + 1.0

    while not stop_event.is_set():
        now = time.monotonic()

        if now >= next_analysis:
            if analysis_lock.locked():
                print("[ANALYSIS] Busy at scheduled tick; skipping stale cycle.")
                log_event("analysis_skipped_busy", {})
            else:
                threading.Thread(
                    target=analyze_once,
                    daemon=True
                ).start()

            # Fixed observation clock. Never queue missed analyses.
            next_analysis += ANALYSIS_INTERVAL

            if next_analysis < now:
                next_analysis = now + ANALYSIS_INTERVAL

        time.sleep(0.10)


# ============================================================
# STATUS HEARTBEAT
# ============================================================

def heartbeat_loop():
    while not stop_event.wait(60):
        with frame_lock:
            buffer_count = len(frame_buffer)

        state = get_current_state_copy()

        state_summary = (
            f"{state['match_phase']}/{state['activity']}"
            if state
            else "waiting-for-first-analysis"
        )

        print(
            f"[HEARTBEAT] Booth alive | "
            f"buffer={buffer_count} frames | "
            f"state={state_summary}"
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("==================================================")
    print("              FORTNITE BOOTH V0.2")
    print("==================================================")
    print()
    print(f"Teammate: {TEAMMATE_NAME} ({TEAMMATE_GAMER_TAG})")
    print(f"Capture: 1 frame every {CAPTURE_INTERVAL:.1f}s")
    print(
        f"Vision: 5 frames over ~8 seconds, "
        f"analysis every {ANALYSIS_INTERVAL:.0f}s"
    )
    print(
        f"Normal commentary target: "
        f"{NORMAL_COMMENTARY_MIN:.0f}-{NORMAL_COMMENTARY_MAX:.0f}s"
    )
    print(f"Runtime log: {LOG_FILE}")
    print()
    print("OPTIONAL HOTKEYS")
    print("F8  = Force general commentary")
    print("F9  = Focus next line on Newb")
    print(f"F10 = Focus next line on {TEAMMATE_NAME}")
    print("F11 = Force clutch/play-by-play call")
    print("CTRL+SHIFT+Q = Shut down")
    print()
    print("The Booth no longer depends on hotkeys.")
    print("Fortnite can remain in the foreground.")
    print()

    setup_hotkeys()

    threads = [
        threading.Thread(
            target=capture_loop,
            name="capture",
            daemon=True
        ),
        threading.Thread(
            target=analysis_scheduler_loop,
            name="analysis_scheduler",
            daemon=True
        ),
        threading.Thread(
            target=heartbeat_loop,
            name="heartbeat",
            daemon=True
        )
    ]

    for thread in threads:
        thread.start()

    try:
        while not stop_event.wait(0.5):
            pass
    except KeyboardInterrupt:
        print()
        print("[SHUTDOWN] Ctrl+C received.")
        stop_event.set()

    print("[SHUTDOWN] Waiting briefly for threads...")
    time.sleep(0.5)
    print("[SHUTDOWN] Fortnite Booth stopped.")


if __name__ == "__main__":
    main()
