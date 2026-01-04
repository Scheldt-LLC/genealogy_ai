"""Reconciliation agent for detecting and merging duplicate people.

This module identifies potential duplicate people in the genealogy database
using fuzzy name matching, date/place comparison, and vector similarity.
"""

import re
from dataclasses import dataclass
from typing import cast

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from src.backend.genealogy_ai.storage.sqlite import Event, GenealogyDatabase, Person


def normalize_name(name: str) -> str:
    """Normalize a name for better matching.

    Handles variations like:
    - "O'Byrne, John" vs "John O'Byrne"
    - Punctuation differences (apostrophes, hyphens)
    - "Last, First" vs "First Last" ordering

    Args:
        name: The name to normalize

    Returns:
        Normalized name with parts sorted alphabetically
    """
    # Convert to lowercase
    normalized = name.lower()

    # Remove punctuation (keep spaces)
    normalized = re.sub(r"['\-,.]", " ", normalized)

    # Split into parts and remove empty strings
    parts = [part for part in normalized.split() if part]

    # Sort parts alphabetically for consistent comparison
    parts.sort()

    # Join back together
    return " ".join(parts)


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
        weighted_scores = []  # (score, weight) tuples

        # Compare primary names using token_set_ratio (handles middle names better)
        norm_name1 = normalize_name(cast(str, person1.primary_name))
        norm_name2 = normalize_name(cast(str, person2.primary_name))

        # Use token_set_ratio for better subset matching (Harry Scheldt vs Harry Vernon Scheldt)
        name_score = fuzz.token_set_ratio(norm_name1, norm_name2) / 100.0

        # Also try regular ratio for exact matches
        exact_score = fuzz.ratio(norm_name1, norm_name2) / 100.0

        # Use the better of the two scores
        best_name_score = max(name_score, exact_score)

        if best_name_score >= self.name_threshold:
            reasons.append(f"name match: {best_name_score:.2f}")
            weighted_scores.append((best_name_score, 1.0))  # Weight: 1.0
        else:
            # Check alternate names (also normalized)
            person1_names = {normalize_name(cast(str, person1.primary_name))}
            person1_names.update(normalize_name(n.name) for n in person1.names)

            person2_names = {normalize_name(cast(str, person2.primary_name))}
            person2_names.update(normalize_name(n.name) for n in person2.names)

            # Check if any names match using token_set_ratio
            max_variant_score = 0.0
            for n1 in person1_names:
                for n2 in person2_names:
                    token_score = fuzz.token_set_ratio(n1, n2) / 100.0
                    ratio_score = fuzz.ratio(n1, n2) / 100.0
                    score = max(token_score, ratio_score)
                    max_variant_score = max(max_variant_score, score)

            if max_variant_score >= self.name_threshold:
                reasons.append(f"name variant match: {max_variant_score:.2f}")
                weighted_scores.append((max_variant_score, 1.0))  # Weight: 1.0
            else:
                # Check if we have a reasonable name similarity (lower threshold)
                # This allows birth date to be the deciding factor
                if best_name_score >= 0.60 or max_variant_score >= 0.60:
                    name_to_use = max(best_name_score, max_variant_score)
                    reasons.append(f"partial name match: {name_to_use:.2f}")
                    weighted_scores.append((name_to_use, 0.5))  # Lower weight for partial match
                else:
                    # Check for maiden/married name pattern (same first name, different last name)
                    # Split names to get first names
                    name1_parts = norm_name1.split()
                    name2_parts = norm_name2.split()

                    if name1_parts and name2_parts:
                        # Check if first names match well
                        first_name_score = fuzz.ratio(name1_parts[0], name2_parts[0]) / 100.0

                        if first_name_score >= 0.90:  # First names very similar
                            reasons.append(f"first name match: {first_name_score:.2f}")
                            # Use lower weight - birth date will be the deciding factor
                            weighted_scores.append((first_name_score, 0.3))
                        else:
                            # Names are too different - unlikely to be duplicate
                            return None
                    else:
                        return None

        # Compare birth dates if both exist - THIS IS A VERY STRONG SIGNAL
        person1_birth = self._get_event(cast(int, person1.id), "birth", session)
        person2_birth = self._get_event(cast(int, person2.id), "birth", session)

        birth_date_match = False
        if person1_birth and person2_birth:
            birth1_date = cast(str | None, person1_birth.date)
            birth2_date = cast(str | None, person2_birth.date)
            if birth1_date and birth2_date:
                if birth1_date == birth2_date:
                    reasons.append("exact birth date match")
                    weighted_scores.append((1.0, 3.0))  # Weight: 3.0 - VERY STRONG SIGNAL
                    birth_date_match = True
                else:
                    # Different birth dates - strong signal they're different people
                    reasons.append("different birth dates")
                    weighted_scores.append((0.0, 2.0))  # High weight for mismatch too

        # Compare birth places if both exist
        if person1_birth and person2_birth:
            birth1_place = cast(str | None, person1_birth.place)
            birth2_place = cast(str | None, person2_birth.place)
            if birth1_place and birth2_place:
                place_score = (
                    fuzz.ratio(person1_birth.place.lower(), person2_birth.place.lower()) / 100.0
                )
                if place_score >= 0.8:
                    reasons.append(f"similar birth place: {place_score:.2f}")
                    weighted_scores.append((place_score, 0.5))  # Weight: 0.5 - supporting evidence

        # Compare death dates if both exist
        person1_death = self._get_event(cast(int, person1.id), "death", session)
        person2_death = self._get_event(cast(int, person2.id), "death", session)

        if person1_death and person2_death:
            death1_date = cast(str | None, person1_death.date)
            death2_date = cast(str | None, person2_death.date)
            if death1_date and death2_date:
                if death1_date == death2_date:
                    reasons.append("exact death date match")
                    weighted_scores.append((1.0, 2.0))  # Weight: 2.0 - strong signal
                else:
                    reasons.append("different death dates")
                    weighted_scores.append((0.0, 1.5))  # Penalty for mismatch

        # Calculate overall confidence using weighted average
        if not weighted_scores:
            return None

        total_weighted_score = sum(score * weight for score, weight in weighted_scores)
        total_weight = sum(weight for _, weight in weighted_scores)
        confidence = total_weighted_score / total_weight if total_weight > 0 else 0.0

        # Special case: Birth date match + reasonable name = very high confidence
        if birth_date_match and confidence >= 0.75:
            confidence = max(confidence, 0.95)  # Boost to near-certain

        return DuplicateCandidate(
            person1_id=cast(int, person1.id),
            person1_name=cast(str, person1.primary_name),
            person2_id=cast(int, person2.id),
            person2_name=cast(str, person2.primary_name),
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
