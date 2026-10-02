# Fortnite Booth — Development Notes

This document records meaningful prototype discoveries, design decisions, technical problems, test results, and architectural changes.

It is intentionally not a complete diary of every debugging step.

---

## V0.1.0 — Manual Producer Prototype

### Initial Goal

The original concept was an AI color commentator that could observe Fortnite gameplay and provide sports-broadcast-style commentary during a livestream.

Earlier experiments with general-purpose AI screen sharing exposed three major problems:

1. Difficulty maintaining awareness of a rapidly changing game environment.
2. Player voice chat being interpreted as conversation directed at the AI.
3. Long-running multimodal sessions becoming unreliable or timing out.

### Architectural Decision

Rather than making the AI continuously watch and listen to the entire stream, the first prototype used a producer-driven architecture.

The AI received:

- A gameplay screenshot
- A short producer event cue
- Recent Booth commentary for limited continuity

The AI did **not** receive:

- Player microphone audio
- Discord voice chat
- Fortnite voice chat

This prevented normal player conversation from accidentally triggering or steering the commentator.

---

## V0.1 Producer Controls

The first prototype used global hotkeys:

- `F8` — general commentary
- `F9` — Newb moment / roast
- `F10` — teammate moment
- `F11` — important or clutch moment
- `Ctrl+Shift+Q` — shut down

The producer cue supplemented the screenshot rather than requiring vision alone to determine why a moment was noteworthy.

---

## V0.1 Commentary Memory

V0.1 retained a small number of recent Booth comments in memory during the current Python session.

This allowed the model to make occasional callbacks and begin developing recurring jokes without requiring a continuously open multimodal conversation.

The history was lost when the program exited.

---

## Windows Audio Playback Issue

### Symptom

The OpenAI speech endpoint successfully generated audio, but Windows playback initially produced only a beep.

Inspection showed that the generated file had a valid WAV/RIFF signature.

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

- 1 channel
- 16-bit samples
- 24,000 Hz sample rate

The resulting WAV contains a normal finalized frame count and plays correctly through Windows.

### Result

After the PCM-to-WAV conversion:

- Generated speech played successfully through the headset.
- TikTok LIVE Studio captured the commentary through the existing desktop/system audio path.
- No virtual audio cable was required for the initial prototype.

This PCM-to-WAV path became the stable audio implementation and was retained in later versions.

---

## Early Latency Observations

Initial successful tests showed that latency was distributed across two major API operations:

1. Screenshot interpretation and commentary generation
2. Speech generation

A displayed "complete turnaround" time in early V0.1 also included the duration of the spoken commentary because WAV playback was synchronous.

This exposed an important distinction between:

- Time until commentary text is ready
- Time until generated speech is ready
- Time until speech begins
- Total duration until speech playback finishes

The viewer's perceived latency is primarily determined by the time until speech begins, not the time until the final word finishes playing.

---

## First Live Gameplay Test

The first gameplay tests demonstrated:

- Useful contextual commentary
- Successful gameplay-image interpretation
- Working generated speech
- Working livestream audio capture
- Some genuinely entertaining moments
- Noticeable screenshot-timing limitations
- Noticeable but potentially manageable latency

The largest structural limitation was that a single screenshot frequently captured the aftermath of an event rather than the event itself.

For example, a hotkey could be pressed immediately after a fight, but by the time the screenshot was captured the visible frame might show only the player standing over dropped loot.

This directly motivated the idea of retaining recent visual history.

---

## Original V1 Concept — Rolling Visual Replay Buffer

The first proposed improvement was to continuously retain a small number of recent screenshots in local memory.

An early concept looked approximately like:

```text
T - 3.0 seconds
T - 2.0 seconds
T - 1.0 second
T = current frame
```

No API request would be required while maintaining this local buffer.

When the producer triggered The Booth, selected recent frames could be submitted together so the model could reason about:

```text
setup → action → result → aftermath
```

rather than only the final state.

This idea became the foundation of V0.2.

---

# V0.2.0 — Continuous Vision and Automatic Commentary

V0.2 represented the first major architectural change.

Instead of requiring a producer to decide when The Booth should look at the game, the program began observing gameplay continuously and automatically deciding when commentary was appropriate.

Two concepts that were originally expected to become separate development stages were combined:

1. Rolling visual history
2. Automatic gameplay-event awareness

Testing showed that these were tightly related and were more useful when implemented together.

---

