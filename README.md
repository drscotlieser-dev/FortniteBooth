# Fortnite Booth

**Fortnite Booth** is an experimental AI-powered sports-style commentator for live Fortnite streams.

The project is exploring whether multimodal AI can function as a live broadcast booth: observing gameplay, understanding what is happening over time, deciding what matters, generating sports-style commentary, and delivering that commentary through synthesized speech during a live match.

The long-term goal is not simply to describe gameplay. The goal is to create something that feels like an actual sports broadcast built around Fortnite.


## Current Version — V0.2

V0.2 moves Fortnite Booth from manually triggered commentary to continuous game observation and automatic commentary.

Rather than waiting for a producer to request a comment from a single screenshot, the program continuously watches gameplay, maintains recent visual history, extracts structured game state, and decides when something is worth talking about.


### V0.2 Features

- Continuous local gameplay capture at approximately one frame per second
- Rolling 15-second visual buffer stored in memory
- Temporal analysis of multiple frames rather than a single screenshot
- Structured Fortnite game-state extraction
- High-detail HUD crops for important interface regions
- Automatic detection of meaningful gameplay developments
- Automatic commentary scheduling
- Play-by-play and color-commentary modes
- Short-term continuity between successive game-state analyses
- Independent capture, analysis, commentary, and speech execution
- AI-generated speech
- Windows-compatible audio playback
- Diagnostic JSONL session logging
- Optional producer hotkeys for manual intervention
- Compatibility with normal desktop-audio capture in streaming software


### V0.2 Vision Architecture

Gameplay is captured locally once per second.

Approximately every eight seconds, the system selects five frames from the rolling buffer:

```text
T-8 seconds
T-6 seconds
T-4 seconds
T-2 seconds
NOW
```


## Version History

### V0.1.0

Initial producer-triggered prototype using a single gameplay screenshot,
vision analysis, generated commentary, TTS, and Windows audio playback.

### V0.2.0

Added continuous screen capture, a rolling temporal buffer, structured
game-state extraction, automatic event detection, and automatic commentary.

See [`docs/development-notes.md`](docs/development-notes.md) for detailed
development history and design decisions.

## Next — V0.3

V0.3 is being designed as a transition from an AI commentator to an
AI broadcast booth.

Planned areas include:

- Two distinct announcer personalities
- A broadcast-director layer
- Continuous discussion during low-action gameplay
- Player statistics and historical performance
- Weapon, map, season, and update knowledge
- Persistent match and session storylines
- Automatic transition into play-by-play during combat