"""Minimal smoke test for repository foundation."""

from pathlib import Path
import src


def test_repository_foundation():
    """Verify project structure integrity and subpackage importability."""
    root = Path(__file__).resolve().parent.parent
    assert (root / "AGENTS.md").is_file()
    assert (root / "README.md").is_file()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src").is_dir()

    # Verify foundational subpackages can be imported without error
    import src.agent
    import src.evaluation
    import src.financial
    import src.ingestion
    import src.nlp
    import src.pipeline
    import src.retrieval

    assert src is not None
