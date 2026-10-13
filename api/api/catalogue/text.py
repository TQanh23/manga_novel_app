"""How an episode's text is divided: the one definition of "a paragraph"."""

import re

# One or more blank lines; a line holding only spaces or tabs counts as blank.
_BLANK_LINES = re.compile(r"(?:\r?\n[ \t]*){2,}")


def split_paragraphs(body_md: str) -> list[str]:
    """The paragraphs of an episode, in order, each still Markdown.

    A paragraph ends at a blank line. A single line break stays inside its
    paragraph, as it does in Markdown. Reading positions are indexes into this
    list, so every client and every job that needs paragraphs uses this
    function instead of splitting on its own. It looks at line breaks only,
    never at spaces between words, so it holds for Korean, Japanese and
    Vietnamese alike.
    """
    return [part.strip() for part in _BLANK_LINES.split(body_md) if part.strip()]
