---
name: reset-cache
description: Delete the .cache directory after a schema, prompt, or model change so stale pickles are not reused.
disable-model-invocation: true
---

1. List what is in `.cache/` (namespaces and file counts) and show it.
2. The key already covers schema fingerprint, prompt, and model. Reset only
   after changes outside those, such as extractor or table-parsing code.
3. Delete `.cache/` after the owner confirms the listing.
4. The next run rebuilds the cache and repeats the LLM calls.
