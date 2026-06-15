# Stores short-term session memory: last topic, last turns, current mode.
"""
Session Memory for Admission Robot AI Brain.

This module stores short-term context per session.

Why we need it:
- Users ask follow-up questions.
- The text may contain pronouns like "it", "this faculty", "دي", "دي بكام".
- The brain must remember the previous topic.

Example:
User: "Where is engineering?"
Memory stores: current_faculty_id = engineering_and_technology

User: "How much is it?"
Text processor detects intent = fees, but no faculty.
Memory fills missing faculty = engineering_and_technology.
"""

from copy import deepcopy
import re
from typing import Any

from models import ConversationTurn, ProcessedText, SessionMemory


class MemoryManager:
    """
    In-memory session storage.

    Current implementation uses a normal Python dictionary.
    This is good for local testing and your standalone AI Brain module.

    Later, the backend/integration team can replace it with Redis
    without changing the brain logic.
    """

    def __init__(self, max_turns: int = 3) -> None:
        self.max_turns = max_turns
        self.sessions: dict[str, SessionMemory] = {}

    def get_or_create_session(
        self,
        session_id: str,
        language: str,
        mode: str,
    ) -> SessionMemory:
        """
        Get an existing session or create a new one.
        """

        if session_id not in self.sessions:
            self.sessions[session_id] = SessionMemory(
                session_id=session_id,
                language=language,
                mode=mode,
            )

        session = self.sessions[session_id]

        # Keep latest language/mode selected by the user.
        session.language = language
        session.mode = mode

        return session

    def enrich_with_memory(
        self,
        session: SessionMemory,
        processed_text: ProcessedText,
    ) -> ProcessedText:
        """
        Fill missing context from memory.

        Example:
        Current text: "How much is it?"
        Current entities: intent = fees, faculty = None
        Memory: current_faculty_id = engineering_and_technology

        Result:
        faculty becomes engineering_and_technology with match_type = memory
        """

        enriched_text = deepcopy(processed_text)
        entities = enriched_text.entities

        faculty = entities.get("faculty")
        intent = entities.get("intent")
        text_looks_follow_up = self._looks_like_follow_up(enriched_text.normalized_text)

        if (
            faculty is None
            and session.current_faculty_id is not None
            and text_looks_follow_up
        ):
            entities["faculty"] = {
                "id": session.current_faculty_id,
                "matched_alias": None,
                "match_type": "memory",
                "confidence": 0.80,
            }
            enriched_text.route_notes.append("faculty_filled_from_memory")

        if (
            intent is None
            and session.current_intent_id is not None
            and text_looks_follow_up
        ):
            entities["intent"] = {
                "id": session.current_intent_id,
                "matched_alias": None,
                "match_type": "memory",
                "confidence": 0.70,
            }
            enriched_text.route_notes.append("intent_filled_from_memory")

        enriched_text.search_query = self._rebuild_search_query(
            original_query=enriched_text.search_query,
            entities=entities,
        )

        return enriched_text

    def update_after_turn(
        self,
        session: SessionMemory,
        processed_text: ProcessedText,
    ) -> SessionMemory:
        """
        Update session memory after each processed user turn.
        """

        faculty_id = self._get_entity_id(processed_text.entities.get("faculty"))
        intent_id = self._get_entity_id(processed_text.entities.get("intent"))
        topic = self._build_topic(faculty_id, intent_id)

        if faculty_id:
            session.current_faculty_id = faculty_id

        if intent_id:
            session.current_intent_id = intent_id

        if topic:
            session.current_topic = topic

        turn = ConversationTurn(
            user_text=processed_text.raw_text,
            normalized_text=processed_text.normalized_text,
            faculty_id=faculty_id,
            intent_id=intent_id,
            topic=topic,
            mode=session.mode,
            language=session.language,
        )

        session.turns.append(turn)

        if len(session.turns) > self.max_turns:
            session.turns = session.turns[-self.max_turns :]

        return session

    def reset_session(self, session_id: str) -> None:
        """
        Delete one session from memory.
        """

        self.sessions.pop(session_id, None)

    def get_memory_debug_view(self, session: SessionMemory) -> dict[str, Any]:
        """
        Return memory in a readable format for debugging.
        """

        return {
            "session_id": session.session_id,
            "language": session.language,
            "mode": session.mode,
            "current_faculty_id": session.current_faculty_id,
            "current_intent_id": session.current_intent_id,
            "current_topic": session.current_topic,
            "turns": [
                {
                    "user_text": turn.user_text,
                    "normalized_text": turn.normalized_text,
                    "faculty_id": turn.faculty_id,
                    "intent_id": turn.intent_id,
                    "topic": turn.topic,
                    "mode": turn.mode,
                    "language": turn.language,
                }
                for turn in session.turns
            ],
        }

    def _looks_like_follow_up(self, text: str) -> bool:
        """
        Detect if the user likely refers to previous context.
        """

        follow_up_phrases = {
            "it",
            "this",
            "that",
            "there",
            "its",
            "how much is it",
            "where is it",
            "what about it",
            "دي",
            "ده",
            "دا",
            "ذلك",
            "دي بكام",
            "ده بكام",
            "مصاريفها",
            "مكانها",
            "فين هي",
            "فين ده",
            "فين دي",
            "اوراقها",
            "شروطها",
            "اقسامها",
            "تخصصاتها",
        }

        text_lower = text.lower()

        return any(
            re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text_lower)
            for phrase in follow_up_phrases
        )

    def _get_entity_id(self, entity: dict[str, Any] | None) -> str | None:
        if not entity:
            return None

        return entity.get("id")

    def _build_topic(
        self,
        faculty_id: str | None,
        intent_id: str | None,
    ) -> str | None:
        if faculty_id and intent_id:
            return f"{faculty_id}:{intent_id}"

        if faculty_id:
            return faculty_id

        if intent_id:
            return intent_id

        return None

    def _rebuild_search_query(
        self,
        original_query: str,
        entities: dict[str, Any],
    ) -> str:
        """
        Rebuild search query after memory fills missing context.
        """

        query_parts: list[str] = []

        faculty = entities.get("faculty")
        intent = entities.get("intent")

        if faculty:
            query_parts.append(f"faculty:{faculty['id']}")

        if intent:
            query_parts.append(f"intent:{intent['id']}")

        # Remove old faculty/intent markers to avoid duplicates.
        plain_query_parts = [
            part.strip()
            for part in original_query.split("|")
            if not part.strip().startswith("faculty:")
            and not part.strip().startswith("intent:")
        ]

        query_parts.extend(plain_query_parts)

        return " | ".join(query_parts)
