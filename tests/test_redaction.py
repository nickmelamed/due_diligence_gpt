from ddgpt.io.loaders import Page
from ddgpt.utils.redaction import redact_text, redact_pages


def test_redacts_email_phone_ssn_account():
    text = (
        "Contact jane.doe@example.com or 415-555-0182. "
        "SSN 123-45-6789. Account Number: 900123456."
    )
    redacted = redact_text(text)

    assert "jane.doe@example.com" not in redacted
    assert "123-45-6789" not in redacted
    assert "900123456" not in redacted
    assert "[REDACTED-EMAIL]" in redacted
    assert "[REDACTED-SSN]" in redacted


def test_does_not_touch_financial_figures():
    text = "Net IRR: 16.9%. AUM: $1.26B. TVPI: 1.63x. Management Fee: 2.0%."
    redacted = redact_text(text)
    assert redacted == text


def test_redact_pages_preserves_page_numbers():
    pages = [Page(page_num=1, text="jane.doe@example.com"), Page(page_num=2, text="Net IRR: 16.9%")]
    redacted = redact_pages(pages)

    assert redacted[0].page_num == 1
    assert "[REDACTED-EMAIL]" in redacted[0].text
    assert redacted[1].text == "Net IRR: 16.9%"
