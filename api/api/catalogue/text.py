"""An episode's text: the HTML an author may write, and the one definition of "a paragraph"."""

import re
from collections import Counter
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser

import nh3

# What the editor produces. No attributes at all, so no links, images, styles or
# event handlers: nothing in a stored episode can run or fetch anything.
INLINE_TAGS = frozenset({"strong", "b", "em", "i", "u", "s", "br"})
BLOCK_TAGS = frozenset({"p", "h2", "h3", "blockquote", "hr"})
ALLOWED_TAGS = INLINE_TAGS | BLOCK_TAGS
_VOID_TAGS = frozenset({"br", "hr"})

# One or more blank lines; a line holding only spaces or tabs counts as blank.
_BLANK_LINES = re.compile(r"(?:\r?\n[ \t]*){2,}")
# The whitespace HTML collapses. No-break and ideographic spaces are left alone:
# they mean something in Vietnamese and Japanese text.
_COLLAPSIBLE = re.compile(r"[ \t\r\n\f]+")


@dataclass(frozen=True)
class Block:
    html: str
    text: str


class _BlockParser(HTMLParser):
    """Cuts HTML into top-level blocks.

    Text and inline tags lying loose at the top level are gathered into a <p>,
    and a blank line among them ends it, so pasted plain text keeps its
    paragraphs. A block inside a block is unwrapped (its text stays), except a
    <p> directly inside a <blockquote>. Tags outside the allowlist never get
    here from stored text; if one does, it is dropped and its text kept.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._outer: str | None = None
        self._implicit = False
        self._inner: list[str] = []
        self._text: list[str] = []
        # Tags open inside the current block, innermost last.
        self._open: list[str] = []
        # Block tags unwrapped because they were nested, so their end tags are skipped too.
        self._unwrapped: Counter[str] = Counter()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            return
        if tag in BLOCK_TAGS:
            self._start_block(tag)
            return
        if self._outer is None:
            self._open_block("p", implicit=True)
        if tag == "br":
            self._text.append("\n")
        self._inner.append(f"<{tag}>")
        if tag not in _VOID_TAGS:
            self._open.append(tag)

    def _start_block(self, tag: str) -> None:
        at_top = self._outer is None or (self._implicit and not self._open)
        if at_top:
            self._close_block()
            if tag == "hr":
                self.blocks.append(Block("<hr>", ""))
            else:
                self._open_block(tag, implicit=False)
        elif tag == "p" and self._outer == "blockquote" and not self._open:
            self._inner.append("<p>")
            self._open.append("p")
        elif tag != "hr":
            self._unwrapped[tag] += 1

    def handle_endtag(self, tag: str) -> None:
        if self._unwrapped[tag]:
            self._unwrapped[tag] -= 1
        elif tag in self._open:
            while self._open:
                closed = self._open.pop()
                self._inner.append(f"</{closed}>")
                if closed == tag:
                    break
        elif tag == self._outer and not self._implicit:
            self._close_block()

    def handle_data(self, data: str) -> None:
        if self._outer is not None and not (self._implicit and not self._open):
            self._append_text(data)
            return
        # Loose text at the top level: a blank line ends the paragraph.
        for index, part in enumerate(_BLANK_LINES.split(data)):
            if index > 0:
                self._close_block()
            if self._outer is None and not part.strip():
                continue
            if self._outer is None:
                self._open_block("p", implicit=True)
            self._append_text(part)

    def _append_text(self, data: str) -> None:
        collapsed = _COLLAPSIBLE.sub(" ", data)
        self._text.append(collapsed)
        self._inner.append(escape(collapsed, quote=False))

    def _open_block(self, tag: str, *, implicit: bool) -> None:
        self._outer, self._implicit = tag, implicit
        self._inner, self._text, self._open = [], [], []

    def _close_block(self) -> None:
        if self._outer is None:
            return
        self._inner.extend(f"</{tag}>" for tag in reversed(self._open))
        text = "".join(self._text).strip()
        # A block with no words in it (an empty line in the editor) is not a paragraph.
        if text:
            inner = "".join(self._inner).strip(" ")
            self.blocks.append(Block(f"<{self._outer}>{inner}</{self._outer}>", text))
        self._outer, self._implicit = None, False
        self._inner, self._text, self._open = [], [], []

    def close(self) -> None:
        super().close()
        self._close_block()


def _parse(body_html: str) -> list[Block]:
    parser = _BlockParser()
    parser.feed(body_html)
    parser.close()
    return parser.blocks


def sanitize_html(raw: str) -> str:
    """What an author's HTML is stored as.

    Everything outside the allowlist goes, then the text is cut into top-level
    blocks, one per line. The same text always comes out the same, so saving
    what is already stored adds no version.
    """
    cleaned = nh3.clean(raw, tags=set(ALLOWED_TAGS), attributes={}, link_rel=None)
    return "\n".join(block.html for block in _parse(cleaned))


def split_blocks(body_html: str) -> list[str]:
    """The paragraphs of an episode, in order, each one HTML block.

    Reading positions are indexes into this list, so every client and every job
    that needs paragraphs uses this function instead of splitting on its own.
    It looks at tags and line breaks only, never at spaces between words, so it
    holds for Korean, Japanese and Vietnamese alike.
    """
    return [block.html for block in _parse(body_html)]


def plain_text(body_html: str) -> str:
    """The words of an episode without markup, a blank line between paragraphs."""
    return "\n\n".join(block.text for block in _parse(body_html) if block.text)
