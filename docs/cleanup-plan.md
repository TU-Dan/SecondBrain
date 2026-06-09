# SecondBrain Cleanup Plan

This project is moving from a podcast/content tool toward an autonomous personal Agent system. Cleanup should reduce duplicate entry points before adding more Agent capabilities.

## Keep As Core

- `library.html` as the main operating surface: articles, inbox, feeds, insights, evolution.
- `article.html` as the focused reading and article transformation surface.
- `static/scripts/chat-widget.js` as the universal "Ask Brain" surface.
- `services/agent_tasks.py`, `services/agent_loop.py`, and `services/agent_proposals.py` as the Agent runtime foundation.
- `scripts/publish_to_pages.py` as the publishing integration with the external podcast Pages repo.

## Merge Next

- Merge `/generate` into the Inbox flow.
  - Current state: `/generate` is still linked from the Library sidebar and supports URL/file podcast generation.
  - Target: Library quick save creates an inbox item; podcast generation starts from an inbox item.
  - Remove condition: file upload has an equivalent inbox path.

- Merge `/card` into the Article output panel.
  - Current state: Article output uses `openCardMaker()` and opens `/card`.
  - Target: card preview/export lives inside the Article output panel.
  - Remove condition: article output can preview and export cards without a separate page.

- Merge `feed_items` into `inbox_items`.
  - Current state: RSS items live in `feed_items`; manual/discovery items live in `inbox_items`; `list_unified_inbox()` stitches them together.
  - Target: one inbox table with `source='rss'`, `feed_id`, `published_at`, and `relevance_score`.
  - Remove condition: RSS refresh writes directly to `inbox_items` and existing `feed_items` are migrated.

- Optimize Inbox.
  - Current state: Inbox has improved, but still needs a tighter review/save/read workflow.
  - Target: make Inbox the primary intake surface for RSS, manual URLs, notes, todos, and podcast generation.
  - Remove condition: a new item can be triaged, saved, dismissed, converted to podcast, and opened for reading without switching to legacy routes.

## Bugs To Fix

- Fix article highlighting after the first highlight.
  - Current state: first highlight works, but the second highlight can appear to do nothing.
  - Target: repeated highlights should reliably save, render in preview, and appear in notes without requiring a page refresh.
  - Remove condition: selecting two different text ranges in one reading session creates two visible notes and persists both after refresh.

- Optimize highlight analysis so it does not interrupt article reading.
  - Current state: the highlight-analysis block is expanded above the article, occupies most of the first viewport, shows long Agent output with raw Markdown syntax, and can overflow horizontally. The analysis currently competes with the source article instead of supporting it.
  - Target: keep the article as the primary reading surface. Collapse or summarize highlight analysis by default, render Markdown correctly, constrain height and width, and let readers expand individual analyses on demand.
  - Acceptance criteria:
    - Opening an article shows meaningful source content in the first viewport.
    - Highlight analysis is visually secondary and does not push the article far below the fold.
    - Raw Markdown markers such as `###`, `**`, tables, and separators are rendered or removed.
    - Long analysis wraps correctly without horizontal overflow.
    - Readers can expand, collapse, and inspect one highlight analysis without expanding every analysis.
  - Remove condition: an article with at least four analyzed highlights remains comfortable to read on desktop and mobile, with no raw Markdown or horizontal overflow.

## Delete Or Move

- Move one-off maintenance helpers out of `services/`.
  - Done: `services/importer.py` moved to `scripts/import_remote_rss.py`.

- Keep generated artifacts out of feature reviews.
  - Done: `.gitignore` ignores generated/runtime assets in `static/audio`, generated Markdown under `static/scripts`, `static/transcripts`, `static/images`, `static/episodes.json`, `static/podcast.xml`, and local `brain/*` data.
  - Exception: `static/scripts/chat-widget.js` remains tracked because it is application code used by templates.
  - Confirmed impact: not committing newly generated files in these paths does not break existing code paths; it only means locally generated podcast media, remote thumbnail cache, RSS episode state, and GBrain content are not portable through Git.

- Hide 大脑演化 from the main navigation.
  - Done: the UI entry is hidden while keeping the evolution view, Agent task APIs, proposal APIs, and logs available for future admin/debug use.

## Do Not Delete Yet

- `/generate`: still supports direct file upload.
- `/card`: still supports article output card export.
- `/publish`: still provides manual publishing from the local app.
- `feed_items`: still stores RSS-specific state until the inbox migration exists.

## Preferred Order

1. Hide or de-emphasize legacy UI entry points while leaving routes available.
2. Add replacement capability in the core surface.
3. Migrate data.
4. Remove old route/template/table only after replacement is verified.
