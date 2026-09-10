# Fortnite Booth

**Fortnite Booth** is an experimental AI-powered color commentator for live Fortnite Zero Build streams.

Instead of continuously listening to player voice chat, the system uses producer-triggered gameplay screenshots and short event cues to generate concise sports-style color commentary. The generated commentary is converted to speech and played through the stream's normal Windows audio path.

The goal is not constant AI narration. The goal is to create a recurring broadcast character — **The Booth** — that can analyze, praise, roast, and develop running storylines around noteworthy moments during a live match.

## Current Version

**V0 prototype / v0.1.0**

The current prototype supports:

* Global producer hotkeys
* Live monitor screenshot capture
* AI vision analysis of the current gameplay scene
* Different commentary modes for different events
* Short-term memory of recent Booth comments
* AI-generated speech
* Windows-compatible audio playback
* Compatibility with a normal TikTok LIVE Studio desktop-audio workflow

## Current Controls

| Hotkey         | Function                   |
| -------------- | -------------------------- |
| `F8`           | General Booth commentary   |
| `F9`           | Newbdaddy moment / roast   |
| `F10`          | Zelda moment               |
| `F11`          | Important or clutch moment |
| `Ctrl+Shift+Q` | Shut down                  |

## How It Works

```text
Producer hotkey
      ↓
Capture current gameplay screen
      ↓
Screenshot + event cue + recent Booth history
      ↓
OpenAI vision/language model
      ↓
Short color-commentary line
      ↓
OpenAI text-to-speech
      ↓
Raw PCM audio
      ↓
Python builds Windows-compatible WAV
      ↓
Windows playback
      ↓
Streaming software captures system audio
```

Player microphone audio and Discord voice chat are not sent to the AI in the current version.

## Requirements

* Windows
* Python
* OpenAI API account and API key
* Fortnite or another game/display source
* Streaming software capable of capturing Windows system audio

Install the Python dependencies with:

```powershell
python -m pip install -r requirements.txt
```

## API Key

The project expects the OpenAI API key to be available through the environment variable:

```text
OPENAI_API_KEY
```

Do **not** place an API key directly inside `booth.py` or commit API credentials to GitHub.

On Windows, one way to store it for future sessions is:

```powershell
setx OPENAI_API_KEY "YOUR_API_KEY"
```

Restart VS Code after initially creating the variable so new processes inherit it.

## Running the Prototype

From the project directory with the Python virtual environment activated:

```powershell
python .\booth.py
```

The program will wait in the background for one of the producer hotkeys.

## Current Limitations

V0 intentionally favors simplicity over automation.

Known limitations include:

* A single screenshot captures the moment the hotkey is pressed, which can miss the action immediately preceding it.
* AI analysis and speech generation introduce several seconds of latency.
* Commentary events are manually triggered.
* The program currently assumes a Windows audio environment.
* Commentary history is temporary and lasts only for the current program session.

## Roadmap

### V1 — Instant Replay Vision

Maintain a short rolling screenshot buffer so The Booth can see the sequence leading into an event rather than only its aftermath.

### V2 — Event Awareness

Detect useful gameplay state changes and obvious events automatically where practical.

### V3 — Broadcast Memory

Improve persistent session statistics, player tendencies, recurring jokes, storylines, and producer logic.

### V4 — Realtime Broadcast Architecture

Explore lower-latency realtime model interaction and more autonomous decisions about when commentary is warranted.

## Development Notes

Technical discoveries, bugs, design decisions, and prototype history are recorded in [`docs/development-notes.md`](docs/development-notes.md).

## AI-Assisted Development

Created by **Scot Lieser** with AI-assisted architecture, programming, debugging, and prototyping using **ChatGPT by OpenAI**.

ChatGPT is used as a development tool and pair-programming assistant; it is not listed as a repository collaborator or software author.

## Status

Experimental prototype.

The current focus is validating whether selective AI color commentary improves the entertainment value and viewer engagement of live gameplay before adding substantial automation.
