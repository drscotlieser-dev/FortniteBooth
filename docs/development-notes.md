# Fortnite Booth — Development Notes

This document records meaningful prototype discoveries, design decisions, technical problems, and solutions.

It is intentionally not a complete diary of every debugging step.

---

## V0 — Manual Producer Prototype

### Initial Goal

The original concept was an AI color commentator that could observe Fortnite gameplay and provide sports-broadcast-style commentary during a livestream.

Earlier experiments with general-purpose AI screen sharing exposed three major problems:

1. Difficulty maintaining awareness of a rapidly changing game environment.
2. Player voice chat being interpreted as conversation directed at the AI.
3. Long-running multimodal sessions becoming unreliable or timing out.

### Architectural Decision

Rather than making the AI continuously watch and listen to the entire stream, V0 uses a producer-driven architecture.

The AI receives:

* A gameplay screenshot
* A short producer event cue
* Recent Booth commentary for limited continuity

The AI does **not** receive:

* Player microphone audio
* Discord voice chat
* Fortnite voice chat

This prevents normal player conversation from accidentally triggering or steering the commentator.

---

## Producer Controls

The first prototype uses global hotkeys:

* `F8` — general commentary
* `F9` — Newbdaddy moment / roast
* `F10` — Zelda moment
* `F11` — important or clutch moment

The producer cue supplements the screenshot rather than requiring vision alone to determine why a moment was noteworthy.

---

## Commentary Memory

V0 retains a small number of recent Booth comments in memory during the current Python session.

This allows the model to make callbacks and begin developing recurring jokes without requiring a continuously open multimodal conversation.

The history is currently lost when the program exits.

---

## Windows Audio Playback Issue

### Symptom

The OpenAI speech endpoint successfully generated audio, but Windows playback produced only a beep.

Initial inspection showed that the generated file had a valid WAV/RIFF signature.

However, Python's `wave` module reported:

```text
channels=1
rate=24000
sample_width=2
frames=2147483647
compression=NONE
```

The frame count was clearly invalid for a short piece of commentary.

### Cause

The returned WAV used a streaming-style placeholder length rather than a finalized frame count that Windows' simple WAV playback path handled correctly.

The file therefore looked superficially like a valid WAV while still being unsuitable for the chosen Windows playback mechanism.

### Solution

The speech request was changed to request raw PCM audio.

Python then creates the WAV container itself using:

* 1 channel
* 16-bit samples
* 24,000 Hz sample rate

The resulting WAV contains a normal finalized frame count and plays correctly through Windows.

### Result

After the PCM-to-WAV conversion:

* Generated speech played successfully through the headset.
* TikTok LIVE Studio also captured the commentary through the existing desktop/system audio path.

This avoided requiring a virtual audio cable for the first prototype.

---

## Early Latency Observations

Initial successful tests showed that latency is distributed across two major API operations:

1. Screenshot interpretation and commentary generation
2. Speech generation

A displayed "complete turnaround" time in early V0 also included the duration of the spoken commentary because WAV playback was synchronous.

Future instrumentation should separately measure:

* Hotkey press → text commentary ready
* Hotkey press → generated audio ready
* Hotkey press → first spoken audio
* Spoken audio duration

This distinction matters because the viewer's perceived delay is the time until speech begins, not the time until playback finishes.

---

## First Live Gameplay Test

The first gameplay test demonstrated:

* Useful contextual comedy
* Successful commentary generation
* Working stream audio capture
* Noticeable screenshot-timing limitations
* Noticeable but potentially manageable latency

The single-frame capture occasionally risks showing only the aftermath of an event.

This directly motivates V1.

---

## Planned V1 — Rolling Visual Replay Buffer

Instead of capturing only the frame present when a producer presses a hotkey, V1 should continuously retain a small number of recent screenshots in local memory.

Example:

```text
T - 3.0 seconds
T - 2.0 seconds
T - 1.0 second
T = current frame
```

No API request is required while maintaining this local buffer.

When a producer triggers The Booth, selected recent frames can be submitted together so the model can reason about:

```text
setup → action → result → aftermath
```

rather than only the final state.

The main goal of V1 is improved temporal understanding without yet introducing full continuous video analysis.

---

## Longer-Term Direction

Possible later development includes:

* Automatic detection of selected HUD state changes
* Automatic triggering for high-value events
* Session statistics
* Player-specific tendencies
* Persistent broadcast storylines
* Improved audio control and ducking
* Stream overlays indicating that The Booth is reviewing a play
* Lower-latency realtime model architecture
* Logic governing when the commentator should remain silent

A central design principle is that selective commentary is likely more entertaining than continuous AI narration.

The Booth should behave like a broadcast personality, not like an accessibility description of every frame.
