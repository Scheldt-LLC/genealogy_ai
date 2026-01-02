# Contributing to Genealogy AI

Thank you for your interest in contributing to Genealogy AI! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Project Principles](#project-principles)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:

   ```bash
   git clone https://github.com/your-username/genealogy-ai.git
   cd genealogy-ai
   ```

3. Add the upstream repository:

   ```bash
   git remote add upstream https://github.com/Scheldt-LLC/genealogy-ai.git
   ```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Tesseract OCR
- Git

### Installation

1. Install uv (if not already installed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

3. Install pre-commit hooks:

   ```bash
   pre-commit install
   ```

4. Verify your setup:

   ```bash
   pytest
   ruff check .
   mypy genealogy_ai
   ```

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

- Use a clear and descriptive title
- Describe the exact steps to reproduce the problem
- Provide specific examples
- Describe the behavior you observed and what you expected
- Include screenshots if relevant
- Note your environment (OS, Python version, etc.)

**Bug Report Template:**

```markdown
**Description**
A clear description of the bug.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Run command '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Environment**
- OS: [e.g., macOS 14.0]
- Python version: [e.g., 3.11.5]
- Project version: [e.g., 0.1.0]

**Additional Context**
Any other context about the problem.
```

### Suggesting Enhancements

Enhancement suggestions are welcome! Please provide:

- A clear and descriptive title
- A detailed description of the proposed feature
- Explain why this enhancement would be useful
- List any alternatives you've considered

### Your First Code Contribution

Unsure where to begin? Look for issues labeled:

- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `documentation` - Documentation improvements

### Pull Requests

1. Create a new branch for your feature:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following our [Coding Standards](#coding-standards)

3. Write or update tests as needed

4. Ensure all tests pass:

   ```bash
   pytest
   ```

5. Run linting and formatting:

   ```bash
   ruff format .
   ruff check .
   mypy genealogy_ai
   ```

6. Commit your changes with a meaningful message (see [Commit Guidelines](#commit-message-guidelines))

7. Push to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

8. Open a Pull Request

## Coding Standards

### Python Style Guide

We follow PEP 8 with some modifications, enforced by Ruff:

- **Line length**: 100 characters (not 79)
- **Quotes**: Double quotes for strings
- **Imports**: Sorted alphabetically, grouped by standard library, third-party, and local
- **Type hints**: Required for all functions and methods
- **Docstrings**: Google style for all public modules, classes, and functions

### Code Formatting

We use **Ruff** for both linting and formatting:

```bash
# Format code
ruff format .

# Check for linting issues
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Type Checking

We use **mypy** with strict mode:

```bash
mypy genealogy_ai
```

All functions should have type annotations:

```python
def extract_person(text: str, confidence_threshold: float = 0.7) -> list[Person]:
    """Extract person entities from text.

    Args:
        text: The text to extract from.
        confidence_threshold: Minimum confidence score.

    Returns:
        List of extracted Person objects.
    """
    ...
```

### Documentation

- **Docstrings**: Required for all public modules, classes, functions, and methods
- **Comments**: Use sparingly; code should be self-documenting
- **Type hints**: Always include for function parameters and returns
- **README updates**: Update if your changes affect user-facing functionality

**Docstring Example (Google Style):**

```python
def reconcile_people(
    candidates: list[Person],
    threshold: float = 0.85
) -> list[tuple[Person, Person, float]]:
    """Find potential duplicate people in the database.

    This function uses semantic similarity to identify people who might
    be the same person with different name spellings or data variations.

    Args:
        candidates: List of Person objects to check for duplicates.
        threshold: Similarity threshold (0.0 to 1.0). Higher values
            require more similarity. Defaults to 0.85.

    Returns:
        List of tuples containing (person1, person2, similarity_score)
        for each potential duplicate pair.

    Raises:
        ValueError: If threshold is not between 0.0 and 1.0.

    Example:
        >>> people = [Person(name="John Smith"), Person(name="Jon Smith")]
        >>> duplicates = reconcile_people(people, threshold=0.8)
        >>> len(duplicates)
        1
    """
    ...
```

## Testing Guidelines

### Test Structure

- **Unit tests**: In `tests/unit/` - Test individual functions/methods
- **Integration tests**: In `tests/integration/` - Test component interactions
- **Fixtures**: Share common test data using pytest fixtures

### Writing Tests

```python
import pytest
from genealogy_ai.agents.extract_entities import extract_person


class TestPersonExtraction:
    """Tests for person entity extraction."""

    def test_extract_simple_name(self):
        """Should extract a simple name from text."""
        text = "John Smith was born in 1850."
        result = extract_person(text)

        assert len(result) == 1
        assert result[0].name == "John Smith"

    def test_extract_with_confidence(self):
        """Should respect confidence threshold."""
        text = "Maybe someone named Jane?"
        result = extract_person(text, confidence_threshold=0.9)

        assert len(result) == 0

    @pytest.mark.slow
    def test_large_document(self):
        """Should handle large documents efficiently."""
        # Mark slow tests with @pytest.mark.slow
        ...
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_extraction.py

# Specific test
pytest tests/unit/test_extraction.py::TestPersonExtraction::test_extract_simple_name

# With coverage
pytest --cov=genealogy_ai --cov-report=html

# Skip slow tests
pytest -m "not slow"

# Only integration tests
pytest tests/integration
```

### Test Coverage

- Aim for >80% coverage for new code
- All public functions should have tests
- Critical paths (data integrity, source preservation) require 100% coverage

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Format

```text
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Maintenance tasks
- **ci**: CI/CD changes

### Examples

```text
feat(extraction): add support for handwritten dates

Implement fuzzy date parsing to handle common handwriting variations
like "abt 1850" or "circa 1850". Uses dateparser library with custom
patterns for genealogical documents.

Closes #42
```

```text
fix(ocr): handle rotated pages correctly

The OCR engine was failing on rotated scanned pages. Added automatic
rotation detection using pytesseract's OSD (Orientation and Script Detection).

Fixes #38
```

```text
docs(readme): update installation instructions for uv

Replaced pip installation instructions with uv-based setup.
Added troubleshooting section for common issues.
```

### Best Practices

- Use present tense ("add feature" not "added feature")
- Use imperative mood ("move cursor to..." not "moves cursor to...")
- First line should be ≤72 characters
- Reference issues and pull requests when relevant
- Explain **why** not just **what** in the body

## Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass locally
- [ ] New code has tests
- [ ] Documentation is updated
- [ ] Commit messages follow guidelines
- [ ] Branch is up to date with main

### PR Checklist

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] All tests pass

## Related Issues
Closes #(issue number)
```

### Review Process

1. At least one maintainer must review and approve
2. All CI checks must pass
3. Discussions must be resolved
4. Branch must be up to date with main

### After Merge

- Delete your feature branch
- Update your local main:

  ```bash
  git checkout main
  git pull upstream main
  ```

## Project Principles

When contributing, keep these principles in mind:

### 1. Preserve Original Data

**Never** delete or modify original source documents or OCR output.

```python
# GOOD: Store alongside original
original_text = "Jon Smith"
normalized_name = normalize_name(original_text)  # "John Smith"
# Store both in database

# BAD: Replace original
text = normalize_name(text)  # Original lost forever
```

### 2. Separate Ground Truth from Interpretations

```python
# GOOD: Clear provenance
class Person:
    primary_name: str  # From document
    source_document_id: str  # Reference to original
    confidence: float  # AI confidence

# BAD: Mixed data
class Person:
    name: str  # Is this from OCR or AI inference?
```

### 3. Human-in-the-Loop

Never auto-merge, auto-delete, or auto-correct without user approval:

```python
# GOOD: Suggest, don't apply
suggested_duplicates = find_duplicates(people)
return suggested_duplicates  # User reviews and approves

# BAD: Automatic merge
duplicates = find_duplicates(people)
for dup in duplicates:
    auto_merge(dup)  # No human oversight!
```

### 4. Transparency

- Prompts are stored in `prompts/` as markdown files
- Schemas are in `schemas/` as JSON/Python
- Confidence scores are always recorded
- AI model and version are logged

### 5. Correctness Over Speed

- Validate inputs
- Use type hints
- Write tests
- Document assumptions
- Preserve data integrity

## Questions?

If you have questions:

- Check existing [issues](https://github.com/Scheldt-LLC/genealogy-ai/issues)
- Start a [discussion](https://github.com/Scheldt-LLC/genealogy-ai/discussions)
- Read the [documentation](docs/)

Thank you for contributing to Genealogy AI!
