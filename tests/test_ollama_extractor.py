import pytest

from ddgpt.extract.ollama_extractor import ollama_is_available, OllamaExtractor
from ddgpt.io.loaders import Page


def test_ollama_is_available_false_when_unreachable():
    # Port 1 is a reserved/unroutable port -- guaranteed nothing is listening.
    assert ollama_is_available("http://localhost:1", timeout=0.5) is False


def test_ollama_extractor_falls_back_to_regex_when_unreachable():
    extractor = OllamaExtractor(model="llama3.2:3b", temperature=0.0, prompt_text="extract fields", host="http://localhost:1")
    pages = [Page(page_num=1, text="Net IRR: 16.9%. AUM: $1.20B.")]

    doc = extractor.extract("test.pdf", pages)

    assert doc.doc_name == "test.pdf"
    assert any("fallback" in note for note in doc.notes)


@pytest.mark.skipif(not ollama_is_available(), reason="requires a running local Ollama server")
def test_ollama_extractor_live_extraction():
    extractor = OllamaExtractor(model="llama3.2:3b", temperature=0.0, prompt_text=(
        "Extract fields specified by the schema. If a field is not present, set it to null "
        "and add it to missing_fields. Return ONLY valid JSON."
    ))
    pages = [Page(page_num=1, text="Assets Under Management (AUM): $1.20B. Net IRR: 16.9%. TVPI: 1.55x.")]

    doc = extractor.extract("live_test.pdf", pages)

    assert doc.doc_name == "live_test.pdf"
