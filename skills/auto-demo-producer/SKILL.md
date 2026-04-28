---
name: auto-demo-producer
description: >
  Produce narrated video demos of web applications automatically.
  Uses Playwright for browser recording, edge-tts for narration, and ffmpeg for assembly.
  USE FOR: create demo video, record demo, auto demo, video demo, narrated walkthrough,
  product demo, screen recording with voiceover, demo producer, make a demo video,
  record a walkthrough, create a screencast with narration, auto-generate demo.
  DO NOT USE FOR: editing existing videos, live streaming, webcam recording.
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
