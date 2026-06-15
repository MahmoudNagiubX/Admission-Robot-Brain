# Cleans STT text, fixes numbers, protects phone/ID/email, corrects domain terms.
"""
Text Intelligence Layer.

This file prepares the text before it enters the AI Brain.

Current step:
- keep raw text
- remove extra spaces
- prepare normalized/corrected/search versions

Future steps:
- Arabic normalization
- English/Arabic digit normalization
- spoken number conversion
- phone / ID / email protection
- faculty name detection
- fuzzy correction
"""

import re

from models import ProcessedText


class TextProcessor:
    """
    Cleans and prepares text before brain routing.
    """

    def process(self, raw_text: str, language: str) -> ProcessedText:
        """
        Process raw STT text into a clean structured package.
        """

        normalized_text = self._normalize_spaces(raw_text)

        # For now, these are the same.
        # Later each one will have a different job.
        protected_text = normalized_text
        corrected_text = normalized_text
        search_query = normalized_text

        return ProcessedText(
            raw_text=raw_text,
            normalized_text=normalized_text,
            protected_text=protected_text,
            corrected_text=corrected_text,
            search_query=search_query,
            language=language,
            entities={},
            route_notes=[
                "raw_text_saved",
                "extra_spaces_removed",
                "text_processor_step_2_completed",
            ],
        )

    def _normalize_spaces(self, text: str) -> str:
        """
        Remove leading/trailing spaces and replace multiple spaces with one space.
        """

        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text