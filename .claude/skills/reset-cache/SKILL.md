---
name: reset-cache
description: Delete the .cache directory after a schema, prompt, or model change so stale pickles are not reused.
disable-model-invocation: true
---

Clear the disk cache.

1. List what is in `.cache/` (namespaces and file counts) and show it.
2. Say why a reset is needed. The cache key already includes the schema
   fingerprint, the prompt text, and the model, so a reset is only needed
   when something outside those changed, such as extractor code or table
   parsing.
3. Delete `.cache/` after the owner confirms the listing.
4. Cached pages and extractions rebuild on the next run, which costs LLM
   calls again.