## V0.2 Continuous Local Capture

V0.2 captures the configured Fortnite monitor locally at approximately:

```text
1 frame per second
```

The frames are stored in memory rather than immediately sent to the API.

The rolling visual buffer retains approximately:

```text
15 seconds
```

of recent gameplay.

This means continuous observation does not require an API request every second.

---

## V0.2 Temporal Vision Analysis

Approximately every eight seconds, the system selects five frames from the rolling buffer:

```text
T-8 seconds
T-6 seconds
T-4 seconds
T-2 seconds
NOW
```

These frames provide the vision model with a crude temporal sequence rather than an isolated screenshot.

The full temporal frames are downsampled to reduce bandwidth and vision cost.

The newest frame is also used to create higher-detail crops of important HUD regions.

Current crops include:

- Top-right HUD / minimap
- Bottom-left player and teammate status
- Bottom-right weapon, inventory, ammunition, and resource information

This allows the system to use lower-detail imagery for temporal context while reserving higher-detail vision for areas containing small HUD information.

---

## Structured Game-State Extraction

A major V0.2 design change was separating:

```text
SEEING THE GAME
```

from:

```text
COMMENTING ON THE GAME
```

The vision model no longer exists primarily to produce a line of commentary.

Its job is first to extract structured game state.

The V0.2 state includes fields such as:

- Camera owner
- Match phase
- Location
- Current activity
- Health
- Shield
- Overshield
- Teammate state
- Teammate visibility
- Personal eliminations
- Team eliminations
- Players remaining
- Selected weapon
- Magazine ammunition
- Reserve ammunition
- Healing activity
- Confirmed damage dealt
- Damage received
- Visible enemies
- Major event
- Event importance
- Confidence
- Sequence summary

The newest structured state can then be compared with the previous state.

This gives the program some ability to reason about change over time rather than interpreting every vision request independently.

---

## Fortnite-Specific Vision Rules

Testing showed that general visual intelligence alone was not sufficient for consistently interpreting the Fortnite HUD.

A set of explicit Fortnite-specific rules was therefore developed from gameplay screenshots.

Important corrections included the following.

### Camera Ownership

The gameplay camera belongs to Newb by default.

Seeing a teammate's:

- Nameplate
- Marker
- Silhouette
- Character model

does **not** mean that the camera belongs to the teammate.

The system should only identify the teammate as the camera owner when explicit spectator-interface evidence supports that conclusion.

### Personal vs. Team Eliminations

Fortnite displays multiple elimination-related values.

The vision model must not assume that a visible team elimination count is Newb's personal elimination count.

### Magazine vs. Reserve Ammunition

A weapon's current magazine ammunition must not be confused with total ammunition.

For example:

```text
magazine_ammo = rounds currently loaded
reserve_ammo = additional ammunition available
```

A visible magazine value therefore does not justify commentary such as:

```text
"Newb only has six bullets left."
```

unless reserve ammunition also supports that conclusion.

### Health, Shield, and Overshield

The system distinguishes:

- Health
- Normal shield
- Zero Build overshield

Storm damage affects health rather than normal shield.

### Storm State

Evidence such as:

- Purple screen effects
- Storm rain
- Storm warning text
- Storm boundary
- Minimap state

can help determine whether the player is inside the storm or merely near it.

### DBNO, Elimination, and Revive

The system distinguishes:

- Alive
- Down But Not Out
- Reviving
- Fully eliminated
- Spectating

A knocked player should not automatically be described as eliminated.

### Combat

Useful combat evidence includes:

- Damage numbers
- Muzzle flash
- Falling magazine ammunition
- Incoming tracers
- Directional damage indicators
- Falling health
- Kill-feed events
- Enemy markers

The system is instructed to prefer uncertainty over inventing a combat event that is not visually supported.

---

## Match-Phase Awareness

V0.2 introduced basic recognition of different Fortnite match phases.

Examples include:

```text
LOBBY
BATTLE_BUS
DROPPING
ACTIVE
DBNO
SPECTATING
MATCH_OVER
UNKNOWN
```

This helped reduce nonsensical commentary caused by treating every screenshot as generic active gameplay.

---

## Automatic Event Importance

The vision system assigns an importance value to developments in the recent frame sequence.

The approximate meaning is:

```text
0 = nothing useful changed
1 = quiet background state
2 = mildly interesting development
3 = meaningful tactical development
4 = major event worth prompt commentary
5 = exceptional / clutch / knock / elimination / high-danger event
```

