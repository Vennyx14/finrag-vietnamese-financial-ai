"""Read NAME=value pairs from a .env file without loading them into os.environ.

The file holds API keys, so nothing in this module puts a value into an
exception, a log record or a repr. The format is the subset that
`.env.example` documents:

- blank lines and lines whose first non-space character is '#' are skipped;
- a line without '=' or without a name is skipped;
- the name is the text before the first '='; the value is the rest, stripped,
  with one pair of matching surrounding quotes removed;
- an empty value is kept as "" so callers can tell "empty" from "missing";
- when a name appears twice, the later line wins.

No python-dotenv: this is all FinRAG needs (AGENTS.md section 11).
"""

from pathlib import Path
from typing import Dict, Union


def read_env_file(path: Union[str, Path]) -> Dict[str, str]:
    """Return the NAME=value pairs of a .env file; a missing file gives {}."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # The decoder's message quotes bytes of the file, which may be a key.
        raise ValueError(f"{path} is not UTF-8 text") from None
    values: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        name = name.strip()
        if not separator or not name:
            continue
        values[name] = _unquote(value.strip())
    return values


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value
