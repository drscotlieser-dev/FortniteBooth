import os
import base64
import io
import tempfile
import threading
import time
import winsound

from collections import deque
from pathlib import Path

import keyboard
import mss
import wave

from PIL import Image
from openai import OpenAI
print("### BOOTH VERSION 2 - WAV TEST ###")

# ============================================================
# CONFIGURATION
# ============================================================

# 1 = first monitor
# 2 = second monitor
#
# If Fortnite is on your main monitor, leave this at 1.
MONITOR_NUMBER = 1

# Fast / inexpensive vision model
VISION_MODEL = "gpt-5.6-luna"

# OpenAI text-to-speech model
TTS_MODEL = "gpt-4o-mini-tts"

# OpenAI recommends Cedar and Marin among its higher-quality voices.
TTS_VOICE = "cedar"


# ============================================================
# PLAYER INFORMATION
# ============================================================

PLAYER_CONTEXT = """
Tonight's Fortnite Zero Build squad:

NEWBDADDY:
- Scot.
- Aggressive player.
- Loves vehicles.
- Often willing to attempt questionable plays.
- Capable of very good plays, but absolutely fair game for roasting.

ZELDA:
- Newbdaddy's teammate tonight.
- Treat Zelda as an independent competitor, not as a sidekick.
- Learn apparent gameplay tendencies from screenshots and supplied event cues.

The audience is watching a live gaming broadcast.
"""


# ============================================================
# COMMENTATOR PERSONALITY
# ============================================================

COMMENTATOR_INSTRUCTIONS = """
You are THE BOOTH, a fictional television sports color commentator
covering a live Fortnite Zero Build broadcast.

You are NOT the play-by-play announcer.

Your job is to provide short, insightful, funny COLOR COMMENTARY
when the producer sends the broadcast to you.

STYLE:

- Dry television sports-commentator delivery.
- Confident analysis of ridiculous situations.
- Treat stupid Fortnite decisions with the seriousness of elite professional sports.
- Clever rather than loud.
- Sarcasm is welcome.
- Occasional absurd fake statistics are welcome when obviously comedic.
- Roast players when they deserve it.
- Praise genuinely excellent plays when appropriate.
- Develop running storylines and callbacks across the broadcast.
- Sound like a veteran analyst who has somehow studied Fortnite for thirty years.
- Never explain a joke.
- Never laugh at your own joke.

IMPORTANT:

- Refer to Newbdaddy and Zelda in third person.
- Never respond as though either player is talking directly to you.
- Never say "I can see".
- Never mention being an AI.
- Never mention screenshots.
- Never mention prompts or instructions.
- Do not merely read information visible on the HUD.
- Do not make up important factual game events you cannot infer.
- Comedic fake statistics are allowed.
- Do not imitate or claim to be a real sports commentator, actor, or movie character.

LENGTH:

Usually ONE sentence.

Two short sentences are acceptable if genuinely better.

Target approximately 8 to 35 words.

The spoken commentary should generally last about 3 to 9 seconds.

QUALITY TEST:

Generic narration is a failure.

A clever observation, roast, running gag, or piece of fake sports analysis
that could make viewers anticipate the next trip to The Booth is a success.
"""


# ============================================================
# VOICE PERFORMANCE
# ============================================================

TTS_INSTRUCTIONS = """
Perform this as a veteran American television sports color commentator.

Use a dry, understated, confident delivery.

Sound experienced and analytical.

There should be a faint sense that the commentator finds the situation
ridiculous, but never laugh at your own joke.

Use natural sports-broadcast rhythm.

Use a little additional emphasis on the punch line or final phrase
when appropriate.

Do not sound like an AI assistant.

Do not imitate any specific real person.
"""


# ============================================================
# CHECK API KEY
# ============================================================

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print()
    print("ERROR: OPENAI_API_KEY was not found.")
    print("Close VS Code completely, reopen it, and try again.")
    print()
    raise SystemExit


print("[STARTUP] OpenAI API key found.")


# ============================================================
# OPENAI CLIENT
# ============================================================

