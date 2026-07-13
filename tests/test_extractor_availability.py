from ddgpt.config import Config
from ddgpt.pipeline.builders import extractor_availability


def test_ollama_reported_active_when_reachable(monkeypatch):
    cfg = Config()
    monkeypatch.setattr("ddgpt.pipeline.builders.ollama_is_available", lambda host: True)
    status = extractor_availability(cfg)
    assert status["OllamaExtractor"] == "active"


def test_ollama_reported_skipped_with_reason_when_unreachable(monkeypatch):
    cfg = Config()
    monkeypatch.setattr("ddgpt.pipeline.builders.ollama_is_available", lambda host: False)
    status = extractor_availability(cfg)
    assert status["OllamaExtractor"].startswith("skipped")
    assert cfg.ollama.host in status["OllamaExtractor"]


def test_ollama_reported_disabled_when_config_disabled(monkeypatch):
    cfg = Config()
    cfg.ollama.enabled = False
    monkeypatch.setattr("ddgpt.pipeline.builders.ollama_is_available", lambda host: True)
    status = extractor_availability(cfg)
    assert status["OllamaExtractor"] == "disabled in config"


def test_cohere_reported_skipped_without_api_key(monkeypatch):
    cfg = Config()
    monkeypatch.delenv("CO_API_KEY", raising=False)
    status = extractor_availability(cfg)
    assert status["CohereExtractor"] == "skipped: CO_API_KEY not set"


def test_cohere_reported_active_with_api_key(monkeypatch):
    cfg = Config()
    monkeypatch.setenv("CO_API_KEY", "fake-key-for-test")
    status = extractor_availability(cfg)
    assert status["CohereExtractor"] == "active"


def test_vision_reported_disabled_by_default():
    cfg = Config()
    status = extractor_availability(cfg)
    assert status["VisionChartExtractor"] == "disabled in config"


def test_vision_reported_skipped_for_unsupported_provider():
    cfg = Config()
    cfg.vision.enabled = True
    cfg.vision.provider = "cohere"
    status = extractor_availability(cfg)
    assert status["VisionChartExtractor"].startswith("skipped: unsupported provider")


def test_vision_reported_skipped_when_model_not_pulled(monkeypatch):
    cfg = Config()
    cfg.vision.enabled = True
    monkeypatch.setattr("ddgpt.pipeline.builders.ollama_vision_is_available", lambda host, model: False)
    status = extractor_availability(cfg)
    assert status["VisionChartExtractor"].startswith("skipped")
    assert cfg.vision.model in status["VisionChartExtractor"]


def test_vision_reported_active_when_model_available(monkeypatch):
    cfg = Config()
    cfg.vision.enabled = True
    monkeypatch.setattr("ddgpt.pipeline.builders.ollama_vision_is_available", lambda host, model: True)
    status = extractor_availability(cfg)
    assert status["VisionChartExtractor"] == "active"
