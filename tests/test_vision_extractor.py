import json as json_mod

import pytest

from ddgpt.extract.vision_extractor import OllamaVisionExtractor, ollama_vision_is_available
from ddgpt.ingestion.page_render import render_pages_png

PROMPT = "extract any chart on this page"


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_ollama_vision_is_available_false_when_unreachable():
    # Port 1 is a reserved/unroutable port -- guaranteed nothing is listening.
    assert ollama_vision_is_available("http://localhost:1", "llama3.2-vision", timeout=0.5) is False


def test_ollama_vision_is_available_false_when_model_not_pulled(monkeypatch):
    import requests

    def fake_get(url, timeout):
        return _FakeResponse({"models": [{"name": "llama3.2:3b"}]})

    monkeypatch.setattr(requests, "get", fake_get)
    assert ollama_vision_is_available("http://localhost:11434", "llama3.2-vision") is False


def test_ollama_vision_is_available_true_when_model_pulled(monkeypatch):
    import requests

    def fake_get(url, timeout):
        return _FakeResponse({"models": [{"name": "llama3.2-vision:latest"}]})

    monkeypatch.setattr(requests, "get", fake_get)
    assert ollama_vision_is_available("http://localhost:11434", "llama3.2-vision") is True


def test_extract_charts_skips_non_pdf_without_network_call(monkeypatch):
    import requests

    def fail_post(*args, **kwargs):
        raise AssertionError("should not make a network call for a non-PDF path")

    monkeypatch.setattr(requests, "post", fail_post)

    extractor = OllamaVisionExtractor(PROMPT)
    result = extractor.extract_charts("doc.txt", "sample_docs/Manager_Update_Atlas_Growth_Fund_III_v2.txt")
    assert result == []


def test_extract_page_returns_empty_list_when_no_chart(monkeypatch):
    import requests

    def fake_post(url, json, timeout):
        return _FakeResponse({"response": json_mod.dumps({"charts": []})})

    monkeypatch.setattr(requests, "post", fake_post)

    extractor = OllamaVisionExtractor(PROMPT)
    result = extractor._extract_page("doc.pdf", 1, b"fake-png-bytes")
    assert result == []


def test_extract_page_parses_chart_with_series(monkeypatch):
    import requests

    payload = {
        "charts": [
            {
                "chart_type": "bar",
                "title": "AUM Growth by Quarter",
                "x_label": "Quarter",
                "y_label": "AUM ($M)",
                "series": [
                    {"label": "Q1", "value": 100},
                    {"label": "Q2", "value": 120},
                ],
                "summary": "AUM grew steadily across quarters.",
            }
        ]
    }

    def fake_post(url, json, timeout):
        return _FakeResponse({"response": json_mod.dumps(payload)})

    monkeypatch.setattr(requests, "post", fake_post)

    extractor = OllamaVisionExtractor(PROMPT)
    result = extractor._extract_page("doc.pdf", 3, b"fake-png-bytes")

    assert len(result) == 1
    assert result[0]["page"] == 3
    assert result[0]["chart_type"] == "bar"
    assert result[0]["title"] == "AUM Growth by Quarter"
    assert result[0]["series"] == [{"label": "Q1", "value": 100.0}, {"label": "Q2", "value": 120.0}]
    assert result[0]["evidence"]["page"] == 3


def test_extract_page_parses_multiple_charts_on_same_page(monkeypatch):
    import requests

    payload = {
        "charts": [
            {"chart_type": "bar", "title": "Revenue Growth", "series": [{"label": "A", "value": 84}], "summary": "s1"},
            {"chart_type": "pie", "title": "Sector Mix", "series": [{"label": "AI", "value": 40}], "summary": "s2"},
        ]
    }

    def fake_post(url, json, timeout):
        return _FakeResponse({"response": json_mod.dumps(payload)})

    monkeypatch.setattr(requests, "post", fake_post)

    extractor = OllamaVisionExtractor(PROMPT)
    result = extractor._extract_page("doc.pdf", 1, b"fake-png-bytes")

    assert len(result) == 2
    assert {c["chart_type"] for c in result} == {"bar", "pie"}
    assert all(c["page"] == 1 for c in result)


def test_extract_page_returns_empty_list_after_retries_exhausted(monkeypatch):
    import requests

    def fake_post(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr("ddgpt.extract.vision_extractor.time.sleep", lambda *_: None)

    extractor = OllamaVisionExtractor(PROMPT)
    result = extractor._extract_page("doc.pdf", 1, b"fake-png-bytes")
    assert result == []


def test_render_pages_png_returns_all_pages():
    images = render_pages_png("sample_docs/test_packet.pdf", dpi=100)
    assert set(images.keys()) == {1, 2, 3}
    for png_bytes in images.values():
        assert png_bytes.startswith(b"\x89PNG")


def test_render_pages_png_respects_page_numbers_filter():
    images = render_pages_png("sample_docs/test_packet.pdf", dpi=100, page_numbers=[2])
    assert set(images.keys()) == {2}


def test_extract_charts_respects_max_pages_cap():
    extractor = OllamaVisionExtractor(PROMPT, max_pages=1)
    # No mocking of requests.post here -- if max_pages weren't respected this
    # would attempt 3 real HTTP calls against a (likely unreachable) host and
    # take a long time to fail; if it IS respected, only 1 page is attempted
    # and the assertion below on call count (via monkeypatch) confirms it.
    calls = []

    def fake_extract_page(doc_name, page_num, png_bytes):
        calls.append(page_num)
        return []

    extractor._extract_page = fake_extract_page
    extractor.extract_charts("doc.pdf", "sample_docs/test_packet.pdf")
    assert calls == [1]
