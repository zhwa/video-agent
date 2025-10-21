import yaml
from pathlib import Path


def test_providers_example_exists_and_parses():
    p = Path(__file__).resolve().parents[1] / "config" / "providers.example.yaml"
    assert p.exists(), f"providers.example.yaml not found at {p}"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "llm" in cfg
    assert "tts" in cfg
    assert isinstance(cfg.get("region_priority"), list)
