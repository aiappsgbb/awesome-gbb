---
name: auto-demo-producer
description: >
  Produce narrated video demos of web applications automatically.
  Uses Playwright for browser recording, edge-tts for narration, and ffmpeg for assembly.
  USE FOR: create demo video, record demo, auto demo, video demo, narrated walkthrough,
  product demo, screen recording with voiceover, demo producer, make a demo video,
  record a walkthrough, create a screencast with narration, auto-generate demo.
  DO NOT USE FOR: editing existing videos, live streaming, webcam recording.
metadata:
  version: "1.1.0"
---

# Auto Demo Producer

Produce professional narrated video demos of ANY web application — automatically.

## Pipeline Overview

```
User context → Demo script → Slides → TTS narration → Browser recording → Final MP4
```

Three phases, fully automated:
1. **Narration** — edge-tts (free Microsoft Neural TTS) generates audio per scene
2. **Recording** — Playwright drives headless Chromium with video capture
3. **Assembly** — ffmpeg merges video + audio into polished MP4

## When to Activate

- User asks to "create a demo", "record a walkthrough", "make a video demo"
- User provides a URL + description of what to show
- User wants an automated screencast with voiceover

## Step-by-Step Workflow

### Step 1: Gather Context

Ask the user for:
1. **Target URL** — the web app to demo (e.g., `https://myapp.azurewebsites.net`)
2. **What to show** — key features, user flows, or scenarios
3. **Audience** — who will watch? (executives, developers, customers)
4. **Duration target** — how long should the demo be? (1-5 min typical)
5. **Voice preference** — language and gender (default: `en-US-JennyNeural`)
6. **Branding** — product name, subtitle, organization, accent color for intro/outro

### Step 2: Create Demo Script

Generate a `demo_script.md` using this format:

```markdown
# Demo: {Product Name}

## intro | 5
> slide intro
Welcome to this demo of Product Name. Today we'll walk through the key features.

## login | 8
> goto {base_url}
> fill Username demo@contoso.com
> fill Password ****
> click button Sign In
Here we sign in to the application using our demo credentials.

## dashboard | 10
> wait 2
> scroll down 300
The dashboard shows a real-time overview of all active items.

## feature_one | 12
> click link Feature One
> wait 1
> scroll down 200
Let's explore Feature One, which allows you to create and manage workflows.

## outro | 5
> slide outro
Thank you for watching! Visit us at contoso.com for more information.
```

**Script format rules:**
- `## scene_id | min_duration_seconds` — scene header
- `> action args...` — Playwright actions (see Action Reference below)
- Plain text lines = narration (spoken by TTS voice)
- Narration determines actual scene duration (padded to match audio length)

### Step 3: Generate Slides

Run the slide generator to create intro/outro HTML files:

```powershell
python generate_slides.py `
    --title "Product Name" `
    --subtitle "Your tagline here" `
    --org "Contoso" `
    --badge "Powered by Azure" `
    --accent "#60a5fa" `
    --out-dir ./slides
```

### Step 4: Install Dependencies

```powershell
pip install edge-tts playwright
playwright install chromium
# Ensure ffmpeg is available:
# Windows: winget install Gyan.FFmpeg
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

### Step 5: Run the Recorder

```powershell
python record_demo.py `
    --script demo_script.md `
    --base-url "https://myapp.azurewebsites.net" `
    --voice en-US-JennyNeural `
    --slides-dir ./slides `
    --output demo_final.mp4
```

Additional options:
- `--resolution 1280x720` for smaller file size
- `--var project_id=abc123` for custom variables in script
- `--var username=demo@contoso.com` for parameterized flows

### Step 6: Review and Iterate

After recording, review the output video. Common adjustments:
- **Too fast?** Increase `min_duration` in scene headers
- **Wrong timing?** Add `> wait N` actions between steps
- **Missing steps?** Add more scenes to the script
- **Wrong voice?** Try a different edge-tts voice

