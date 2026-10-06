from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.pipeline.fusion_extractor import FusionExtractor
import ddgpt.pipeline.fusion_extractor as fusion_extractor_module


class _CountingExtractor:
    model = "test-model"
    temperature = 0.0
    prompt_text = "prompt"

    def __init__(self):
        self.calls = 0

    def extract(self, doc_name, pages):
        self.calls += 1
        return ExtractedDoc(doc_name=doc_name)


def _make_fusion(tmp_path):
    fe = FusionExtractor.__new__(FusionExtractor)
    fe.cache_dir = str(tmp_path)
    fe.enable_disk_cache = True
    return fe


def test_cache_hit_on_unchanged_schema_fingerprint(tmp_path):
    from ddgpt.io.loaders import Page

    fe = _make_fusion(tmp_path)
    extractor = _CountingExtractor()
    pages = [Page(page_num=1, text="hello")]

    fe._extract_with_cache(extractor, "doc.pdf", pages)
    fe._extract_with_cache(extractor, "doc.pdf", pages)

    assert extractor.calls == 1  # second call was a cache hit


def test_cache_miss_when_schema_fingerprint_changes(tmp_path, monkeypatch):
    from ddgpt.io.loaders import Page

    fe = _make_fusion(tmp_path)
    extractor = _CountingExtractor()
    pages = [Page(page_num=1, text="hello")]

    fe._extract_with_cache(extractor, "doc.pdf", pages)

    # Simulate a schema change between runs -- a stale pickle from the old
    # fingerprint must not be reused.
    monkeypatch.setattr(fusion_extractor_module, "SCHEMA_FINGERPRINT", "a-different-fingerprint")
    fe._extract_with_cache(extractor, "doc.pdf", pages)

    assert extractor.calls == 2  # cache missed -- recomputed instead of reusing the stale entry
