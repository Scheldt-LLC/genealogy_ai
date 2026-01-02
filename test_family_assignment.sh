#!/bin/bash
# Test if family assignments are being saved

echo "=== Checking family assignments ==="
echo ""
echo "People with family names:"
sqlite3 genealogy.db "SELECT id, primary_name, family_name, family_side FROM people WHERE family_name IS NOT NULL;"
echo ""
echo "All families in database:"
sqlite3 genealogy.db "SELECT DISTINCT family_name, COUNT(*) as count FROM people WHERE family_name IS NOT NULL GROUP BY family_name;"
echo ""
echo "Recent people (last 5):"
sqlite3 genealogy.db "SELECT id, primary_name, family_name, family_side, created_at FROM people ORDER BY created_at DESC LIMIT 5;"