## Action Reference

| Action | Syntax | Description |
|--------|--------|-------------|
| `goto` | `> goto https://url.com` | Navigate to URL |
| `slide` | `> slide intro` | Show HTML slide from slides directory |
| `click` | `> click link Link Text` | Click a link by text |
| `click` | `> click button Button Text` | Click a button by text |
| `click` | `> click text Any Text` | Click any element by text |
| `fill` | `> fill Label value` | Fill a form textbox |
| `type` | `> type #selector value` | Type into element by CSS selector |
| `hover` | `> hover Element Text` | Hover over element |
| `select` | `> select Label Option` | Select dropdown option |
| `scroll` | `> scroll down 300` | Scroll down by pixels |
| `scroll` | `> scroll up 200` | Scroll up by pixels |
| `wait` | `> wait 2` | Pause for N seconds |
| `screenshot` | `> screenshot name.png` | Save screenshot |

## Voice Selection

Popular edge-tts voices (all free, no API key needed):

| Voice | Language | Style |
|-------|----------|-------|
| `en-US-JennyNeural` | English (US) | Warm, conversational |
| `en-US-GuyNeural` | English (US) | Professional, clear |
| `en-US-AriaNeural` | English (US) | Natural, versatile |
| `en-GB-SoniaNeural` | English (UK) | Polished, professional |
| `it-IT-IsabellaNeural` | Italian | Natural, clear |
| `de-DE-KatjaNeural` | German | Professional |
| `fr-FR-DeniseNeural` | French | Elegant |
| `es-ES-ElviraNeural` | Spanish | Clear |
| `ja-JP-NanamiNeural` | Japanese | Natural |
| `zh-CN-XiaoxiaoNeural` | Chinese | Versatile |

Full list: `edge-tts --list-voices`

## Variables

Use `{variable_name}` in scripts. Built-in:
- `{base_url}` — set via `--base-url` argument

Custom variables via `--var key=value`:
```markdown
> goto {base_url}/projects/{project_id}
> fill Search {search_term}
```

## Output

The skill produces:
- `demo_final.mp4` — H.264 video, AAC audio, web-optimized (faststart)
- Resolution: 1920×1080 (default) or custom
- Quality: CRF 18 (high quality), AAC 192kbps

## Tips for Great Demos

1. **Script first** — Write narration before actions. The story drives the pacing.
2. **Short scenes** — 8-15 seconds per scene. Keep it punchy.
3. **Generous waits** — Add `> wait 1-2` after navigations for visual breathing room.
4. **Match narration to action** — Describe what's happening on screen as it happens.
5. **Intro/outro slides** — Always use them for professional polish.
6. **Test incrementally** — Record one scene first to check timing, then add more.
7. **Brand consistency** — Intro/outro slide colors MUST match the PoC's brand palette (from `threadlight-design` Cross-cutting Pattern 1). Don't use default blue/purple gradients for a red-branded customer. Copy the CSS custom properties from the PoC's `demo-deck.html` into the slide HTML files.
8. **Subtitles** — Generate a WebVTT file from the narration text. **Do NOT use external `<track src="file.vtt">`** — Edge blocks CORS on `file://` protocol. Instead, embed the VTT inline as a JS blob URL: `var blob = new Blob([vttData], {type:'text/vtt'}); track.src = URL.createObjectURL(blob);` and dynamically append the `<track>` element. Timestamps MUST use `HH:MM:SS.mmm` format (not `MM:SS.mm` — Edge rejects it).
9. **Embed in deck** — If the PoC ships a `demo-deck.html`, embed the video as a fallback on the live-demo holding card. Wire a `V` key toggle: press V to play the video inline on the `.is-cue` slide, press V again to stop. Add a visible control bar (play/pause button + clickable progress bar + time display) so the presenter doesn't depend on keyboard shortcuts alone. Auto-stop on `ended` event. The fallback hint ("Press V for pre-recorded fallback") shows below the cue text at low opacity.

