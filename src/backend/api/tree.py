"""Family tree API endpoints."""

from pathlib import Path
from typing import cast

from quart import Blueprint, Response, current_app, jsonify, request

from src.backend.genealogy_ai.storage.sqlite import Event, GenealogyDatabase, Person, Relationship

tree_bp = Blueprint("tree", __name__)


@tree_bp.route("/api/tree", methods=["GET"])
async def get_tree() -> Response | tuple[Response, int]:
    """Get family tree data (all people and relationships).

    Query parameters:
        - person_id: Optional - focus on a specific person and their immediate family
        - family_name: Optional - filter by family name (e.g., "scheldt", "byrnes")
        - family_side: Optional - filter by family side ("maternal" or "paternal")

    Returns:
        JSON with people and relationships
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        person_id = request.args.get("person_id", type=int)
        family_name = request.args.get("family_name", type=str)
        family_side = request.args.get("family_side", type=str)

        try:
            # Build base query with optional family filters
            query = session.query(Person)

            if family_name:
                query = query.filter(Person.family_name == family_name)

            if family_side:
                query = query.filter(Person.family_side == family_side)

            # Get all people or specific person's family
            if person_id:
                # Get specific person
                person = session.query(Person).filter(Person.id == person_id).first()
                if not person:
                    return jsonify({"error": "Person not found"}), 404

                # Get their immediate family (parents, children, spouses)
                person_ids = {person_id}

                # Get relationships for this person
                rels = (
                    session.query(Relationship)
                    .filter(
                        (Relationship.source_person_id == person_id)
                        | (Relationship.target_person_id == person_id)
                    )
                    .all()
                )

                for rel in rels:
                    person_ids.add(cast(int, rel.source_person_id))
                    person_ids.add(cast(int, rel.target_person_id))

                people = query.filter(Person.id.in_(person_ids)).all()
            else:
                # Get all people (with optional family filter)
                people = query.all()

            # Build people data
            people_data = []
            for person in people:
                # Get events
                birth_event = (
                    session.query(Event)
                    .filter(Event.person_id == person.id, Event.event_type == "birth")
                    .first()
                )

                death_event = (
                    session.query(Event)
                    .filter(Event.person_id == person.id, Event.event_type == "death")
                    .first()
                )

                person_data = {
                    "id": person.id,
                    "name": person.primary_name,
                    "birth_date": birth_event.date if birth_event else None,
                    "birth_place": birth_event.place if birth_event else None,
                    "death_date": death_event.date if death_event else None,
                    "death_place": death_event.place if death_event else None,
                    "family_name": person.family_name,
                    "family_side": person.family_side,
                }

                people_data.append(person_data)

            # Get relationships
            relationships = rels if person_id else session.query(Relationship).all()

            relationships_data = []
            for rel in relationships:
                relationships_data.append(
                    {
                        "id": rel.id,
                        "source_id": rel.source_person_id,
                        "target_id": rel.target_person_id,
                        "type": rel.relationship_type,
                    }
                )

            return jsonify(
                {
                    "success": True,
                    "people": people_data,
                    "relationships": relationships_data,
                }
            ), 200

        finally:
            session.close()

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to get tree data: {e!s}"}), 500


@tree_bp.route("/api/tree/people", methods=["GET"])
async def list_people() -> Response | tuple[Response, int]:
    """Get a simple list of all people (for selection/search).

    Returns:
        JSON with list of people (id, name, birth year)
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        try:
            people = session.query(Person).all()

            people_list = []
            for person in people:
                # Get birth year for sorting
                birth_event = (
                    session.query(Event)
                    .filter(Event.person_id == person.id, Event.event_type == "birth")
                    .first()
                )

                birth_year = None
                date_str = cast(str | None, birth_event.date) if birth_event else None
                if birth_event and date_str:
                    # Try to extract year from date string
                    try:
                        # Handle various date formats (YYYY, YYYY-MM-DD, etc.)
                        year_part = date_str.split("-")[0]
                        birth_year = int(year_part) if year_part.isdigit() else None
                    except Exception:
                        birth_year = None

                people_list.append(
                    {
                        "id": person.id,
                        "name": person.primary_name,
                        "birth_year": birth_year,
                    }
                )

            # Sort by birth year (oldest first), then by name
            people_list.sort(key=lambda x: (x["birth_year"] or 9999, x["name"]))

            return jsonify(
                {
                    "success": True,
                    "people": people_list,
                }
            ), 200

        finally:
            session.close()

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to list people: {e!s}"}), 500


