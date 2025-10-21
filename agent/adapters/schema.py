from typing import Any, Dict, List, Tuple


REQUIRED_SLIDE_KEYS = [
    "id",
    "title",
    "bullets",
    "visual_prompt",
    "estimated_duration_sec",
    "speaker_notes",
]


def validate_slide_plan(plan: Any) -> Tuple[bool, List[str]]:
    """Validate the structure of a slide plan using simple structural checks.

    Returns (True, []) if valid, otherwise (False, [error messages]).
    """
    errors: List[str] = []
    if not isinstance(plan, dict):
        errors.append("Plan must be a JSON object/dict.")
        return False, errors
    if "slides" not in plan:
        errors.append("Missing 'slides' key.")
        return False, errors
    slides = plan["slides"]
    if not isinstance(slides, list):
        errors.append("'slides' must be a list.")
        return False, errors
    for idx, s in enumerate(slides):
        if not isinstance(s, dict):
            errors.append(f"Slide at index {idx} must be an object.")
            continue
        for key in REQUIRED_SLIDE_KEYS:
            if key not in s:
                errors.append(f"Slide at index {idx} missing required key: {key}")
        # type checks
        if "bullets" in s and not isinstance(s["bullets"], list):
            errors.append(f"Slide at index {idx} 'bullets' must be a list")
        if "estimated_duration_sec" in s and not isinstance(s["estimated_duration_sec"], int):
            # allow ints only for simplicity
            errors.append(f"Slide at index {idx} 'estimated_duration_sec' must be an int")

    return (len(errors) == 0), errors
