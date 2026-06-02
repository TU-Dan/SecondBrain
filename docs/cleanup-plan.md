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

## Delete Or Move

- Move one-off maintenance helpers out of `services/`.
  - Done: `services/importer.py` moved to `scripts/import_remote_rss.py`.

- Keep generated artifacts out of feature reviews.
  - `static/audio`, `static/transcripts`, `static/scripts`, `static/images`, `static/podcast.xml`, and `static/episodes.json` are generated/runtime artifacts.
  - `brain/articles` and `brain/insights` need a tracking policy because they are product data, not app code.

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
