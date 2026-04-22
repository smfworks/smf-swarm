# SMF Swarm Web Frontend Implementation Plan

## Goal
Add a standalone, slick web interface to SMF Swarm that allows casual users to type prediction queries and upload reports (PDF/text), then view streaming results. Activated via `smf-swarm web` — prints a local URL to the terminal.

## Architecture
- **Backend:** Flask (BSD-3, lightweight, already in SMF Works stack) + REST API
- **Frontend:** Single-page Vanilla JS + HTML5. Dark theme, glassmorphism, cyberpunk-inspired. No bundler.
- **Pipeline:** Async queue + Server-Sent Events (SSE) for real-time progress streaming
- **Upload:** PDF/text ingestion → text extraction → fed into pipeline context
- **Standalone:** `smf-swarm web [--port 8080]` boots server; Ctrl+C stops

## New Files (Backend)
1. `src/smf_swarm/web/__init__.py`
2. `src/smf_swarm/web/app.py` — Flask app factory, CORS, static serving
3. `src/smf_swarm/web/api.py` — REST endpoints: `/api/predict`, `/api/upload`, `/api/stream/<job_id>`, `/api/status/<job_id>`
4. `src/smf_swarm/web/upload.py` — PDF/text file ingestion, text extraction
5. `src/smf_swarm/web/jobs.py` — In-memory job queue with threading

## New Files (Frontend)
6. `src/smf_swarm/web/static/index.html` — Single-page mission-control layout
7. `src/smf_swarm/web/static/css/main.css` — Dark glassmorphism theme
8. `src/smf_swarm/web/static/js/main.js` — App bootstrap, tab navigation
9. `src/smf_swarm/web/static/js/pipeline.js` — Pipeline runner, SSE client, UI updates
10. `src/smf_swarm/web/static/js/components.js` — Reusable UI components (cards, progress bars, terminal log)

## Modified Files
11. `src/smf_swarm/pipeline.py` — Add `run_async()` generator that yields progress events
12. `src/smf_swarm/cli.py` — Add `web` subcommand with `--port` and `--host`
13. `pyproject.toml` — Add `flask>=3.0.0` and `PyPDF2>=3.0.0` to dependencies
14. `README.md` — Add Web UI section with screenshot placeholder

## Design Spec (Frontend)
- **Background:** #0a0a0f (deep charcoal) with subtle grid overlay
- **Accent 1:** #f5a623 (amber/gold — confidence indicators)
- **Accent 2:** #00d4ff (cyan — links, active states)
- **Glass cards:** rgba(255,255,255,0.03) background, backdrop-filter blur(12px), 1px border rgba(255,255,255,0.06)
- **Typography:** Inter or system sans for body, JetBrains Mono or system mono for terminal log
- **Layout:**
  - Top bar: SMF Predict logo + mode selector (Standard | Debate | Full) + domain dropdown
  - Left column: Query textarea (auto-expand) + Upload dropzone + Run button
  - Right column: Streaming terminal log (collapsible) + Progress indicators per node
  - Bottom: Results panel — confidence arc, executive summary, risk assessment, dissent, social simulation

## Terminal UX
After `pip install smf-swarm`, user runs:
```
$ smf-swarm web
🌐 SMF Swarm Web UI
━━━━━━━━━━━━━━━━━━━━━
Server: http://127.0.0.1:8080
Press Ctrl+C to stop
━━━━━━━━━━━━━━━━━━━━━
[2026-04-21 22:45:12] Ready. Waiting for connections...
```

The link is printed in bold with a QR code suggestion (TBD).

## Job Queue Model
```
POST /api/predict
  Body: {query, mode, domain, context_text (from upload)}
  Response: {job_id, status: "queued"}

GET /api/stream/<job_id>  (SSE)
  Events: {type: "progress", node: "data_gatherer", status: "running"}
          {type: "progress", node: "data_gatherer", status: "complete", duration: 4.2}
          {type: "result", result: PipelineResult}
          {type: "error", message: "..."}

POST /api/upload
  Body: multipart/form-data (file)
  Response: {filename, text_preview, char_count}

GET /api/status/<job_id>
  Response: {job_id, status, progress_pct, current_node, result}
```