## Recording Agent Demos (battle-tested pattern)

> **This section was extracted from 6 failed recording attempts on a
> Foundry-hosted-agent PoC.** The patterns below are the only approach
> that reliably produces a watchable video when agent response time is
> unpredictable (10–50 seconds).

### The problem

AI agent demos are **not recordable in real time**. The agent takes
10–50 seconds to respond. If you record the browser continuously and
overlay pre-generated narration audio, the voice describes the answer
while the screen still shows "Working...". No amount of post-production
speed-up or audio-shifting fixes this reliably — the two timelines are
fundamentally desynchronised.

### The solution: screenshot-per-scene jump-cuts

Never show "Working..." in the video. Jump-cut from "question typed"
directly to "answer rendered". The agent wait happens **off-camera**
between screenshots.

**Per-scene workflow:**

1. **Type the prompt** → screenshot the typed state (narrator introduces the question over this frame)
2. **Click "Ask"** → poll until the response fully renders (off-camera — no recording)
3. **Screenshot the completed answer** (narrator describes the response over this frame)
4. **Build segment**: still image + matching narration audio clip (exact duration match)
5. **Concatenate** all segments: intro → K1typed → K1done → K2typed → K2done → … → outro

**Smart wait — appear → disappear polling:**

```python
# Phase 1: wait for loading indicator to APPEAR (confirms API call started)
for _ in range(30):
    if await page.evaluate("() => !!document.body.innerText.match(/Working/)"):
        break
    await page.wait_for_timeout(500)

# Phase 2: wait for loading indicator to DISAPPEAR (confirms response rendered)
for _ in range(120):
    if not await page.evaluate("() => !!document.body.innerText.match(/Working/)"):
        break
    await page.wait_for_timeout(1000)
await page.wait_for_timeout(2000)  # let DOM settle
```

Adapt the regex (`/Working/`) to match whatever loading indicator the
workspace uses. The 2-phase pattern prevents the common bug where the
script checks before "Working..." even appears and immediately proceeds.

**Building a segment from a still image + audio:**

```python
def make_segment(image_path, audio_path, output_path):
    audio_dur = ffprobe_duration(audio_path)
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(audio_dur),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output_path),
    ], check=True)
```

Each segment's duration equals its narration audio — **the narrator
always describes what's on screen**.

### Anti-patterns (from 6 failed VF3 recording attempts)

| ❌ Approach | Why it fails |
|---|---|
| Record continuously + overlay audio afterwards | Audio and video timelines never align — narrator talks about citations while screen shows "Working..." |
| Speed up "Working..." video portions with `setpts` | Looks janky; speedup factor depends on unpredictable agent response time |
| Fixed `> wait 35` timers in the script | Agent response time is 10–50s; fixed timers either cut off answers or waste 30s showing nothing |
| Record video + audio simultaneously in real time | Playwright can't capture system audio; headless Chromium has no audio device |
| Post-process with audio-shift detection | Too fragile; "Working..." text appears in DOM but visual loading spinners vary per workspace |

### Voice selection for agent demos

Use a **British voice** (`en-GB-SoniaNeural`) for UK-audience PoCs —
it reads naturally at demo pace and matches the professional register.
Avoid US casual voices for regulated-industry demos (FSI, telco, healthcare).

## File Locations

When activated as a global Copilot CLI skill, the scripts are at:
- `~/.copilot/skills/auto-demo-producer/scripts/record_demo.py`
- `~/.copilot/skills/auto-demo-producer/scripts/generate_slides.py`

Copy them to your project directory before running, or reference directly.

## Prerequisites

- **Python 3.10+** with `pip`
- **edge-tts** — `pip install edge-tts` (free Microsoft Neural TTS)
- **Playwright** — `pip install playwright && playwright install chromium`
- **ffmpeg** — system binary (see install commands above)
