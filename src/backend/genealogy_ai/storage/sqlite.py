"""SQLite database for structured genealogical data.

This module defines the database schema and provides access to genealogical facts.
This is the source of truth for extracted information.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Document(Base):
    """Source document record."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False, unique=True)
    page = Column(Integer)
    ocr_text = Column(Text)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, source='{self.source}', page={self.page})>"


class Person(Base):
    """Person entity."""

    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    primary_name = Column(String, nullable=False)
    notes = Column(Text)
    confidence = Column(Float)
    source_document_id = Column(Integer, ForeignKey("documents.id"))
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

    # Relationships
    names = relationship("Name", back_populates="person", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="person", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Person(id={self.id}, name='{self.primary_name}')>"


class Name(Base):
    """Alternate names for a person (including spellings, maiden names, etc.)."""

    __tablename__ = "names"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    name = Column(String, nullable=False)
    name_type = Column(String)  # birth, married, nickname, variant, etc.
    confidence = Column(Float)

    # Relationships
    person = relationship("Person", back_populates="names")

    def __repr__(self) -> str:
        return f"<Name(id={self.id}, person_id={self.person_id}, name='{self.name}')>"


class Event(Base):
    """Life event (birth, death, marriage, etc.)."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    event_type = Column(String, nullable=False)  # birth, death, marriage, etc.
    date = Column(String)  # Stored as string to handle uncertain/partial dates
    place = Column(String)
    description = Column(Text)
    confidence = Column(Float)
    source_document_id = Column(Integer, ForeignKey("documents.id"))

    # Relationships
    person = relationship("Person", back_populates="events")

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type='{self.event_type}', person_id={self.person_id})>"


class Relationship(Base):
    """Relationship between two people."""

    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True)
    source_person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    target_person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    relationship_type = Column(String, nullable=False)  # parent, spouse, child, etc.
    confidence = Column(Float)
    notes = Column(Text)
    source_document_id = Column(Integer, ForeignKey("documents.id"))

    def __repr__(self) -> str:
        return (
            f"<Relationship(id={self.id}, "
            f"type='{self.relationship_type}', "
            f"source={self.source_person_id}, "
            f"target={self.target_person_id})>"
        )


class GenealogyDatabase:
    """Database manager for genealogical data."""

    def __init__(self, db_path: Path | None = None):
        """Initialize the database.

        Args:
            db_path: Path to SQLite database file (default: ./genealogy.db)
        """
        self.db_path = db_path or Path("./genealogy.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        """Get a new database session."""
        return self.Session()

    def get_document_by_source(self, source: str, page: int | None = None) -> Document | None:
        """Get a document by source path and optional page number.

        Args:
            source: Path to source document
            page: Optional page number

        Returns:
            Document object if found, None otherwise
        """
        session = self.get_session()
        try:
            query = session.query(Document).filter(Document.source == source)
            if page is not None:
                query = query.filter(Document.page == page)
            return query.first()
        finally:
            session.close()

    def add_document(
        self, source: str, page: int, ocr_text: str, skip_if_exists: bool = True
    ) -> Document | None:
        """Add a document record.

        Args:
            source: Path to source document
            page: Page number
            ocr_text: Extracted OCR text
            skip_if_exists: If True, skip adding if document already exists

        Returns:
            Created Document object, or existing document if skip_if_exists=True, or None if skipped
        """
        session = self.get_session()
        try:
            # Check if document already exists
            if skip_if_exists:
                existing = (
                    session.query(Document)
                    .filter(Document.source == source, Document.page == page)
                    .first()
                )
                if existing:
                    return existing

            doc = Document(source=source, page=page, ocr_text=ocr_text)
            session.add(doc)
            session.commit()
            session.refresh(doc)
            return doc
        finally:
            session.close()

    def add_person(
        self,
        primary_name: str,
        notes: str | None = None,
        confidence: float | None = None,
        source_document_id: int | None = None,
    ) -> Person:
        """Add a person record.

        Args:
            primary_name: Primary name for the person
            notes: Optional notes
            confidence: Confidence score (0-1)
            source_document_id: Source document ID for citation

        Returns:
            Created Person object
        """
        session = self.get_session()
        try:
            person = Person(
                primary_name=primary_name,
                notes=notes,
                confidence=confidence,
                source_document_id=source_document_id,
            )
            session.add(person)
            session.commit()
            session.refresh(person)
            return person
        finally:
            session.close()

    def add_name(
        self,
        person_id: int,
        name: str,
        name_type: str | None = None,
        confidence: float | None = None,
    ) -> Name:
        """Add an alternate name for a person.

        Args:
            person_id: Person ID
            name: The name
            name_type: Type of name (birth, married, etc.)
            confidence: Confidence score (0-1)

        Returns:
            Created Name object
        """
        session = self.get_session()
        try:
            name_obj = Name(
                person_id=person_id, name=name, name_type=name_type, confidence=confidence
            )
            session.add(name_obj)
            session.commit()
            session.refresh(name_obj)
            return name_obj
        finally:
            session.close()

    def add_event(
        self,
        person_id: int,
        event_type: str,
        date: str | None = None,
        place: str | None = None,
        description: str | None = None,
        confidence: float | None = None,
        source_document_id: int | None = None,
    ) -> Event:
        """Add a life event.

        Args:
            person_id: Person ID
            event_type: Type of event (birth, death, marriage, etc.)
            date: Date of event (flexible format)
            place: Location
            description: Event description
            confidence: Confidence score (0-1)
            source_document_id: Source document ID

        Returns:
            Created Event object
        """
        session = self.get_session()
        try:
            event = Event(
                person_id=person_id,
                event_type=event_type,
                date=date,
                place=place,
                description=description,
                confidence=confidence,
                source_document_id=source_document_id,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
        finally:
            session.close()

    def add_relationship(
        self,
        source_person_id: int,
        target_person_id: int,
        relationship_type: str,
        confidence: float | None = None,
        notes: str | None = None,
        source_document_id: int | None = None,
    ) -> Relationship:
        """Add a relationship between two people.

        Args:
            source_person_id: Source person ID
            target_person_id: Target person ID
            relationship_type: Type of relationship
            confidence: Confidence score (0-1)
            notes: Optional notes
            source_document_id: Source document ID for citation

        Returns:
            Created Relationship object
        """
        session = self.get_session()
        try:
            rel = Relationship(
                source_person_id=source_person_id,
                target_person_id=target_person_id,
                relationship_type=relationship_type,
                confidence=confidence,
                notes=notes,
                source_document_id=source_document_id,
            )
            session.add(rel)
            session.commit()
            session.refresh(rel)
            return rel
        finally:
            session.close()

    def get_person_by_name(self, name: str) -> list[Person]:
        """Search for people by name.

        Args:
            name: Name to search for

        Returns:
            List of matching Person objects
        """
        session = self.get_session()
        try:
            # Search both primary names and alternate names
            people = (
                session.query(Person)
                .filter(Person.primary_name.ilike(f"%{name}%"))
                .all()
            )

            # Also search alternate names
            name_matches = session.query(Name).filter(Name.name.ilike(f"%{name}%")).all()
            for name_obj in name_matches:
                if name_obj.person not in people:
                    people.append(name_obj.person)

            return people
        finally:
            session.close()

    def store_extraction(
        self, extraction_result: "ExtractionResult", document_id: int
    ) -> dict[str, int]:
        """Store extracted entities from a document.

        Args:
            extraction_result: ExtractionResult object with people, events, relationships
            document_id: ID of the source document

        Returns:
            Dictionary with counts of stored entities
        """
        from src.backend.genealogy_ai.schemas import ExtractionResult

        people_count = 0
        events_count = 0
        relationships_count = 0
        name_to_person_id: dict[str, int] = {}

        # First pass: Create people and store name mappings
        for person_data in extraction_result.people:
            # Check if person already exists
            existing = self.get_person_by_name(person_data.primary_name)
            if existing:
                # Person might already exist - for now, create anyway
                # (reconciliation will be Phase 2)
                pass

            # Create person
            person = self.add_person(
                primary_name=person_data.primary_name,
                confidence=person_data.confidence,
                notes=person_data.notes,
                source_document_id=document_id,
            )
            people_count += 1
            name_to_person_id[person_data.primary_name] = person.id

            # Add name variants
            for variant in person_data.name_variants:
                self.add_name(person.id, variant)

        # Second pass: Create events
        for event_data in extraction_result.events:
            # Find person by name
            person_id = name_to_person_id.get(event_data.person_name)
            if not person_id:
                # Try to find existing person
                existing = self.get_person_by_name(event_data.person_name)
                if existing:
                    person_id = existing[0].id
                else:
                    # Create person if not found
                    person = self.add_person(
                        primary_name=event_data.person_name,
                        confidence=0.7,
                        source_document_id=document_id,
                    )
                    person_id = person.id
                    name_to_person_id[event_data.person_name] = person_id

            # Create event
            self.add_event(
                person_id=person_id,
                event_type=event_data.event_type,
                date=event_data.date,
                place=event_data.place,
                confidence=event_data.confidence,
                description=event_data.notes,
                source_document_id=document_id,
            )
            events_count += 1

        # Third pass: Create relationships
        for rel_data in extraction_result.relationships:
            # Find both people
            person1_id = name_to_person_id.get(rel_data.person1)
            person2_id = name_to_person_id.get(rel_data.person2)

            if not person1_id:
                existing = self.get_person_by_name(rel_data.person1)
                if existing:
                    person1_id = existing[0].id
                else:
                    person = self.add_person(
                        primary_name=rel_data.person1,
                        confidence=0.7,
                        source_document_id=document_id,
                    )
                    person1_id = person.id

            if not person2_id:
                existing = self.get_person_by_name(rel_data.person2)
                if existing:
                    person2_id = existing[0].id
                else:
                    person = self.add_person(
                        primary_name=rel_data.person2,
                        confidence=0.7,
                        source_document_id=document_id,
                    )
                    person2_id = person.id

            # Create relationship
            self.add_relationship(
                source_person_id=person1_id,
                target_person_id=person2_id,
                relationship_type=rel_data.relationship_type,
                confidence=rel_data.confidence,
                notes=rel_data.notes,
                source_document_id=document_id,
            )
            relationships_count += 1

        return {
            "people": people_count,
            "events": events_count,
            "relationships": relationships_count,
        }

    def merge_people(self, keep_id: int, merge_id: int) -> None:
        """Merge two people records, keeping one and removing the other.

        Args:
            keep_id: ID of person to keep
            merge_id: ID of person to merge into keep_id (will be deleted)
        """
        session = self.get_session()
        try:
            # Get both people
            keep_person = session.query(Person).filter(Person.id == keep_id).first()
            merge_person = session.query(Person).filter(Person.id == merge_id).first()

            if not keep_person or not merge_person:
                raise ValueError("One or both people not found")

            # Merge alternate names
            for name in merge_person.names:
                # Only add if not already present
                existing_names = {n.name.lower() for n in keep_person.names}
                existing_names.add(keep_person.primary_name.lower())
                if name.name.lower() not in existing_names:
                    self.add_name(keep_id, name.name)

            # Update all events to point to kept person
            session.query(Event).filter(Event.person_id == merge_id).update(
                {"person_id": keep_id}
            )

            # Update all relationships
            session.query(Relationship).filter(
                Relationship.source_person_id == merge_id
            ).update({"source_person_id": keep_id})

            session.query(Relationship).filter(
                Relationship.target_person_id == merge_id
            ).update({"target_person_id": keep_id})

            # Delete the merged person's alternate names
            session.query(Name).filter(Name.person_id == merge_id).delete()

            # Delete the merged person
            session.delete(merge_person)

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with database stats
        """
        session = self.get_session()
        try:
            return {
                "total_documents": session.query(Document).count(),
                "total_people": session.query(Person).count(),
                "total_events": session.query(Event).count(),
                "total_relationships": session.query(Relationship).count(),
            }
        finally:
            session.close()
