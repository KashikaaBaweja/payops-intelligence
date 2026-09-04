import re

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize whitespace and strip obvious boilerplate lines."""

    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _MULTI_SPACE.sub(" ", raw_line).strip()
        if line.lower() in {"confidential", "internal use only", "draft"}:
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = _MULTI_NEWLINE.sub("\n\n", cleaned)
    return cleaned.strip()
