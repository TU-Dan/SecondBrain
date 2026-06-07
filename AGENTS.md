# MySecondBrain Project Guide

## Purpose

MySecondBrain is a local FastAPI application for capturing, processing, and
publishing personal knowledge. It includes a content-to-podcast pipeline that
writes generated material into the knowledge base and publishes an RSS feed.

## Important Paths

- `main.py`: FastAPI application and HTTP routes.
- `services/`: extraction, LLM, RSS, database, memory, and podcast job services.
- `packages/content-to-podcast/`: reusable podcast generation package and CLI.
- `templates/`: server-rendered web UI.
- `scripts/`: setup, verification, and RSS publishing commands.
- `static/`: generated podcast and application assets.
- `data/`: local runtime data, models, cookies, and SQLite database.

## Development

```bash
/opt/anaconda3/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Prepare and check the Mac-local podcast tools:

```bash
bash scripts/setup_podcast_tools_macos.sh
bash scripts/capture_douyin_cookie.sh
bash scripts/start_douyin_downloader.sh
bash scripts/check_podcast_tools.sh
```

## Verification

```bash
python -m unittest discover -s tests -p 'test_podcast_pipeline.py' -v
python scripts/verify_podcast_fidelity.py
python scripts/verify_youtube_url_normalization.py
python -m py_compile main.py services/*.py packages/content-to-podcast/content_to_podcast/*.py
```

For frontend changes, start the app and verify the affected workflow in a
browser. Run `git diff --check` before finishing.

For a real Douyin acceptance check, confirm:

- `bash scripts/check_podcast_tools.sh` reports downloader and Cookie ready.
- A public Douyin URL reaches podcast job status `done` with
  `transcript_source=whisper`.
- The knowledge-base article exists and the Cloudflare RSS enclosure URL
  returns HTTP 200.

## Engineering Constraints

- Preserve the existing Cloudflare RSS publishing flow through
  `scripts/publish_to_pages.py`.
- Do not commit generated audio, transcripts, models, cookies, or downloaded
  third-party media.
- Keep platform-specific media download behavior inside source adapters.
- Podcast jobs are persistent SQLite records and are consumed by one worker.
- Preserve unrelated local changes; do not rewrite generated files unless the
  task requires it.

## Definition Of Done

The requested behavior is implemented, focused tests pass, existing podcast
verification scripts pass, the application starts successfully, and failures
return actionable job error codes without losing generated content.

For every new feature iteration, provide Dan with clear acceptance criteria and
a step-by-step validation path, including expected results. Update this
`AGENTS.md` when the feature introduces new stable validation commands,
workflows, or project-specific acceptance requirements.
