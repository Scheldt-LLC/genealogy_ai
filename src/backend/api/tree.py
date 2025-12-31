"""Family tree API endpoints."""

from pathlib import Path

from quart import Blueprint, current_app, jsonify, request

from src.backend.genealogy_ai.storage.sqlite import Event, GenealogyDatabase, Person, Relationship

tree_bp = Blueprint("tree", __name__)


@tree_bp.route("/api/tree", methods=["GET"])
async def get_tree() -> tuple[dict, int]:
    """Get family tree data (all people and relationships).

    Query parameters:
        - person_id: Optional - focus on a specific person and their immediate family

    Returns:
        JSON with people and relationships
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        person_id = request.args.get("person_id", type=int)

        try:
            # Get all people or specific person's family
            if person_id:
                # Get specific person
                person = session.query(Person).filter(Person.id == person_id).first()
                if not person:
                    return jsonify({"error": "Person not found"}), 404

                # Get their immediate family (parents, children, spouses)
                person_ids = {person_id}

                # Get relationships for this person
                rels = session.query(Relationship).filter(
                    (Relationship.source_person_id == person_id)
                    | (Relationship.target_person_id == person_id)
                ).all()

                for rel in rels:
                    person_ids.add(rel.source_person_id)
                    person_ids.add(rel.target_person_id)

                people = session.query(Person).filter(Person.id.in_(person_ids)).all()
            else:
                # Get all people
                people = session.query(Person).all()

            # Build people data
            people_data = []
            for person in people:
                # Get events
                birth_event = session.query(Event).filter(
                    Event.person_id == person.id,
                    Event.event_type == "birth"
                ).first()

                death_event = session.query(Event).filter(
                    Event.person_id == person.id,
                    Event.event_type == "death"
                ).first()

                person_data = {
                    "id": person.id,
                    "name": person.primary_name,
                    "birth_date": birth_event.date if birth_event else None,
                    "birth_place": birth_event.place if birth_event else None,
                    "death_date": death_event.date if death_event else None,
                    "death_place": death_event.place if death_event else None,
                }

                people_data.append(person_data)

            # Get relationships
            if person_id:
                relationships = rels
            else:
                relationships = session.query(Relationship).all()

            relationships_data = []
            for rel in relationships:
                relationships_data.append({
                    "id": rel.id,
                    "source_id": rel.source_person_id,
                    "target_id": rel.target_person_id,
                    "type": rel.relationship_type,
                })

            return jsonify({
                "success": True,
                "people": people_data,
                "relationships": relationships_data,
            }), 200

        finally:
            session.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get tree data: {e!s}"}), 500


@tree_bp.route("/api/tree/people", methods=["GET"])
async def list_people() -> tuple[dict, int]:
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
                birth_event = session.query(Event).filter(
                    Event.person_id == person.id,
                    Event.event_type == "birth"
                ).first()

                birth_year = None
                if birth_event and birth_event.date:
                    # Try to extract year from date string
                    try:
                        # Handle various date formats (YYYY, YYYY-MM-DD, etc.)
                        birth_year = birth_event.date.split('-')[0]
                        if birth_year.isdigit():
                            birth_year = int(birth_year)
                        else:
                            birth_year = None
                    except:
                        birth_year = None

                people_list.append({
                    "id": person.id,
                    "name": person.primary_name,
                    "birth_year": birth_year,
                })

            # Sort by birth year (oldest first), then by name
            people_list.sort(key=lambda x: (x["birth_year"] or 9999, x["name"]))

            return jsonify({
                "success": True,
                "people": people_list,
            }), 200

        finally:
            session.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to list people: {e!s}"}), 500
