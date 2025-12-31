"""Pydantic schemas for genealogical entities.

These schemas define the structure for extracted genealogical information
and are used for validation and serialization.
"""

from pydantic import BaseModel, Field


class PersonExtraction(BaseModel):
    """A person extracted from a document."""

    primary_name: str = Field(description="Primary name as written in the document")
    name_variants: list[str] = Field(
        default_factory=list, description="Alternative spellings, nicknames, maiden names"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score for this person (0.0-1.0)"
    )
    notes: str | None = Field(
        default=None, description="Additional context about this person"
    )


class EventExtraction(BaseModel):
    """A genealogical event (birth, death, marriage, etc.)."""

    person_name: str = Field(description="Name of the person this event relates to")
    event_type: str = Field(
        description="Type of event: birth, death, marriage, immigration, etc."
    )
    date: str | None = Field(
        default=None, description="Date as written in the document (not normalized)"
    )
    place: str | None = Field(
        default=None, description="Place as written in the document"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score for this event (0.0-1.0)"
    )
    notes: str | None = Field(
        default=None, description="Additional context about this event"
    )


class RelationshipExtraction(BaseModel):
    """A relationship between two people."""

    person1: str = Field(description="First person's name")
    person2: str = Field(description="Second person's name")
    relationship_type: str = Field(
        description="Type of relationship: parent, child, spouse, sibling, etc."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score for this relationship (0.0-1.0)"
    )
    notes: str | None = Field(
        default=None, description="Additional context about this relationship"
    )


class ExtractionResult(BaseModel):
    """Complete extraction result from a document."""

    people: list[PersonExtraction] = Field(
        default_factory=list, description="People mentioned in the document"
    )
    events: list[EventExtraction] = Field(
        default_factory=list, description="Events mentioned in the document"
    )
    relationships: list[RelationshipExtraction] = Field(
        default_factory=list, description="Relationships mentioned in the document"
    )

    def is_empty(self) -> bool:
        """Check if the extraction result is empty."""
        return not (self.people or self.events or self.relationships)