@tree_bp.route("/api/families", methods=["GET"])
async def get_families() -> Response | tuple[Response, int]:
    """Get list of all unique family names with person counts.

    Returns:
        JSON with list of families and statistics
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        families = db.get_family_list()

        return jsonify(
            {
                "success": True,
                "families": families,
                "count": len(families),
            }
        ), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to list families: {e!s}"}), 500


@tree_bp.route("/api/people/<int:person_id>/family", methods=["POST"])
async def assign_person_family(person_id: int) -> Response | tuple[Response, int]:
    """Assign a person to a family.

    Args:
        person_id: ID of the person to update

    Body:
        - family_name: Family name to assign (required)
        - family_side: Optional family side ("maternal" or "paternal")

    Returns:
        JSON with success status
    """
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        family_name = data.get("family_name")
        if not family_name:
            return jsonify({"error": "family_name is required"}), 400

        family_side = data.get("family_side")

        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        db.update_person_family(
            person_id=person_id,
            family_name=family_name,
            family_side=family_side,
        )

        return jsonify(
            {
                "success": True,
                "message": f"Person {person_id} assigned to family '{family_name}'",
            }
        ), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to assign family: {e!s}"}), 500


@tree_bp.route("/api/people/<int:person_id>/documents", methods=["GET"])
async def get_person_documents(person_id: int) -> Response | tuple[Response, int]:
    """Get all documents linked to a person.

    Args:
        person_id: ID of the person

    Query parameters:
        - link_type: Optional filter by link type (e.g., "extracted_from", "portrait_of")

    Returns:
        JSON with list of linked documents
    """
    try:
        link_type = request.args.get("link_type", type=str)

        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        documents = db.get_person_documents(person_id=person_id, link_type=link_type)

        documents_data = [
            {
                "document_id": doc["document_id"],
                "link_type": doc["link_type"],
                "notes": doc["notes"],
                "source": doc["source"],
                "page": doc["page"],
                "document_type": doc["document_type"],
                "created_at": doc["created_at"],
            }
            for doc in documents
        ]

        return jsonify(
            {
                "success": True,
                "person_id": person_id,
                "documents": documents_data,
                "count": len(documents_data),
            }
        ), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to get person documents: {e!s}"}), 500


@tree_bp.route("/api/people/<int:person_id>/documents", methods=["POST"])
async def link_document_to_person(person_id: int) -> Response | tuple[Response, int]:
    """Manually link a document to a person.

    Args:
        person_id: ID of the person

    Body:
        - document_id: Document ID to link (required)
        - link_type: Type of link (required, e.g., "portrait_of", "mentioned_in")
        - notes: Optional notes about the link

    Returns:
        JSON with success status
    """
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        document_id = data.get("document_id")
        link_type = data.get("link_type")
        notes = data.get("notes")

        if not document_id:
            return jsonify({"error": "document_id is required"}), 400
        if not link_type:
            return jsonify({"error": "link_type is required"}), 400

        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        db.add_person_document_link(
            person_id=person_id,
            document_id=document_id,
            link_type=link_type,
            notes=notes,
        )

        return jsonify(
            {
                "success": True,
                "message": f"Document {document_id} linked to person {person_id}",
            }
        ), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to link document: {e!s}"}), 500


@tree_bp.route("/api/people/<int:person_id>/documents/<int:document_id>", methods=["DELETE"])
async def unlink_document_from_person(
    person_id: int, document_id: int
) -> Response | tuple[Response, int]:
    """Remove a document link from a person.

    Args:
        person_id: ID of the person
        document_id: ID of the document

    Returns:
        JSON with success status
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        db.remove_person_document_link(person_id=person_id, document_id=document_id)

        return jsonify(
            {
                "success": True,
                "message": f"Document {document_id} unlinked from person {person_id}",
            }
        ), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to unlink document: {e!s}"}), 500
