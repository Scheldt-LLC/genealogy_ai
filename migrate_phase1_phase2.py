#!/usr/bin/env python3
"""
Migration script for Phase 1 & 2: Add family trees and document linking support

This script adds:
- documents.document_type column
- people.family_name and people.family_side columns
- person_documents junction table for document linking

Usage: python migrate_phase1_phase2.py
"""

import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path: Path):
    """Migrate the database schema to support family trees and document linking."""

    print(f"Migrating database: {db_path}")

    # Check if database exists
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # Create backup
    backup_path = db_path.parent / f"{db_path.name}.backup"
    print(f"Creating backup at: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if migrations already applied
        cursor.execute("PRAGMA table_info(documents)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'document_type' in columns:
            print("✓ Migration already applied - document_type column exists")
            return

        print("\nApplying migrations...")

        # 1. Add document_type to documents table
        print("  1. Adding document_type column to documents table...")
        cursor.execute("""
            ALTER TABLE documents ADD COLUMN document_type TEXT
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_documents_document_type ON documents(document_type)")
        print("     ✓ Added document_type column")

        # 2. Add family_name and family_side to people table
        print("  2. Adding family_name column to people table...")
        cursor.execute("""
            ALTER TABLE people ADD COLUMN family_name TEXT
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_people_family_name ON people(family_name)")
        print("     ✓ Added family_name column")

        print("  3. Adding family_side column to people table...")
        cursor.execute("""
            ALTER TABLE people ADD COLUMN family_side TEXT
        """)
        print("     ✓ Added family_side column")

        # 3. Create person_documents junction table
        print("  4. Creating person_documents table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                link_type TEXT NOT NULL,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_person_documents_person_id ON person_documents(person_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_person_documents_document_id ON person_documents(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_person_documents_link_type ON person_documents(link_type)")
        print("     ✓ Created person_documents table")

        # 4. Migrate existing source_document_id relationships to person_documents
        print("  5. Migrating existing document relationships...")
        cursor.execute("""
            INSERT INTO person_documents (person_id, document_id, link_type, created_at)
            SELECT id, source_document_id, 'extracted_from', datetime('now')
            FROM people
            WHERE source_document_id IS NOT NULL
        """)
        migrated_count = cursor.rowcount
        print(f"     ✓ Migrated {migrated_count} existing relationships")

        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print(f"\nBackup saved at: {backup_path}")
        print("You can delete the backup once you've verified everything works.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        print(f"Database has been rolled back. Backup is at: {backup_path}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = Path(__file__).parent / "data" / "genealogy.db"

    # Allow custom path as command line argument
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    print("=" * 60)
    print("Database Migration: Phase 1 & 2")
    print("Family Trees & Document Linking")
    print("=" * 60)
    print()

    migrate_database(db_path)