This state becomes an input to the commentary scheduler.

---

## Automatic Commentary Scheduling

V0.2 no longer requires producer hotkeys for normal operation.

The program automatically determines when commentary is appropriate.

The prototype uses different timing rules for:

- Ordinary commentary
- Important developments
- Major events
- Maximum silence

The original goal was to avoid constant narration while still allowing The Booth to respond automatically to meaningful gameplay.

Producer hotkeys remain available as overrides.

---

## Play-by-Play and Color Commentary

V0.2 introduced a distinction between:

### Play-by-Play

Used when the match contains significant immediate action such as:

- Combat
- Taking fire
- DBNO situations
- Revives
- Clutch moments
- Other high-importance developments

### Color Commentary

Used during quieter gameplay for:

- Tactical observations
- Player decisions
- General match context
- Occasional humor
- Ongoing storylines

The original commentary persona was also adjusted away from constant jokes and roasts toward a more credible sports-broadcast style.

Humor remained available, but was no longer required in every line.

---

## V0.2 Concurrency

V0.1 effectively treated a commentary request as one long operation:

```text
capture
↓
model
↓
speech generation
↓
audio playback
↓
operation complete
```

V0.2 separates major tasks into independent execution paths.

Conceptually:

```text
CAPTURE
continues collecting gameplay frames

VISION
periodically analyzes recent gameplay

COMMENTARY
decides what should be said

SPEECH
generates and plays the resulting line
```

Audio playback still blocks the speech thread while a line is being spoken.

However, capture and vision can continue while the announcer is talking.

This avoids losing gameplay observation merely because a spoken comment lasts several seconds.

---

## Analysis Backlog Prevention

Live commentary becomes less useful if vision requests form a backlog and begin describing events that happened long ago.

V0.2 therefore avoids queueing repeated analysis jobs.

If the previous vision analysis is still running when another analysis interval arrives, the new cycle can be skipped rather than added to a growing queue.

For live broadcasting, recent information is more valuable than complete but stale information.

---

## Diagnostic Logging

V0.2 creates JSONL session logs under:

```text
logs/
```

Logs may include:

- Vision-analysis timing
- Extracted game state
- Commentary decisions
- Generated commentary
- Audio timing
- Skipped analysis cycles
- Errors

The `logs/` directory is excluded from Git because these files are runtime artifacts rather than source code.

The logs are intended to support later analysis of:

- Latency
- Event-detection quality
- Commentary frequency
- Vision mistakes
- Broadcast timing

---

## V0.2 Testing Result

V0.2 produced a substantial technical improvement over V0.1.

The program became better at:

- Understanding changing gameplay
- Detecting active combat
- Tracking some HUD state
- Recognizing major events
- Maintaining observation while speech was playing
- Triggering commentary automatically
- Distinguishing play-by-play from quieter commentary

However, a new problem became obvious during real gameplay testing.

The Booth was technically more capable, but it still did not feel like a natural sports broadcast.

---

# The Broadcast-Naturalness Problem

The V0.2 system remained fundamentally event-oriented.

Its behavior was roughly:

```text
observe gameplay
↓
detect something interesting
↓
say something
↓
wait
↓
detect another interesting thing
↓
say something else
```

Even when the individual comments were good, they often felt like isolated AI observations.

This differed significantly from watching an actual sports broadcast.

---

## Baseball Broadcast Analogy

Baseball became a useful comparison because its pacing resembles Fortnite in an important way:

```text
long periods of lower-intensity activity
↓
sudden bursts of meaningful action
↓
return to lower-intensity activity
```

During quiet portions of a baseball game, announcers do not normally remain silent until the next pitch becomes exciting.

They discuss:

- Players
- Teams
- Statistics
- Previous seasons
- Trends
- Recent performance
- Strategy
- Equipment
- League developments
- Earlier moments in the game
- Relevant stories

When meaningful action begins, the broadcast immediately shifts back toward play-by-play.

Fortnite naturally contains similar discussion material.

Examples include:

- Wins
- Win percentage
- Eliminations
- Downs
- K/D
- Tracker Rating
- Ranked performance
- Seasonal trends
- Previous matches
- Favorite weapons
- Weapon damage
- Magazine size
- Reload time
- Weapon rarity
- Buffs and nerfs
- Current loot pool
- Map changes
- POIs
- Seasonal mechanics
- Sprites
- Overrides
- Collaborations
- Rotations
- Loadout decisions
- Push vs. disengage decisions
- Storm positioning
- Player tendencies

