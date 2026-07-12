from __future__ import annotations

import re
from typing import List

from ddgpt.io.loaders import Page

# Deliberately narrow: only patterns that can never overlap with the target
# financial fields (AUM/IRR/TVPI/fees are dollar amounts and percentages,
# never emails/phones/SSNs/account numbers), so redaction can't clobber the
# figures the pipeline is trying to extract.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
ACCOUNT_RE = re.compile(r"\b(?:account|acct)\s*(?:no\.?|number|#)?\s*[:#]?\s*\d{6,}\b", re.IGNORECASE)


def redact_text(text: str) -> str:
    text = EMAIL_RE.sub("[REDACTED-EMAIL]", text)
    text = SSN_RE.sub("[REDACTED-SSN]", text)
    text = PHONE_RE.sub("[REDACTED-PHONE]", text)
    text = ACCOUNT_RE.sub("[REDACTED-ACCOUNT]", text)
    return text


def redact_pages(pages: List[Page]) -> List[Page]:
    """Copy of `pages` with obviously sensitive identifiers stripped, for use
    only on the copy sent to third-party LLM APIs -- evidence verification
    still checks extracted snippets against the original, unredacted pages."""
    return [Page(page_num=p.page_num, text=redact_text(p.text or "")) for p in pages]
