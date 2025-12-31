"""Reconciliation agent for detecting and merging duplicate people.

This module identifies potential duplicate people in the genealogy database
using fuzzy name matching, date/place comparison, and vector similarity.
"""

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from src.backend.genealogy_ai.storage.sqlite import Event, GenealogyDatabase, Name, Person


@dataclass
class DuplicateCandidate:
    """A potential duplicate person match."""

    person1_id: int
    person1_name: str
    person2_id: int
    person2_name: str
    confidence: float
    reasons: list[str]

    def __str__(self) -> str:
        """Format duplicate candidate for display."""
        reasons_str = ", ".join(self.reasons)
        return (
            f"{self.person1_name} (ID: {self.person1_id}) ↔ "
            f"{self.person2_name} (ID: {self.person2_id}) "
            f"[confidence: {self.confidence:.2f}] ({reasons_str})"
        )


class ReconciliationAgent:
    """Detect and suggest merges for duplicate people."""

    def __init__(
        self,
        db: GenealogyDatabase,
        name_threshold: float = 0.85,
        min_confidence: float = 0.60,
    ):
        """Initialize the reconciliation agent.

        Args:
            db: Database instance
            name_threshold: Minimum fuzzy match score for names (0-1)
            min_confidence: Minimum overall confidence to report (0-1)
        """
        self.db = db
        self.name_threshold = name_threshold
        self.min_confidence = min_confidence

    def find_duplicates(self) -> list[DuplicateCandidate]:
        """Find all potential duplicate people.

        Returns:
            List of duplicate candidates sorted by confidence (highest first)
        """
        session = self.db.get_session()
        try:
            people = session.query(Person).all()
            candidates = []

            # Compare each pair of people
            for i, person1 in enumerate(people):
                for person2 in people[i + 1 :]:
                    candidate = self._compare_people(person1, person2, session)
                    if candidate and candidate.confidence >= self.min_confidence:
                        candidates.append(candidate)

            # Sort by confidence (highest first)
            candidates.sort(key=lambda x: x.confidence, reverse=True)
            return candidates
        finally:
            session.close()

    def _compare_people(
        self, person1: Person, person2: Person, session: Session
    ) -> DuplicateCandidate | None:
        """Compare two people for potential duplication.

        Args:
            person1: First person
            person2: Second person
            session: Database session

        Returns:
            DuplicateCandidate if match found, None otherwise
        """
        reasons = []
        scores = []

        # Compare primary names
        name_score = fuzz.ratio(
            person1.primary_name.lower(), person2.primary_name.lower()
        ) / 100.0

        if name_score >= self.name_threshold:
            reasons.append(f"name match: {name_score:.2f}")
            scores.append(name_score)
        else:
            # Check alternate names
            person1_names = {person1.primary_name.lower()}
            person1_names.update(n.name.lower() for n in person1.names)

            person2_names = {person2.primary_name.lower()}
            person2_names.update(n.name.lower() for n in person2.names)

            # Check if any names match
            max_variant_score = 0.0
            for n1 in person1_names:
                for n2 in person2_names:
                    score = fuzz.ratio(n1, n2) / 100.0
                    max_variant_score = max(max_variant_score, score)

            if max_variant_score >= self.name_threshold:
                reasons.append(f"name variant match: {max_variant_score:.2f}")
                scores.append(max_variant_score)
            else:
                # Names don't match - unlikely to be duplicate
                return None

        # Compare birth dates if both exist
        person1_birth = self._get_event(person1.id, "birth", session)
        person2_birth = self._get_event(person2.id, "birth", session)

        if person1_birth and person2_birth:
            if person1_birth.date and person2_birth.date:
                if person1_birth.date == person2_birth.date:
                    reasons.append("same birth date")
                    scores.append(1.0)
                else:
                    # Different birth dates - strong signal they're different people
                    reasons.append("different birth dates")
                    scores.append(0.0)

        # Compare birth places if both exist
        if person1_birth and person2_birth:
            if person1_birth.place and person2_birth.place:
                place_score = (
                    fuzz.ratio(
                        person1_birth.place.lower(), person2_birth.place.lower()
                    )
                    / 100.0
                )
                if place_score >= 0.8:
                    reasons.append(f"similar birth place: {place_score:.2f}")
                    scores.append(place_score * 0.8)  # Weight place less than name

        # Compare death dates if both exist
        person1_death = self._get_event(person1.id, "death", session)
        person2_death = self._get_event(person2.id, "death", session)

        if person1_death and person2_death:
            if person1_death.date and person2_death.date:
                if person1_death.date == person2_death.date:
                    reasons.append("same death date")
                    scores.append(1.0)

        # Calculate overall confidence
        if not scores:
            return None

        confidence = sum(scores) / len(scores)

        return DuplicateCandidate(
            person1_id=person1.id,
            person1_name=person1.primary_name,
            person2_id=person2.id,
            person2_name=person2.primary_name,
            confidence=confidence,
            reasons=reasons,
        )

    def _get_event(self, person_id: int, event_type: str, session: Session) -> Event | None:
        """Get an event for a person.

        Args:
            person_id: Person ID
            event_type: Event type (birth, death, etc.)
            session: Database session

        Returns:
            Event if found, None otherwise
        """
        return (
            session.query(Event)
            .filter(Event.person_id == person_id, Event.event_type == event_type)
            .first()
        )
