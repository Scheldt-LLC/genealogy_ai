"""Genealogy AI CLI - Main entry point.

This module provides the command-line interface for the Genealogy AI project.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.backend.genealogy_ai.ingestion.chunking import DocumentChunker
from src.backend.genealogy_ai.ingestion.ocr import OCRProcessor
from src.backend.genealogy_ai.storage.chroma import ChromaStore
from src.backend.genealogy_ai.storage.sqlite import GenealogyDatabase

app = typer.Typer(
    name="geneai",
    help="Genealogy AI - Extract genealogical information from historical documents",
    add_completion=False,
)
console = Console()


@app.command()
def ingest(
    paths: list[Path] = typer.Argument(
        ..., help="Paths to PDF, image, or text files to ingest (or directories with --recursive)", exists=True
    ),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="Recursively search directories for supported files"
    ),
    output_dir: Path = typer.Option(
        Path("./ocr_output"), "--output-dir", "-o", help="Directory for OCR output"
    ),
    db_path: Path = typer.Option(Path("./genealogy.db"), "--db", help="Path to SQLite database"),
    chroma_dir: Path = typer.Option(
        Path("./chroma_db"), "--chroma-dir", help="Directory for Chroma vector database"
    ),
    chunk_size: int = typer.Option(1000, "--chunk-size", help="Maximum characters per chunk"),
    chunk_overlap: int = typer.Option(
        200, "--chunk-overlap", help="Character overlap between chunks"
    ),
    save_images: bool = typer.Option(False, "--save-images", help="Save extracted page images"),
    dpi: int = typer.Option(300, "--dpi", help="DPI for PDF to image conversion"),
) -> None:
    """Ingest documents using OCR and store in vector database.

    This command processes PDF, image, or text files, extracts text (using OCR for
    images and PDFs), chunks the text, and stores it in both SQLite and Chroma
    vector databases.

    Supported file types: .pdf, .png, .jpg, .jpeg, .tiff, .tif, .bmp, .txt
    """
    console.print("\n[bold cyan]Genealogy AI - Document Ingestion[/bold cyan]\n")

    # Collect all files to process
    files_to_process: list[Path] = []
    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".txt"}

    for path in paths:
        if path.is_file():
            files_to_process.append(path)
        elif path.is_dir() and recursive:
            # Recursively find all supported files
            for ext in supported_extensions:
                files_to_process.extend(path.rglob(f"*{ext}"))
        elif path.is_dir():
            console.print(
                f"[yellow]Skipping directory {path} (use --recursive to process directories)[/yellow]"
            )

    if not files_to_process:
        console.print("[red]No files found to process.[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Found {len(files_to_process)} file(s) to process[/dim]\n")

    # Initialize components
    ocr_processor = OCRProcessor(output_dir=output_dir, save_images=save_images)
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chroma_store = ChromaStore(persist_directory=chroma_dir)
    db = GenealogyDatabase(db_path=db_path)

    total_chunks = 0
    total_pages = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for doc_path in files_to_process:
            task = progress.add_task(f"Processing {doc_path.name}...", total=None)

            try:
                # OCR processing
                progress.update(task, description="[yellow]OCR: {doc_path.name}")
                ocr_results = ocr_processor.process_document(doc_path)
                total_pages += len(ocr_results)

                # Store documents in SQLite
                progress.update(task, description="[blue]Storing in database...")
                for ocr_result in ocr_results:
                    db.add_document(
                        source=str(ocr_result.source_path),
                        page=ocr_result.page_number,
                        ocr_text=ocr_result.text,
                    )

                # Chunk text
                progress.update(task, description="[magenta]Chunking text...")
                chunks = chunker.chunk_ocr_results(ocr_results)
                total_chunks += len(chunks)

                # Store in Chroma
                progress.update(task, description="[green]Storing in vector DB...")
                chroma_store.add_chunks(chunks)

                progress.update(
                    task,
                    description=f"[bold green]✓ {doc_path.name} "
                    f"({len(ocr_results)} pages, {len(chunks)} chunks)",
                )

            except Exception as e:
                progress.update(task, description=f"[bold red]✗ {doc_path.name}: {e!s}")
                console.print(f"[red]Error processing {doc_path}: {e!s}[/red]")
                continue

    # Display summary
    console.print("\n[bold green]Ingestion Complete![/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Documents Processed", str(len(files_to_process)))
    table.add_row("Total Pages", str(total_pages))
    table.add_row("Total Chunks", str(total_chunks))
    table.add_row("OCR Output Directory", str(output_dir.absolute()))
    table.add_row("Database Path", str(db_path.absolute()))
    table.add_row("Vector DB Path", str(chroma_dir.absolute()))

    console.print(table)
    console.print()


@app.command()
def stats(
    db_path: Path = typer.Option(Path("./genealogy.db"), "--db", help="Path to SQLite database"),
    chroma_dir: Path = typer.Option(
        Path("./chroma_db"), "--chroma-dir", help="Directory for Chroma vector database"
    ),
) -> None:
    """Display statistics about the genealogy database."""
    console.print("\n[bold cyan]Genealogy AI - Database Statistics[/bold cyan]\n")

    # SQLite stats
    db = GenealogyDatabase(db_path=db_path)
    db_stats = db.get_stats()

    table = Table(show_header=True, header_style="bold cyan", title="SQLite Database")
    table.add_column("Metric", style="dim")
    table.add_column("Count", justify="right")

    for key, value in db_stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)
    console.print()

    # Chroma stats
    try:
        chroma_store = ChromaStore(persist_directory=chroma_dir)
        chroma_stats = chroma_store.get_stats()

        table = Table(show_header=True, header_style="bold cyan", title="Vector Database (Chroma)")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        for key, value in chroma_stats.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[yellow]Warning: Could not load Chroma stats: {e!s}[/yellow]\n")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    k: int = typer.Option(5, "--limit", "-k", help="Number of results to return"),
    chroma_dir: Path = typer.Option(
        Path("./chroma_db"), "--chroma-dir", help="Directory for Chroma vector database"
    ),
) -> None:
    """Search the vector database for similar text chunks."""
    console.print(f"\n[bold cyan]Searching for:[/bold cyan] {query}\n")

    chroma_store = ChromaStore(persist_directory=chroma_dir)
    results = chroma_store.search(query, k=k)

    if not results:
        console.print("[yellow]No results found.[/yellow]\n")
        return

    for i, (text, metadata, score) in enumerate(results, 1):
        console.print(f"[bold cyan]Result {i}[/bold cyan] (score: {score:.4f})")
        console.print(f"[dim]Source:[/dim] {metadata.get('source', 'Unknown')}")
        console.print(f"[dim]Page:[/dim] {metadata.get('page', 'Unknown')}")
        console.print(f"\n{text}\n")
        console.print("-" * 80 + "\n")


@app.command()
def extract(
    db_path: Path = typer.Option(Path("./genealogy.db"), "--db", help="Path to SQLite database"),
    model: str = typer.Option(None, "--model", help="LLM model to use (overrides config)"),
    limit: int = typer.Option(
        None, "--limit", help="Limit number of documents to process (for testing)"
    ),
) -> None:
    """Extract genealogical entities from ingested documents using AI.

    This command processes OCR'd documents and extracts structured information:
    - People (with name variants)
    - Events (births, deaths, marriages, etc.)
    - Relationships (parent, child, spouse, etc.)

    Requires: OPENAI_API_KEY in .env file
    """
    from src.backend.genealogy_ai.agents.extract_entities import EntityExtractor

    console.print("\n[bold cyan]Genealogy AI - Entity Extraction[/bold cyan]\n")

    # Check for API key
    try:
        from src.backend.genealogy_ai.config import settings

        settings.get_api_key()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(
            "\n[yellow]Please create a .env file with your OPENAI_API_KEY.[/yellow]"
        )
        console.print("[dim]Copy .env.example to .env and add your API key.[/dim]\n")
        raise typer.Exit(1) from e

    # Initialize components
    db = GenealogyDatabase(db_path=db_path)
    extractor = EntityExtractor(model_name=model)

    # Get all documents from database
    session = db.get_session()
    try:
        from src.backend.genealogy_ai.storage.sqlite import Document

        query = session.query(Document)
        if limit:
            query = query.limit(limit)
        documents = query.all()

        if not documents:
            console.print("[yellow]No documents found. Run 'geneai ingest' first.[/yellow]\n")
            raise typer.Exit(1)

        console.print(f"[dim]Processing {len(documents)} document(s)...[/dim]\n")
    finally:
        session.close()

    # Process each document
    total_people = 0
    total_events = 0
    total_relationships = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for doc in documents:
            task = progress.add_task(f"Extracting from {Path(doc.source).name}...", total=None)

            try:
                # Extract entities
                progress.update(task, description=f"[yellow]Analyzing {Path(doc.source).name}...")
                result = extractor.extract(doc.ocr_text, doc.source, doc.page)

                if result.is_empty():
                    progress.update(
                        task, description=f"[dim]✓ {Path(doc.source).name} (no entities found)"
                    )
                    continue

                # Store in database
                progress.update(task, description=f"[blue]Storing entities...")
                counts = db.store_extraction(result, doc.id)

                total_people += counts["people"]
                total_events += counts["events"]
                total_relationships += counts["relationships"]

                progress.update(
                    task,
                    description=f"[bold green]✓ {Path(doc.source).name} "
                    f"({counts['people']} people, {counts['events']} events, "
                    f"{counts['relationships']} relationships)",
                )

            except Exception as e:
                progress.update(
                    task, description=f"[bold red]✗ {Path(doc.source).name}: {e!s}"
                )
                console.print(f"[red]Error processing {doc.source}: {e!s}[/red]")
                continue

    # Display summary
    console.print("\n[bold green]Extraction Complete![/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Documents Processed", str(len(documents)))
    table.add_row("People Extracted", str(total_people))
    table.add_row("Events Extracted", str(total_events))
    table.add_row("Relationships Extracted", str(total_relationships))
    table.add_row("Database Path", str(db_path.absolute()))

    console.print(table)
    console.print()


@app.command()
def reconcile(
    db_path: Path = typer.Option(Path("./genealogy.db"), "--db", help="Path to SQLite database"),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", help="Automatically approve matches above threshold"
    ),
    auto_threshold: float = typer.Option(
        1.0, "--auto-threshold", help="Confidence threshold for auto-approval (0.0-1.0, default: 1.0)"
    ),
    min_confidence: float = typer.Option(
        0.6, "--min-confidence", help="Minimum confidence score to show (0.0-1.0)"
    ),
) -> None:
    """Find and merge duplicate people in the database.

    This command identifies potential duplicate people using:
    - Fuzzy name matching
    - Birth/death date comparison
    - Birth/death place comparison

    By default, you'll be prompted to approve each merge. Use --auto-approve to
    automatically merge matches at or above the threshold (default: 1.0 = 100% match only).
    """
    from src.backend.genealogy_ai.agents.reconcile_people import ReconciliationAgent

    console.print("\n[bold cyan]Genealogy AI - Duplicate Reconciliation[/bold cyan]\n")

    db = GenealogyDatabase(db_path=db_path)
    agent = ReconciliationAgent(db=db, min_confidence=min_confidence)

    # Find duplicates
    console.print("[dim]Searching for duplicate people...[/dim]\n")
    candidates = agent.find_duplicates()

    if not candidates:
        console.print("[green]No duplicates found! Your database is clean.[/green]\n")
        return

    console.print(f"[yellow]Found {len(candidates)} potential duplicate(s):[/yellow]\n")

    # Display and process each candidate
    merged_count = 0
    auto_merged_count = 0
    skipped_count = 0

    for i, candidate in enumerate(candidates, 1):
        console.print(f"\n[bold cyan]Duplicate {i}/{len(candidates)}:[/bold cyan]")
        console.print(f"  Person 1: [blue]{candidate.person1_name}[/blue] (ID: {candidate.person1_id})")
        console.print(f"  Person 2: [blue]{candidate.person2_name}[/blue] (ID: {candidate.person2_id})")
        console.print(f"  Confidence: [yellow]{candidate.confidence:.2%}[/yellow]")
        console.print(f"  Reasons: {', '.join(candidate.reasons)}")

        # Auto-approve matches at or above threshold if enabled
        is_auto_approved = auto_approve and candidate.confidence >= auto_threshold
        if is_auto_approved:
            console.print(f"  [green]Auto-approving (confidence {candidate.confidence:.2%} >= {auto_threshold:.2%})...[/green]")
            approve = True
        else:
            # Ask user
            approve = typer.confirm(f"\n  Merge these people? (keep {candidate.person1_name})")

        if approve:
            try:
                db.merge_people(
                    keep_id=candidate.person1_id, merge_id=candidate.person2_id
                )
                console.print(f"  [bold green]✓ Merged into {candidate.person1_name}[/bold green]")
                merged_count += 1
                if is_auto_approved:
                    auto_merged_count += 1
            except Exception as e:
                console.print(f"  [bold red]✗ Error: {e!s}[/bold red]")
        else:
            console.print("  [dim]Skipped[/dim]")
            skipped_count += 1

    # Summary
    console.print("\n[bold green]Reconciliation Complete![/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Duplicates Found", str(len(candidates)))
    table.add_row("Merged", str(merged_count))
    if auto_approve:
        table.add_row("  └─ Auto-merged", str(auto_merged_count))
        table.add_row("  └─ Manually merged", str(merged_count - auto_merged_count))
    table.add_row("Skipped", str(skipped_count))
    table.add_row("Database Path", str(db_path.absolute()))

    console.print(table)
    console.print()


@app.command()
def tree(
    person: str = typer.Option(..., "--person", "-p", help="Name of person to show family tree for"),
    db_path: Path = typer.Option(Path("./genealogy.db"), "--db", help="Path to SQLite database"),
) -> None:
    """Display family tree for a specific person.

    Shows parents, spouse(s), children, and key life events.
    """
    from rich.tree import Tree

    from src.backend.genealogy_ai.storage.sqlite import Document, Event, Person, Relationship

    console.print(f"\n[bold cyan]Family Tree for:[/bold cyan] {person}\n")

    db = GenealogyDatabase(db_path=db_path)
    session = db.get_session()

    try:
        # Find the person
        people = db.get_person_by_name(person)

        if not people:
            console.print(f"[red]No person found matching '{person}'[/red]\n")
            raise typer.Exit(1)

        if len(people) > 1:
            console.print(f"[yellow]Found {len(people)} people matching '{person}':[/yellow]")
            for i, p in enumerate(people, 1):
                console.print(f"  {i}. {p.primary_name} (ID: {p.id})")
            choice = typer.prompt("\nEnter number to view", type=int)
            if choice < 1 or choice > len(people):
                console.print("[red]Invalid choice[/red]")
                raise typer.Exit(1)
            target_person = people[choice - 1]
        else:
            target_person = people[0]

        # Get events for this person
        birth_event = session.query(Event).filter(
            Event.person_id == target_person.id,
            Event.event_type == "birth"
        ).first()

        death_event = session.query(Event).filter(
            Event.person_id == target_person.id,
            Event.event_type == "death"
        ).first()

        # Build person info string
        person_info = f"[bold blue]{target_person.primary_name}[/bold blue]"
        if birth_event and birth_event.date:
            person_info += f"\n  Born: {birth_event.date}"
            if birth_event.place:
                person_info += f" in {birth_event.place}"
        if death_event and death_event.date:
            person_info += f"\n  Died: {death_event.date}"
            if death_event.place:
                person_info += f" in {death_event.place}"

        # Create tree visualization
        tree_root = Tree(person_info)

        # Add parents
        parent_rels = session.query(Relationship).filter(
            Relationship.source_person_id == target_person.id,
            Relationship.relationship_type == "parent"
        ).all()

        if parent_rels:
            parents_branch = tree_root.add("[yellow]Parents[/yellow]")
            for rel in parent_rels:
                parent = session.query(Person).filter(Person.id == rel.target_person_id).first()
                if parent:
                    parents_branch.add(f"[dim]{parent.primary_name}[/dim]")

        # Add spouse(s)
        spouse_rels = session.query(Relationship).filter(
            Relationship.source_person_id == target_person.id,
            Relationship.relationship_type == "spouse"
        ).all()

        if spouse_rels:
            spouse_branch = tree_root.add("[magenta]Spouse(s)[/magenta]")
            for rel in spouse_rels:
                spouse = session.query(Person).filter(Person.id == rel.target_person_id).first()
                if spouse:
                    spouse_branch.add(f"[dim]{spouse.primary_name}[/dim]")

        # Add children
        child_rels = session.query(Relationship).filter(
            Relationship.target_person_id == target_person.id,
            Relationship.relationship_type == "parent"
        ).all()

        if child_rels:
            children_branch = tree_root.add("[green]Children[/green]")
            for rel in child_rels:
                child = session.query(Person).filter(Person.id == rel.source_person_id).first()
                if child:
                    children_branch.add(f"[dim]{child.primary_name}[/dim]")

        # Display the tree
        console.print(tree_root)
        console.print()

        # Show source citation
        if target_person.source_document_id:
            doc = session.query(Document).filter(
                Document.id == target_person.source_document_id
            ).first()
            if doc:
                console.print(f"[dim]Source: {Path(doc.source).name}, Page {doc.page}[/dim]\n")

    finally:
        session.close()


@app.command()
def export(
    output: Path = typer.Argument(..., help="Output file path"),
    format: str = typer.Option("gedcom", "--format", "-f", help="Export format (gedcom)"),
    db_path: Path = typer.Option(Path("./genealogy.db"), "--db", help="Path to SQLite database"),
) -> None:
    """Export genealogy data to standard formats.

    Currently supports GEDCOM format for compatibility with other genealogy software.
    """
    if format.lower() != "gedcom":
        console.print(f"[red]Unsupported format: {format}[/red]")
        console.print("[yellow]Currently only 'gedcom' format is supported[/yellow]\n")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Exporting to GEDCOM:[/bold cyan] {output}\n")

    from src.backend.genealogy_ai.storage.sqlite import Event, Person, Relationship

    db = GenealogyDatabase(db_path=db_path)
    session = db.get_session()

    try:
        people = session.query(Person).all()

        if not people:
            console.print("[yellow]No people found in database. Nothing to export.[/yellow]\n")
            raise typer.Exit(1)

        # Build GEDCOM file
        gedcom_lines = []
        gedcom_lines.append("0 HEAD")
        gedcom_lines.append("1 SOUR Genealogy AI")
        gedcom_lines.append("1 GEDC")
        gedcom_lines.append("2 VERS 5.5.1")
        gedcom_lines.append("2 FORM LINEAGE-LINKED")
        gedcom_lines.append("1 CHAR UTF-8")

        # Add individuals
        for person in people:
            gedcom_lines.append(f"0 @I{person.id}@ INDI")
            gedcom_lines.append(f"1 NAME {person.primary_name}")

            # Add name variants
            for name in person.names:
                gedcom_lines.append(f"1 NAME {name.name}")
                if name.name_type:
                    gedcom_lines.append(f"2 TYPE {name.name_type}")

            # Add events
            events = session.query(Event).filter(Event.person_id == person.id).all()
            for event in events:
                event_tag = event.event_type.upper()
                if event_tag == "BIRTH":
                    gedcom_lines.append("1 BIRT")
                elif event_tag == "DEATH":
                    gedcom_lines.append("1 DEAT")
                elif event_tag == "MARRIAGE":
                    gedcom_lines.append("1 MARR")
                else:
                    gedcom_lines.append(f"1 EVEN {event_tag}")

                if event.date:
                    gedcom_lines.append(f"2 DATE {event.date}")
                if event.place:
                    gedcom_lines.append(f"2 PLAC {event.place}")
                if event.description:
                    gedcom_lines.append(f"2 NOTE {event.description}")

            # Add notes
            if person.notes:
                gedcom_lines.append(f"1 NOTE {person.notes}")

        # Add families (relationships)
        families = {}
        family_id = 1

        relationships = session.query(Relationship).all()
        for rel in relationships:
            if rel.relationship_type == "spouse":
                # Create family record
                fam_key = tuple(sorted([rel.source_person_id, rel.target_person_id]))
                if fam_key not in families:
                    families[fam_key] = family_id
                    gedcom_lines.append(f"0 @F{family_id}@ FAM")
                    gedcom_lines.append(f"1 HUSB @I{rel.source_person_id}@")
                    gedcom_lines.append(f"1 WIFE @I{rel.target_person_id}@")
                    family_id += 1

        # Add parent-child relationships
        for rel in relationships:
            if rel.relationship_type == "parent":
                # Find family containing this parent
                child_id = rel.source_person_id
                parent_id = rel.target_person_id

                # Look for existing family or create new one
                # For simplicity, add child to all families where parent appears
                for fam_key, fam_id in families.items():
                    if parent_id in fam_key:
                        # Find the family record and add child
                        for i, line in enumerate(gedcom_lines):
                            if line == f"0 @F{fam_id}@ FAM":
                                # Insert child after family declaration
                                gedcom_lines.insert(i + 3, f"1 CHIL @I{child_id}@")
                                break
                        break

        # Add trailer
        gedcom_lines.append("0 TRLR")

        # Write file
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write("\n".join(gedcom_lines))

        console.print(f"[bold green]✓ Exported {len(people)} people to {output}[/bold green]\n")

    finally:
        session.close()


@app.command()
def version() -> None:
    """Display version information."""
    from genealogy_ai import __version__

    console.print(f"\n[bold cyan]Genealogy AI[/bold cyan] version {__version__}\n")


if __name__ == "__main__":
    app()
