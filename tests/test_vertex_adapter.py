import sys
import types
import json
from agent.google import GoogleServices

def test_google_services_with_fake_genai(monkeypatch):
    """Test the unified Google services (LLM functionality)."""
    # Fake google.genai module
    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")

    class FakeClient:
        class FakeModels:
            @staticmethod
            def generate_content(model, contents):
                # Return fake response for LLM
                response = types.SimpleNamespace()
                response.text = json.dumps({
                    "slides": [
                        {
                            "id": "s01",
                            "title": "Google Test",
                            "bullets": ["Unified adapter"],
                            "visual_prompt": "test image",
                            "estimated_duration_sec": 25,
                            "speaker_notes": "test notes"
                        }
                    ]
                })
                return response
        
        def __init__(self, api_key):
            self.models = self.FakeModels()
    
    genai.Client = FakeClient
    google.genai = genai

    sys.modules["google"] = google
    sys.modules["google.genai"] = genai

    # Set API key in environment
    import os
    os.environ["GOOGLE_API_KEY"] = "fake-key-for-testing"

    google = GoogleServices(llm_model="gemini-test")
    result = google.generate_slide_plan("Alpha. Beta.")
    assert isinstance(result, dict)
    assert "slides" in result
    assert len(result["slides"]) >= 1

    # Cleanup
    del sys.modules["google.genai"]
    del sys.modules["google"]
    del os.environ["GOOGLE_API_KEY"]