client = OpenAI()


# ============================================================
# MEMORY
# ============================================================

# Prevent two Booth calls from talking over each other.
booth_lock = threading.Lock()

# Preserve recent comments so the AI can make callbacks.
recent_comments = deque(maxlen=6)

# Temporary WAV file used for announcer speech.
speech_file = Path(tempfile.gettempdir()) / "fortnite_booth.wav"


# ============================================================
# SCREEN CAPTURE
# ============================================================

def capture_screen():
    """
    Capture the selected monitor.

    Resize and compress it before sending it to OpenAI.
    """

    with mss.MSS() as sct:

        if MONITOR_NUMBER >= len(sct.monitors):
            raise ValueError(
                f"Monitor {MONITOR_NUMBER} does not exist. "
                f"Available monitor numbers are 1 through {len(sct.monitors) - 1}."
            )

        monitor = sct.monitors[MONITOR_NUMBER]

        shot = sct.grab(monitor)

        image = Image.frombytes(
            "RGB",
            shot.size,
            shot.rgb
        )

        # We don't need to send a native 1440p/4K frame.
        # Smaller image = lower upload time and lower cost.
        image.thumbnail((1280, 720))

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=75,
            optimize=True
        )

        encoded_image = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        return f"data:image/jpeg;base64,{encoded_image}"


# ============================================================
# GENERATE COMMENTARY
# ============================================================

def generate_commentary(event_hint):

    print("[BOOTH] Capturing screen...")

    screenshot = capture_screen()

    if recent_comments:

        previous_comments = "\n".join(
            f"- {comment}"
            for comment in recent_comments
        )

    else:

        previous_comments = "None. This is the first trip to The Booth."


    producer_prompt = f"""
{PLAYER_CONTEXT}

The broadcast producer has just sent the coverage to The Booth.

PRODUCER EVENT CUE:

{event_hint}


RECENT BOOTH COMMENTARY:

{previous_comments}


Examine the current Fortnite image.

The producer cue explains WHY commentary was requested.

The image provides visual context.

Give the single best short color-commentary line for this moment.

Prefer a specific funny observation over generic Fortnite narration.

Do not repeat a previous joke unless you are intentionally turning it
into a running gag.
"""

    print("[BOOTH] Reviewing the tape...")

    start_time = time.perf_counter()

    response = client.responses.create(

        model=VISION_MODEL,

        reasoning={
            "effort": "none"
        },

        instructions=COMMENTATOR_INSTRUCTIONS,

        input=[
            {
                "role": "user",

                "content": [

                    {
                        "type": "input_text",
                        "text": producer_prompt
                    },

                    {
                        "type": "input_image",
                        "image_url": screenshot,
                        "detail": "auto"
                    }
                ]
            }
        ],

        max_output_tokens=100
    )

    elapsed = time.perf_counter() - start_time

    commentary = response.output_text.strip()

    print(
        f"[BOOTH] Commentary generated in {elapsed:.1f} seconds."
    )

    return commentary


# ============================================================
# GENERATE + PLAY SPEECH
# ============================================================
def speak_commentary(text):

    print("[BOOTH] Announcer is heading to microphone...")

    start_time = time.perf_counter()

    # Ask OpenAI for RAW PCM audio instead of a streaming-style WAV.
    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text,
        instructions=TTS_INSTRUCTIONS,
        response_format="pcm",
        stream_format="audio"
    )

    # Grab the raw PCM bytes returned by OpenAI.
    pcm_bytes = response.content

    print(
        f"[BOOTH] Raw PCM size: {len(pcm_bytes):,} bytes."
    )

    # Build a NORMAL Windows-compatible WAV file ourselves.
    #
    # OpenAI PCM:
    # - mono
    # - 16-bit
    # - 24,000 Hz
    with wave.open(str(speech_file), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)       # 16-bit audio = 2 bytes
        wav_file.setframerate(24000)
        wav_file.writeframes(pcm_bytes)

    elapsed = time.perf_counter() - start_time

    print(
        f"[BOOTH] Voice generated in {elapsed:.1f} seconds."
    )

    # Verify the WAV we just created.
    with wave.open(str(speech_file), "rb") as wav_file:

        print(
            "[BOOTH] WAV verified:"
            f" channels={wav_file.getnchannels()},"
            f" rate={wav_file.getframerate()},"
            f" width={wav_file.getsampwidth()},"
            f" frames={wav_file.getnframes()}"
        )

    print("[BOOTH] Playing commentary...")

    winsound.PlaySound(
        str(speech_file),
        winsound.SND_FILENAME
    )

