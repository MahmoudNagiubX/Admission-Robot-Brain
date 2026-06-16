"""
Console display utilities for Admission Robot.
Handles visual formatting for Right-To-Left (RTL) languages in standard terminals.
"""

import os
import re

def contains_arabic(text: str) -> bool:
    """Check if the text contains Arabic characters."""
    if not isinstance(text, str):
        return False
    return bool(re.search(r"[\u0600-\u06FF]", text))

def format_for_terminal(text: str) -> str:
    """
    Format text for terminal display.
    If it contains Arabic and the fix is enabled, reshape and apply bidi algorithm.
    Otherwise, return the original text.
    """
    if not isinstance(text, str):
        return str(text)

    enable_fix = str(os.getenv("ENABLE_ARABIC_TERMINAL_FIX", "false")).lower() == "true"
    
    if not enable_fix or not contains_arabic(text):
        return text

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except ImportError:
        # If packages are missing, fail gracefully and return original text
        return text
