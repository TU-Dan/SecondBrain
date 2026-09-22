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
python -m unittest discover -s tests -p 'test_publish_to_pages.py' -v
python -m unittest discover -s tests -p 'test_article_content.py' -v
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

For podcast task-management changes, confirm:

- `/tasks` shows current queue order, task state, stage, events, and generated files.
- Cancelling a pending task marks it `cancelled`; cancelling a running task
  terminates its child process and allows the next pending task to start.
- A stage that exceeds its configured timeout fails with `stage_timeout`
  without blocking the queue.
- Retrying a failed or cancelled task creates a new pending attempt linked to
  the original job.
- Original-audio jobs publish audio before transcript/article enrichment.
- Platform or AI subtitles generate the transcript without Whisper; when none
  are available, Whisper runs only if `whisper_transcribe=true`.
- Long original audio is split into files below the Cloudflare Pages limit
  before RSS publication.
- Expanded `/tasks` details remain open across the five-second automatic refresh.
- Terminal task durations use `finished_at` (or the final update time) instead
  of continuing to grow after completion.

For social-output prompt changes, confirm:

- `format_type="wechat"` output reads like a thinking note, not a lecture.
- The article keeps a clear personal observation, supporting source details,
  a tentative judgment, and boundaries or uncertainty.
- The title and first 120 Chinese characters surface a concrete object,
  surprising fact, conflict, change, or cost drawn from the source.
- Its appeal comes from the source's strongest material and core tension,
  rather than vague reflection, anxiety, clickbait, or reader criticism.
- The output contains a concise `【改稿诊断】` followed by a publishable
  `【改后全文】`; the diagnosis explicitly selects one main tone, narrative
  perspective, ending style, and restructuring direction.
- It avoids scolding the reader, generic life advice, forced action lists,
  hollow maxims, and phrases such as “你应该/你必须/真正厉害的人”.
- `list` and `insight` formats are not unintentionally changed.

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
