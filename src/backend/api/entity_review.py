"""Entity review API endpoints for human-in-the-loop entity matching."""

import json
from pathlib import Path
from typing import cast

from quart import Blueprint, Response, current_app, jsonify, request

from src.backend.genealogy_ai.storage.sqlite import (
    EntityMatch,
    GenealogyDatabase,
    PendingEvent,
    PendingPerson,
    Person,
)

entity_review_bp = Blueprint("entity_review", __name__)


@entity_review_bp.route("/api/entities/pending", methods=["GET"])
async def get_pending_entities() -> Response | tuple[Response, int]:
    """Get all pending entities that need review.

    Returns:
        JSON with list of pending entities and their proposed matches
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        try:
            # Get all pending matches
            pending_matches = (
                session.query(EntityMatch).filter(EntityMatch.status == "pending").all()
            )

            matches_data = []
            for match in pending_matches:
                # Get pending person details
                pending_person = (
                    session.query(PendingPerson)
                    .filter_by(id=match.pending_person_id)
                    .first()
                )

                if not pending_person:
                    continue

                # Get pending events
                pending_events = (
                    session.query(PendingEvent)
                    .filter_by(pending_person_id=pending_person.id)
                    .all()
                )

                events_data = [
                    {
                        "event_type": event.event_type,
                        "date": event.date,
                        "place": event.place,
                        "description": event.description,
                    }
                    for event in pending_events
                ]

                # Get existing person details if this is a pending_to_existing match
                existing_person_data = None
                if match.match_type == "pending_to_existing" and match.existing_person_id:
                    existing_person = (
                        session.query(Person).filter_by(id=match.existing_person_id).first()
                    )

                    if existing_person:
                        # Get existing events
                        from src.backend.genealogy_ai.storage.sqlite import Event

                        existing_events = (
                            session.query(Event)
                            .filter_by(person_id=existing_person.id)
                            .all()
                        )

                        existing_person_data = {
                            "id": existing_person.id,
                            "primary_name": existing_person.primary_name,
                            "family_name": existing_person.family_name,
                            "family_side": existing_person.family_side,
                            "events": [
                                {
                                    "event_type": event.event_type,
                                    "date": event.date,
                                    "place": event.place,
                                    "description": event.description,
                                }
                                for event in existing_events
                            ],
                        }

                # Parse reasons from JSON
                reasons = []
                if match.reasons:
                    try:
                        reasons = json.loads(cast(str, match.reasons))
                    except json.JSONDecodeError:
                        reasons = [cast(str, match.reasons)]

                # Parse name variants
                name_variants = []
                if pending_person.name_variants:
                    try:
                        name_variants = json.loads(cast(str, pending_person.name_variants))
                    except json.JSONDecodeError:
                        pass

                matches_data.append(
                    {
                        "match_id": match.id,
                        "batch_id": match.extraction_batch_id,
                        "match_type": match.match_type,
                        "confidence": match.confidence,
                        "reasons": reasons,
                        "pending_entity": {
                            "id": pending_person.id,
                            "primary_name": pending_person.primary_name,
                            "name_variants": name_variants,
                            "family_name": pending_person.family_name,
                            "family_side": pending_person.family_side,
                            "notes": pending_person.notes,
                            "events": events_data,
                        },
                        "existing_entity": existing_person_data,
                    }
                )

            return jsonify(
                {"success": True, "pending_count": len(matches_data), "matches": matches_data}
            ), 200

        finally:
            session.close()

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to get pending entities: {e!s}"}), 500


@entity_review_bp.route("/api/entities/approve/<int:match_id>", methods=["POST"])
async def approve_match(match_id: int) -> Response | tuple[Response, int]:
    """Approve a pending entity match and merge the entities.

    Args:
        match_id: ID of the EntityMatch to approve

    Returns:
        JSON with success status
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        try:
            # Get the match
            match = session.query(EntityMatch).filter_by(id=match_id).first()

            if not match:
                return jsonify({"error": "Match not found"}), 404

            if match.status != "pending":
                return jsonify({"error": f"Match already {match.status}"}), 400

            # Get pending person
            pending_person = (
                session.query(PendingPerson).filter_by(id=match.pending_person_id).first()
            )

            if not pending_person:
                return jsonify({"error": "Pending person not found"}), 404

            if match.match_type == "pending_to_existing":
                # Merge into existing person
                existing_person_id = cast(int, match.existing_person_id)

                # Add name variants
                if pending_person.name_variants:
                    try:
                        variants = json.loads(cast(str, pending_person.name_variants))
                        for variant in variants:
                            db.add_name(existing_person_id, variant)
                    except json.JSONDecodeError:
                        pass

                # Also add the primary name as a variant if different
                existing_person = session.query(Person).filter_by(id=existing_person_id).first()
                if existing_person and pending_person.primary_name != existing_person.primary_name:
                    db.add_name(existing_person_id, cast(str, pending_person.primary_name))

                # Transfer events
                pending_events = (
                    session.query(PendingEvent)
                    .filter_by(pending_person_id=pending_person.id)
                    .all()
                )

                for event in pending_events:
                    db.add_event(
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

                # Create PersonDocument link
                if pending_person.source_document_id:
                    db.add_person_document_link(
                        person_id=existing_person_id,
                        document_id=cast(int, pending_person.source_document_id),
                        link_type="extracted_from",
                    )

                # Mark as approved
                pending_person.status = "approved"
                match.status = "approved"
                match.reviewed_at = __import__("datetime").datetime.utcnow().isoformat()

                session.commit()

                return jsonify(
                    {
                        "success": True,
                        "message": f"Merged pending entity into existing person {existing_person_id}",
                        "person_id": existing_person_id,
                    }
                ), 200

            else:
                return jsonify({"error": f"Unsupported match type: {match.match_type}"}), 400

        finally:
            session.close()

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to approve match: {e!s}"}), 500


@entity_review_bp.route("/api/entities/reject/<int:match_id>", methods=["POST"])
async def reject_match(match_id: int) -> Response | tuple[Response, int]:
    """Reject a pending entity match and create a new person instead.

    Args:
        match_id: ID of the EntityMatch to reject

    Returns:
        JSON with success status
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        try:
            # Get the match
            match = session.query(EntityMatch).filter_by(id=match_id).first()

            if not match:
                return jsonify({"error": "Match not found"}), 404

            if match.status != "pending":
                return jsonify({"error": f"Match already {match.status}"}), 400

            # Get pending person
            pending_person = (
                session.query(PendingPerson).filter_by(id=match.pending_person_id).first()
            )

            if not pending_person:
                return jsonify({"error": "Pending person not found"}), 404

            # Create new person from pending data
            new_person = db.add_person(
                primary_name=cast(str, pending_person.primary_name),
                confidence=pending_person.confidence,
                notes=pending_person.notes,
                source_document_id=cast(int, pending_person.source_document_id)
                if pending_person.source_document_id
                else None,
                family_name=pending_person.family_name,
                family_side=pending_person.family_side,
            )

            new_person_id = cast(int, new_person.id)

            # Add name variants
            if pending_person.name_variants:
                try:
                    variants = json.loads(cast(str, pending_person.name_variants))
                    for variant in variants:
                        db.add_name(new_person_id, variant)
                except json.JSONDecodeError:
                    pass

            # Transfer events
            pending_events = (
                session.query(PendingEvent)
                .filter_by(pending_person_id=pending_person.id)
                .all()
            )

            for event in pending_events:
                db.add_event(
                    person_id=new_person_id,
                    event_type=cast(str, event.event_type),
                    date=event.date,
                    place=event.place,
                    confidence=event.confidence,
                    description=event.description,
                    source_document_id=cast(int, event.source_document_id)
                    if event.source_document_id
                    else None,
                )
                event.status = "rejected"

            # Create PersonDocument link
            if pending_person.source_document_id:
                db.add_person_document_link(
                    person_id=new_person_id,
                    document_id=cast(int, pending_person.source_document_id),
                    link_type="extracted_from",
                )

            # Mark as rejected
            pending_person.status = "rejected"
            match.status = "rejected"
            match.reviewed_at = __import__("datetime").datetime.utcnow().isoformat()

            session.commit()

            return jsonify(
                {
                    "success": True,
                    "message": f"Created new person {new_person_id} from pending entity",
                    "person_id": new_person_id,
                }
            ), 200

        finally:
            session.close()

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to reject match: {e!s}"}), 500


@entity_review_bp.route("/api/entities/batches", methods=["GET"])
async def get_extraction_batches() -> Response | tuple[Response, int]:
    """Get summary of all extraction batches.

    Returns:
        JSON with list of batches and their status
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        try:
            # Get all batches from pending people
            from sqlalchemy import distinct, func

            batch_ids = (
                session.query(distinct(PendingPerson.extraction_batch_id)).all()
            )

            batches_data = []
            for (batch_id,) in batch_ids:
                # Count pending entities in this batch
                pending_count = (
                    session.query(PendingPerson)
                    .filter_by(extraction_batch_id=batch_id, status="pending")
                    .count()
                )

                approved_count = (
                    session.query(PendingPerson)
                    .filter_by(extraction_batch_id=batch_id, status="approved")
                    .count()
                )

                rejected_count = (
                    session.query(PendingPerson)
                    .filter_by(extraction_batch_id=batch_id, status="rejected")
                    .count()
                )

                # Count pending matches
                pending_matches = (
                    session.query(EntityMatch)
                    .filter_by(extraction_batch_id=batch_id, status="pending")
                    .count()
                )

                batches_data.append(
                    {
                        "batch_id": batch_id,
                        "pending_entities": pending_count,
                        "approved_entities": approved_count,
                        "rejected_entities": rejected_count,
                        "pending_matches": pending_matches,
                        "total": pending_count + approved_count + rejected_count,
                    }
                )

            return jsonify({"success": True, "batches": batches_data}), 200

        finally:
            session.close()

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to get batches: {e!s}"}), 500
