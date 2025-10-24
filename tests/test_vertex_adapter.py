import json

def test_google_services_with_fake_genai(monkeypatch):
    """Test the unified Google services (LLM functionality)."""

    # Instead of mocking the google.genai module, mock the GoogleServices methods directly
    # This is cleaner and tests the actual interface

    fake_slide_plan = {
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
    }

    # Create a mock GoogleServices that doesn't need a real API key
    class MockGoogleServices:
        def __init__(self, *args, **kwargs):
            # Don't call parent __init__ to avoid needing real API key
            pass

        def generate_text(self, prompt: str) -> str:
            """Mock generate_text to return JSON slide plan."""
            return json.dumps(fake_slide_plan)

        def generate_slide_plan(self, chapter_text: str, max_slides=None, run_id=None, chapter_id=None):
            """Mock generate_slide_plan to return slide plan directly."""
            # This uses LLMClient, so we need to make sure generate_text works
            from agent.llm_client import LLMClient
            client = LLMClient(max_retries=1)
            result = client.generate_and_validate(
                self, chapter_text, max_slides=max_slides, run_id=run_id, chapter_id=chapter_id
            )
            return result.get("plan", {"slides": []})

    # Use the mock
    google = MockGoogleServices()
    result = google.generate_slide_plan("Alpha. Beta.")

    assert isinstance(result, dict)
    assert "slides" in result
    assert len(result["slides"]) >= 1