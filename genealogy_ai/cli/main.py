"""Genealogy AI CLI - Main entry point.

This module provides the command-line interface for the Genealogy AI project.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from genealogy_ai.ingestion.chunking import DocumentChunker
from genealogy_ai.ingestion.ocr import OCRProcessor
from genealogy_ai.storage.chroma import ChromaStore
from genealogy_ai.storage.sqlite import GenealogyDatabase

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
def version() -> None:
    """Display version information."""
    from genealogy_ai import __version__

    console.print(f"\n[bold cyan]Genealogy AI[/bold cyan] version {__version__}\n")


if __name__ == "__main__":
    app()