This observation significantly changed the planned direction of the project.

---

# Roadmap Evolution

The original conceptual roadmap was approximately:

```text
V1
Rolling visual replay buffer

V2
Automatic event awareness

V3
Broadcast memory and player storylines

V4
More autonomous / lower-latency broadcast architecture
```

Development did not follow those stages cleanly.

Testing showed that rolling visual history and automatic event awareness were strongly connected.

They were therefore implemented together in V0.2.

More importantly, V0.2 testing showed that "broadcast memory" alone would not solve the remaining naturalness problem.

The project needed a larger architectural shift.

The next version therefore evolved from:

```text
better commentator memory
```

into:

```text
a complete AI broadcast booth
```

---

# Planned V0.3 — Two-Announcer Broadcast Booth

V0.3 is being designed as the transition from a single AI commentator to a two-person sports-style broadcast booth.

The central idea is that the system should maintain natural conversation during quieter gameplay rather than waiting for isolated events.

When meaningful action occurs, the broadcast should transition quickly into play-by-play.

---

## Planned Announcer Roles

The two announcers are expected to have different jobs rather than behaving as interchangeable voices.

### Lead / Play-by-Play Announcer

Primary responsibilities may include:

- Introducing the broadcast
- Guiding transitions
- Calling significant live action
- Combat play-by-play
- Identifying important tactical developments
- Moving the discussion from one subject to another
- Returning the broadcast to live action when necessary

### Analyst / Color Commentator

Primary responsibilities may include:

- Player statistics
- Player history
- Current-season performance
- Recent trends
- Weapon analysis
- Loadout discussion
- Patch changes
- Meta discussion
- Map strategy
- Player tendencies
- Tactical interpretation
- Previous-match callbacks

The two voices should feel like people having a conversation rather than alternating unrelated generated statements.

---

## Planned Broadcast Director

V0.3 is expected to introduce a separate broadcast-director layer.

This creates a clearer division between:

```text
GAME OBSERVATION
What is happening?

        ↓

BROADCAST DIRECTION
What should the broadcast be talking about right now?

        ↓

ANNOUNCERS
How should it be presented?
```

This is an important conceptual change.

The vision model should not be responsible for independently deciding how entertaining a screenshot is.

The announcers should not have to rediscover the entire game state from raw images every time they speak.

The director should combine current game state, session context, and available knowledge to determine the most appropriate broadcast topic and mode.

---

## Planned Knowledge Layer

V0.3 will require significantly more contextual knowledge than previous versions.

Potential categories include:

```text
players/
season/
weapons/
map/
patches/
current_session/
broadcast_history/
```

Examples of useful knowledge include:

### Player Information

- Current-season statistics
- Previous-season statistics
- Recent 7-day and 30-day performance
- Wins
- Win percentage
- Eliminations
- K/D
- Playlist-specific results
- Player tendencies
- Preferred weapons
- Strengths
- Weaknesses
- Recurring habits
- Relevant personal gameplay storylines

### Fortnite Information

- Current season
- Current event
- Current POIs
- Weapon statistics
- Item statistics
- Buffs and nerfs
- Patch changes
- Seasonal mechanics
- Current collaborations
- Relevant competitive information

### Session Information

- Results of earlier matches
- Eliminations
- Landing locations
- Important fights
- Repeated tactical decisions
- Recurring loadout choices
- Previous announcer discussions
- Storylines already introduced

The goal is not to provide the entire knowledge base to every model request.

Relevant information should eventually be selected based on current context.

---

## Player Statistics as Broadcast Material

Initial player-profile data demonstrated that Fortnite statistics can function similarly to traditional sports statistics.

Examples include comparisons between:

```text
current season
recent 30 days
recent 7 days
previous seasons
duos
trios
squads
```

This creates natural broadcast topics such as:

- Whether performance is improving or declining
- Whether current play differs from historical performance
- Whether a player performs differently by playlist
- Whether a current match is unusually strong or weak
- Whether a player is approaching or exceeding a normal statistical baseline

The key design principle is that statistics should support conversation rather than simply being read aloud.

---

## Weapon and Loadout Discussion

Inventory changes are potentially valuable broadcast events even when they are visually subtle.

For example:

