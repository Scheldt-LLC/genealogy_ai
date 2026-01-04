"""Entity building agent for consolidating extracted genealogical data.

This module implements a robust entity building pipeline that:
1. Stages extracted entities before database insertion
2. Consolidates entities to build complete records
3. Matches entities using reconciliation logic
4. Auto-approves high-confidence matches (≥95%)
5. Creates match proposals for human review (< 95%)
"""

import json
import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy.orm import Session

from src.backend.genealogy_ai.agents.reconcile_people import (
    DuplicateCandidate,
    ReconciliationAgent,
    normalize_name,
)
from src.backend.genealogy_ai.schemas import ExtractionResult
from src.backend.genealogy_ai.storage.sqlite import (
    EntityMatch,
    GenealogyDatabase,
    PendingEvent,
    PendingPerson,
    PendingRelationship,
    Person,
)


@dataclass
class ConsolidatedEntity:
    """A consolidated entity built from multiple extractions."""

    primary_name: str
    name_variants: list[str]
    confidence: float
    notes: list[str]
    events: list[dict]  # List of event dictionaries
    pending_person_ids: list[int]  # IDs of pending people consolidated into this entity
    source_document_ids: list[int]


class EntityBuilder:
    """Build complete entities from staged extractions."""

    def __init__(
        self,
        db: GenealogyDatabase,
        name_threshold: float = 0.85,
        auto_approve_threshold: float = 0.95,
    ):
        """Initialize the entity builder.

        Args:
            db: Database instance
            name_threshold: Minimum fuzzy match score for names (0-1)
            auto_approve_threshold: Confidence threshold for auto-approval (0-1)
        """
        self.db = db
        self.name_threshold = name_threshold
        self.auto_approve_threshold = auto_approve_threshold
        self.reconciliation_agent = ReconciliationAgent(
            db=db, name_threshold=name_threshold, min_confidence=0.6
        )

    def stage_extraction(
        self,
        extraction_result: ExtractionResult,
        batch_id: str,
        document_id: int,
        family_name: str | None = None,
        family_side: str | None = None,
    ) -> dict[str, int]:
        """Stage extracted entities in pending tables.

        Args:
            extraction_result: Extracted entities
            batch_id: Unique ID for this extraction batch
            document_id: Source document ID
            family_name: Optional family name to assign
            family_side: Optional family side (maternal/paternal)

        Returns:
            Dictionary with counts of staged entities
        """
        session = self.db.get_session()
        try:
            people_count = 0
            events_count = 0
            relationships_count = 0
            name_to_pending_id: dict[str, int] = {}

            # Stage people
            for person_data in extraction_result.people:
                pending_person = PendingPerson(
                    extraction_batch_id=batch_id,
                    primary_name=person_data.primary_name,
                    name_variants=json.dumps(person_data.name_variants),
                    confidence=person_data.confidence,
                    notes=person_data.notes,
                    source_document_id=document_id,
                    family_name=family_name,
                    family_side=family_side,
                    status="pending",
                )
                session.add(pending_person)
                session.flush()  # Get ID
                people_count += 1
                name_to_pending_id[person_data.primary_name] = cast(int, pending_person.id)

            # Stage events
            for event_data in extraction_result.events:
                pending_person_id = name_to_pending_id.get(event_data.person_name)
                pending_event = PendingEvent(
                    extraction_batch_id=batch_id,
                    pending_person_id=pending_person_id,
                    person_name=event_data.person_name,
                    event_type=event_data.event_type,
                    date=event_data.date,
                    place=event_data.place,
                    description=event_data.notes,
                    confidence=event_data.confidence,
                    source_document_id=document_id,
                    status="pending",
                )
                session.add(pending_event)
                events_count += 1

            # Stage relationships
            for rel_data in extraction_result.relationships:
                pending_person1_id = name_to_pending_id.get(rel_data.person1)
                pending_person2_id = name_to_pending_id.get(rel_data.person2)
                pending_rel = PendingRelationship(
                    extraction_batch_id=batch_id,
                    pending_person1_id=pending_person1_id,
                    pending_person2_id=pending_person2_id,
                    person1_name=rel_data.person1,
                    person2_name=rel_data.person2,
                    relationship_type=rel_data.relationship_type,
                    confidence=rel_data.confidence,
                    notes=rel_data.notes,
                    source_document_id=document_id,
                    status="pending",
                )
                session.add(pending_rel)
                relationships_count += 1

            session.commit()

            return {
                "people": people_count,
                "events": events_count,
                "relationships": relationships_count,
            }

        finally:
            session.close()

    def consolidate_batch(self, batch_id: str) -> list[ConsolidatedEntity]:
        """Consolidate pending entities within a batch.

        Groups similar pending people together and merges their data
        to create complete entity records.

        Args:
            batch_id: Extraction batch ID

        Returns:
            List of consolidated entities
        """
        session = self.db.get_session()
        try:
            # Get all pending people in this batch
            pending_people = (
                session.query(PendingPerson)
                .filter(PendingPerson.extraction_batch_id == batch_id)
                .filter(PendingPerson.status == "pending")
                .all()
            )

            # Get all pending events in this batch
            pending_events = (
                session.query(PendingEvent)
                .filter(PendingEvent.extraction_batch_id == batch_id)
                .filter(PendingEvent.status == "pending")
                .all()
            )

            # Group similar people together
            groups: list[list[PendingPerson]] = []
            processed = set()

            for i, person1 in enumerate(pending_people):
                if person1.id in processed:
                    continue

                group = [person1]
                processed.add(cast(int, person1.id))

                # Find similar people in this batch
                for person2 in pending_people[i + 1 :]:
                    if person2.id in processed:
                        continue

                    # Use same matching logic as reconciliation
                    if self._are_similar(person1, person2, session):
                        group.append(person2)
                        processed.add(cast(int, person2.id))

                groups.append(group)

            # Build consolidated entities from groups
            consolidated: list[ConsolidatedEntity] = []

            for group in groups:
                # Merge all people in this group
                entity = self._merge_pending_people(group, pending_events)
                consolidated.append(entity)

            return consolidated

        finally:
            session.close()

    def _are_similar(
        self, person1: PendingPerson, person2: PendingPerson, session: Session
    ) -> bool:
        """Check if two pending people are similar enough to merge.

        Uses same logic as ReconciliationAgent but for pending people.

        Args:
            person1: First pending person
            person2: Second pending person
            session: Database session

        Returns:
            True if people should be merged
        """
        from rapidfuzz import fuzz

        # Compare names
        norm_name1 = normalize_name(cast(str, person1.primary_name))
        norm_name2 = normalize_name(cast(str, person2.primary_name))

        name_score = fuzz.token_set_ratio(norm_name1, norm_name2) / 100.0
        exact_score = fuzz.ratio(norm_name1, norm_name2) / 100.0
        best_name_score = max(name_score, exact_score)

        # If names match well enough, they're similar
        if best_name_score >= self.name_threshold:
            return True

        # Check birth dates if available
        person1_events = (
            session.query(PendingEvent)
            .filter(
                PendingEvent.pending_person_id == person1.id,
                PendingEvent.event_type == "birth",
            )
            .all()
        )

        person2_events = (
            session.query(PendingEvent)
            .filter(
                PendingEvent.pending_person_id == person2.id,
                PendingEvent.event_type == "birth",
            )
            .all()
        )

        if person1_events and person2_events:
            birth1_date = person1_events[0].date
            birth2_date = person2_events[0].date

            # Same birth date + partial name match = similar
            if birth1_date and birth2_date and birth1_date == birth2_date:
                if best_name_score >= 0.6:
                    return True

        return False

    def _merge_pending_people(
        self, group: list[PendingPerson], all_events: list[PendingEvent]
    ) -> ConsolidatedEntity:
        """Merge a group of pending people into one consolidated entity.

        Args:
            group: List of pending people to merge
            all_events: All pending events in the batch

        Returns:
            Consolidated entity with merged data
        """
        # Choose best primary name (prioritize mixed case, more words, longer)
        def name_quality(person: PendingPerson) -> tuple[int, int, int]:
            name = cast(str, person.primary_name)
            has_mixed_case = name != name.upper() and name != name.lower()
            word_count = len(name.split())
            length = len(name)
            return (1 if has_mixed_case else 0, word_count, length)

        best_person = max(group, key=name_quality)
        primary_name = cast(str, best_person.primary_name)

        # Collect all name variants
        name_variants = set()
        for person in group:
            # Add the primary name as a variant if it's not the chosen one
            if person.primary_name != primary_name:
                name_variants.add(cast(str, person.primary_name))

            # Add stored variants
            if person.name_variants:
                try:
                    variants = json.loads(cast(str, person.name_variants))
                    name_variants.update(variants)
                except json.JSONDecodeError:
                    pass

        # Collect all notes
        notes = []
        for person in group:
            if person.notes:
                notes.append(cast(str, person.notes))

        # Calculate average confidence
        confidences = [p.confidence for p in group if p.confidence is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        # Collect all events for people in this group
        person_ids = {cast(int, p.id) for p in group}
        events = []
        for event in all_events:
            if event.pending_person_id in person_ids:
                events.append(
                    {
                        "event_type": event.event_type,
                        "date": event.date,
                        "place": event.place,
                        "description": event.description,
                        "confidence": event.confidence,
                        "source_document_id": event.source_document_id,
                    }
                )

        # Collect source document IDs
        source_docs = {
            cast(int, p.source_document_id) for p in group if p.source_document_id is not None
        }

        return ConsolidatedEntity(
            primary_name=primary_name,
            name_variants=list(name_variants),
            confidence=avg_confidence,
            notes=notes,
            events=events,
            pending_person_ids=[cast(int, p.id) for p in group],
            source_document_ids=list(source_docs),
        )

    def find_matches(self, batch_id: str) -> list[EntityMatch]:
        """Find matches between pending entities and existing people.

        Creates EntityMatch records for all potential matches.

        Args:
            batch_id: Extraction batch ID

        Returns:
            List of entity match records
        """
        session = self.db.get_session()
        try:
            # Get consolidated entities
            consolidated = self.consolidate_batch(batch_id)

            # Get all existing people
            existing_people = session.query(Person).all()

            matches = []

            for entity in consolidated:
                # For each consolidated entity, find best match with existing people
                best_match = None
                best_confidence = 0.0
                best_reasons = []

                for existing_person in existing_people:
                    # Create a temporary comparison using reconciliation logic
                    candidate = self._compare_consolidated_to_existing(
                        entity, existing_person, session
                    )

                    if candidate and candidate.confidence > best_confidence:
                        best_confidence = candidate.confidence
                        best_match = existing_person
                        best_reasons = candidate.reasons

                # Create match record if found
                if best_match and best_confidence >= 0.60:  # Min threshold
                    match_record = EntityMatch(
                        extraction_batch_id=batch_id,
                        match_type="pending_to_existing",
                        pending_person_id=entity.pending_person_ids[0],  # Primary pending ID
                        existing_person_id=cast(int, best_match.id),
                        confidence=best_confidence,
                        reasons=json.dumps(best_reasons),
                        status="pending",
                    )
                    session.add(match_record)
                    matches.append(match_record)

            session.commit()
            return matches

        finally:
            session.close()

    def _compare_consolidated_to_existing(
        self, entity: ConsolidatedEntity, existing_person: Person, session: Session
    ) -> DuplicateCandidate | None:
        """Compare a consolidated entity to an existing person.

        Uses the same logic as ReconciliationAgent.

        Args:
            entity: Consolidated entity
            existing_person: Existing person record
            session: Database session

        Returns:
            DuplicateCandidate if match found
        """
        from rapidfuzz import fuzz

        reasons = []
        weighted_scores = []

        # Compare names
        norm_entity_name = normalize_name(entity.primary_name)
        norm_existing_name = normalize_name(cast(str, existing_person.primary_name))

        name_score = fuzz.token_set_ratio(norm_entity_name, norm_existing_name) / 100.0
        exact_score = fuzz.ratio(norm_entity_name, norm_existing_name) / 100.0
        best_name_score = max(name_score, exact_score)

        if best_name_score >= self.name_threshold:
            reasons.append(f"name match: {best_name_score:.2f}")
            weighted_scores.append((best_name_score, 1.0))
        elif best_name_score >= 0.60:
            reasons.append(f"partial name match: {best_name_score:.2f}")
            weighted_scores.append((best_name_score, 0.5))
        else:
            return None

        # Compare birth dates if available
        entity_birth_events = [e for e in entity.events if e["event_type"] == "birth"]
        existing_birth = self.reconciliation_agent._get_event(
            cast(int, existing_person.id), "birth", session
        )

        birth_date_match = False
        if entity_birth_events and existing_birth and existing_birth.date:
            entity_birth_date = entity_birth_events[0].get("date")
            if entity_birth_date == existing_birth.date:
                reasons.append("exact birth date match")
                weighted_scores.append((1.0, 3.0))  # Very strong signal
                birth_date_match = True
            else:
                reasons.append("different birth dates")
                weighted_scores.append((0.0, 2.0))

        # Calculate confidence
        if not weighted_scores:
            return None

        total_weighted_score = sum(score * weight for score, weight in weighted_scores)
        total_weight = sum(weight for _, weight in weighted_scores)
        confidence = total_weighted_score / total_weight if total_weight > 0 else 0.0

        # Special boost for birth date + name match
        if birth_date_match and confidence >= 0.75:
            confidence = max(confidence, 0.95)

        return DuplicateCandidate(
            person1_id=entity.pending_person_ids[0],
            person1_name=entity.primary_name,
            person2_id=cast(int, existing_person.id),
            person2_name=cast(str, existing_person.primary_name),
            confidence=confidence,
            reasons=reasons,
        )

    def process_batch(
        self, batch_id: str, auto_approve: bool = True
    ) -> dict[str, int | list[int]]:
        """Process a batch of staged entities.

        Consolidates entities, finds matches, auto-approves high-confidence matches,
        and creates review tasks for uncertain matches.

        Args:
            batch_id: Extraction batch ID
            auto_approve: Whether to auto-approve matches ≥ threshold

        Returns:
            Dictionary with processing results
        """
        # Find all matches (this commits them to the database)
        self.find_matches(batch_id)

        auto_approved = 0
        needs_review = 0
        review_ids = []

        session = self.db.get_session()
        try:
            # Re-query matches from the database to get fresh attached instances
            matches = (
                session.query(EntityMatch)
                .filter_by(extraction_batch_id=batch_id, status="pending")
                .all()
            )

            if auto_approve:
                for match in matches:
                    if match.confidence >= self.auto_approve_threshold:
                        # Auto-approve and merge
                        self._approve_match(match, session)
                        auto_approved += 1
                    else:
                        # Needs human review
                        needs_review += 1
                        review_ids.append(cast(int, match.id))
            else:
                needs_review = len(matches)
                review_ids = [cast(int, m.id) for m in matches]

            session.commit()
        finally:
            session.close()

        return {
            "total_matches": len(matches),
            "auto_approved": auto_approved,
            "needs_review": needs_review,
            "review_ids": review_ids,
        }

    def _approve_match(self, match: EntityMatch, session: Session) -> None:
        """Approve a match and merge the entities.

        Args:
            match: Entity match to approve
            session: Database session
        """
        if match.match_type == "pending_to_existing":
            # Merge pending entity into existing person
            pending_person = (
                session.query(PendingPerson).filter_by(id=match.pending_person_id).first()
            )
            if not pending_person:
                return

            existing_person_id = cast(int, match.existing_person_id)

            # Add name variants
            if pending_person.name_variants:
                try:
                    variants = json.loads(cast(str, pending_person.name_variants))
                    for variant in variants:
                        self.db.add_name(existing_person_id, variant)
                except json.JSONDecodeError:
                    pass

            # Transfer events
            pending_events = (
                session.query(PendingEvent)
                .filter_by(pending_person_id=pending_person.id)
                .all()
            )

            for event in pending_events:
                self.db.add_event(
                    person_id=existing_person_id,
                    event_type=cast(str, event.event_type),
                    date=event.date,
                    place=event.place,
                    confidence=event.confidence,
                    description=event.description,
                    source_document_id=cast(int, event.source_document_id)
                    if event.source_document_id
                    else None,
                )
                event.status = "approved"

            # Mark pending person as approved
            pending_person.status = "approved"
            match.status = "approved"


def generate_batch_id() -> str:
    """Generate a unique batch ID for entity extraction."""
    return str(uuid.uuid4())