# ============================================================
# COMPLETE BOOTH SEQUENCE
# ============================================================

def booth(event_hint):

    # If the Booth is already speaking or generating a response,
    # ignore another button press.
    if not booth_lock.acquire(blocking=False):

        print()
        print("[BOOTH] Already handling a previous call.")
        print()

        return


    try:

        print()
        print("==============================================")
        print("             GOING TO THE BOOTH")
        print("==============================================")

        total_start = time.perf_counter()


        commentary = generate_commentary(event_hint)


        if not commentary:

            print("[BOOTH] No commentary was returned.")
            return


        print()
        print("----------------------------------------------")
        print(f"THE BOOTH: {commentary}")
        print("----------------------------------------------")
        print()


        # Save this commentary for future callbacks.
        recent_comments.append(commentary)


        speak_commentary(commentary)


        total_elapsed = time.perf_counter() - total_start

        print()
        print(
            f"[BOOTH] Complete turnaround: "
            f"{total_elapsed:.1f} seconds."
        )
        print()


    except Exception as error:

        print()
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("BOOTH ERROR")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print()
        print(error)
        print()


    finally:

        booth_lock.release()


# ============================================================
# BACKGROUND TRIGGER
# ============================================================

def trigger(event_hint):

    thread = threading.Thread(

        target=booth,

        args=(event_hint,),

        daemon=True
    )

    thread.start()


# ============================================================
# HOTKEYS
# ============================================================

# F8
#
# Something happened.
# Let the AI decide what deserves commentary.

keyboard.add_hotkey(

    "f8",

    lambda: trigger(
        """
        General commentary.

        Something interesting, funny, strange, or noteworthy
        has just happened.

        Determine the best observation from the current scene.
        """
    )
)


# F9
#
# Scot screwed up.

keyboard.add_hotkey(

    "f9",

    lambda: trigger(
        """
        NEWBDADDY MOMENT.

        Newbdaddy has just made a funny, questionable,
        embarrassing, unnecessarily aggressive, or strategically
        dubious decision.

        Roast him if the situation supports it.
        """
    )
)


# F10
#
# Zelda did something notable.

keyboard.add_hotkey(

    "f10",

    lambda: trigger(
        """
        ZELDA MOMENT.

        Zelda has just done something noteworthy.

        Analyze what appears to be happening and give appropriate
        color commentary.

        It may be praise, criticism, absurd analysis, or a developing
        storyline depending on the situation.
        """
    )
)


# F11
#
# Serious / clutch mode.

keyboard.add_hotkey(

    "f11",

    lambda: trigger(
        """
        IMPORTANT COMPETITIVE MOMENT.

        This appears to be a legitimately important or clutch part
        of the match.

        Increase the seriousness and sports-broadcast intensity.

        Humor is still allowed, but do not undermine a genuinely
        impressive moment.
        """
    )
)


# ============================================================
# STARTUP MESSAGE
# ============================================================

print()
print("==============================================")
print("              THE BOOTH")
print("==============================================")
print()
print("SYSTEM STATUS: ONLINE")
print()
print("F8  = General Booth commentary")
print("F9  = Roast Newbdaddy")
print("F10 = Zelda moment")
print("F11 = Clutch / important moment")
print()
print("CTRL + SHIFT + Q = Shut down")
print()
print("Waiting for producer...")
print()


# Keep program alive until shutdown hotkey.
keyboard.wait("ctrl+shift+q")


print()
print("The Booth has left the building.")
print()