```text
player drops AR
↓
player picks up legendary SMG
↓
director retrieves weapon and player context
↓
analyst discusses the tradeoff
```

Possible discussion factors include:

- Rarity
- Damage
- Fire rate
- Magazine size
- Reload time
- Effective range
- Ammunition availability
- Player preference
- Existing inventory
- Match phase
- Expected upcoming fights

A decision made early in the match can later become a callback.

For example, if the analyst questions giving up an AR and the team later struggles at long range, the earlier discussion becomes part of the match storyline.

---

## Planned Opening Broadcast

V0.3 is expected to include a dedicated opening sequence rather than beginning with a random commentary line.

The opening may use context such as:

- Current date
- Current Fortnite event
- Current season
- Relevant collaborations
- Today's duo
- Current skins when confidently identified
- Player statistics
- Recent player activity
- Time away from the game
- Previous session results
- Current session match number

The opening should resemble a pregame sports broadcast conversation.

As the Battle Bus becomes active, the opening discussion should naturally transition into live match coverage.

Later matches in the same session should reference earlier results rather than repeating the original introduction.

---

## Planned Match and Broadcast Memory

V0.3 should remember more than the previous few generated comments.

Potential persistent session information includes:

```text
Match 1
- landing location
- eliminations
- major fight
- cause of elimination
- notable loadout
- strategic mistakes
- strong plays

Match 2
- landing location
- repeated behavior
- evolving player trend
- result
```

The system should also maintain a record of topics already discussed.

For example:

```text
already discussed:
- season win rate
- current event
- player's recent break

not yet discussed:
- recent K/D trend
- shotgun preference
- previous-season comparison
- new seasonal mechanics
```

This should reduce repetitive commentary and allow longer storylines to develop over an entire stream.

---

## Planned Adaptive Vision

The current V0.2 system captures approximately one frame per second locally and performs vision analysis approximately every eight seconds.

For V0.3, one proposed direction is:

```text
local capture:
approximately 2 frames per second

quiet gameplay:
vision analysis approximately every 6 seconds

interesting activity:
vision analysis approximately every 3 seconds

combat:
analyze as quickly as practical without building a backlog
```

The important distinction remains:

```text
local screenshots ≠ API requests
```

A denser local buffer can preserve more temporal information without sending every captured frame to the API.

Simple local image-change detection may eventually help decide when faster visual analysis is warranted.

Potential monitored regions include:

- Main gameplay area
- Health / shield HUD
- Inventory
- Kill feed

Local change detection would not need to understand Fortnite.

Its role would simply be to identify that something changed enough to justify earlier analysis.

---

## Human Voice Activity

An early V0.3 idea was to detect when players were speaking so the Booth could avoid talking over Discord or gameplay conversation.

This has deliberately been deferred.

For initial V0.3 testing:

- Player voice chat will remain outside the AI system.
- The Booth may speak over gameplay conversation.
- Player/Discord volume can be mixed lower underneath the generated broadcast.

This reduces complexity while the more important broadcast architecture is tested.

Voice-activity-aware timing can be reconsidered later if overlapping speech proves distracting.

---

## Updated Broadcast Design Principle

An early design principle stated that selective commentary was likely more entertaining than continuous AI narration.

Testing refined that idea.

The Booth should **not** continuously describe every visible action.

However, it also should **not** remain silent simply because nothing dramatic is happening.

The current principle is:

> Maintain natural sports-broadcast conversation during low-action periods, then transition quickly to event-focused play-by-play when the game demands it.

The desired system is therefore neither:

```text
constant gameplay narration
```

nor:

```text
occasional isolated AI comments
```

The target is:

```text
continuous broadcast conversation
+
selective live play-by-play
```

---

## Current Development Status

V0.1 established that the complete technical path was viable:

```text
gameplay image
→ vision/language model
→ generated commentary
→ generated speech
→ Windows audio
→ livestream
```

V0.2 established:

```text
continuous gameplay observation
→ temporal visual context
→ structured game-state extraction
→ automatic event awareness
→ automatic commentary
```

The current design work for V0.3 is focused on:

```text
continuous gameplay observation
+
structured Fortnite knowledge
+
persistent match/session memory
+
broadcast director
+
two announcers
→
natural full-match sports broadcast
```

The primary challenge is no longer proving that AI can comment on Fortnite.

The current challenge is making the resulting broadcast feel coherent, informed, continuous, and natural over the course of an entire match and livestream session.