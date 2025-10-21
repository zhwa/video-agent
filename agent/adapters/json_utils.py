"""Shared JSON parsing utilities for adapters.

This module provides common JSON extraction and parsing functions used by
multiple LLM adapters to avoid code duplication.
"""

import json
import logging
import re
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


def extract_json_from_text(text: Any) -> Optional[Dict[str, Any]]:
    """
    Extract and parse a JSON object from text or other input.

    Attempts multiple strategies:
    1. Direct parsing if input is already a dict
    2. Direct JSON parsing if input is a string
    3. Regex extraction of first JSON object if direct parsing fails

    Args:
        text: Input text, dict, or other type

    Returns:
        Parsed JSON as dict, or None if extraction/parsing fails

    Examples:
        >>> extract_json_from_text('{"key": "value"}')
        {'key': 'value'}

        >>> extract_json_from_text('Here is JSON: {"a": 1} at end')
        {'a': 1}

        >>> extract_json_from_text({'already': 'dict'})
        {'already': 'dict'}

        >>> extract_json_from_text('no json here')
        None
    """
    # If already a dict, return as-is
    if isinstance(text, dict):
        logger.debug("Input is already a dict")
        return text

    # If not a string, can't extract JSON
    if not isinstance(text, str):
        logger.debug("Input is not a string or dict, cannot extract JSON")
        return None

    # Try direct JSON parsing first
    try:
        parsed = json.loads(text)
        logger.debug("Successfully parsed JSON directly")
        return parsed
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, attempting extraction")

    # Try to extract first JSON object from text
    # This regex finds the first { and matches balanced braces
    m = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", text, flags=re.DOTALL)
    if not m:
        logger.debug("No JSON object found in text")
        return None

    candidate = m.group(0)
    try:
        parsed = json.loads(candidate)
        logger.debug("Successfully extracted and parsed JSON from text")
        return parsed
    except json.JSONDecodeError as e:
        logger.debug("Extracted JSON is invalid: %s", e)
        return None


def extract_json_array_from_text(text: Any) -> Optional[list]:
    """
    Extract and parse a JSON array from text.

    Similar to extract_json_from_text but specifically for arrays.

    Args:
        text: Input text, list, or other type

    Returns:
        Parsed JSON array as list, or None if extraction/parsing fails
    """
    # If already a list, return as-is
    if isinstance(text, list):
        logger.debug("Input is already a list")
        return text

    # If not a string, can't extract
    if not isinstance(text, str):
        logger.debug("Input is not a string or list, cannot extract JSON array")
        return None

    # Try direct parsing first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            logger.debug("Successfully parsed JSON array directly")
            return parsed
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, attempting extraction")

    # Try to extract first JSON array from text
    m = re.search(r"\[(?:[^\[\]]|(?:\[[^\[\]]*\]))*\]", text, flags=re.DOTALL)
    if not m:
        logger.debug("No JSON array found in text")
        return None

    candidate = m.group(0)
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            logger.debug("Successfully extracted and parsed JSON array from text")
            return parsed
    except json.JSONDecodeError as e:
        logger.debug("Extracted JSON array is invalid: %s", e)

    return None


def safe_json_parse(text: str, default: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Safely parse JSON text with a fallback default.

    Useful for situations where you want a guaranteed dict return value.

    Args:
        text: JSON string to parse
        default: Default dict to return if parsing fails (default: empty dict)

    Returns:
        Parsed JSON dict or default value
    """
    if default is None:
        default = {}

    result = extract_json_from_text(text)
    if result is not None:
        return result
    return default
