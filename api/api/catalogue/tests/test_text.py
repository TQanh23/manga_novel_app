"""The HTML an author may store, and what counts as a paragraph: reading positions
are indexes into the split."""

import pytest

from api.catalogue.text import plain_text, sanitize_html, split_blocks


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("<script>alert(1)</script><p>Kept.</p>", "<p>Kept.</p>"),
        ('<p onclick="steal()">Kept.</p>', "<p>Kept.</p>"),
        ('<p style="color:red" class="x" id="y">Kept.</p>', "<p>Kept.</p>"),
        ('<p><img src="x" onerror="steal()">Kept.</p>', "<p>Kept.</p>"),
        ('<p><a href="javascript:steal()">Kept.</a></p>', "<p>Kept.</p>"),
        ('<p><a href="https://example.com">Kept.</a></p>', "<p>Kept.</p>"),
        ("<style>p{}</style><iframe src=x></iframe><p>Kept.</p>", "<p>Kept.</p>"),
        ("<p>Kept.<!-- a note --></p>", "<p>Kept.</p>"),
        ("<p>a &lt;script&gt; &amp; more</p>", "<p>a &lt;script&gt; &amp; more</p>"),
    ],
)
def test_nothing_that_can_run_or_fetch_is_stored(raw: str, stored: str) -> None:
    assert sanitize_html(raw) == stored


def test_the_editors_formatting_is_kept() -> None:
    raw = (
        "<h2>Chương một</h2>"
        "<p>Cô nói <strong>không</strong>, <em>hai lần</em>, <u>rõ</u> và <s>sai</s>.</p>"
        "<p>Dòng một<br>dòng hai</p>"
        "<blockquote><p>Một lời trích.</p></blockquote>"
        "<hr>"
        "<h3>Phần nhỏ</h3>"
    )

    assert split_blocks(sanitize_html(raw)) == [
        "<h2>Chương một</h2>",
        "<p>Cô nói <strong>không</strong>, <em>hai lần</em>, <u>rõ</u> và <s>sai</s>.</p>",
        "<p>Dòng một<br>dòng hai</p>",
        "<blockquote><p>Một lời trích.</p></blockquote>",
        "<hr>",
        "<h3>Phần nhỏ</h3>",
    ]


@pytest.mark.parametrize(
    ("raw", "blocks"),
    [
        ("One.\n\nTwo.", ["<p>One.</p>", "<p>Two.</p>"]),
        ("One.\n\n\n\n\nTwo.", ["<p>One.</p>", "<p>Two.</p>"]),
        # A line of spaces or tabs is a blank line.
        ("One.\n   \nTwo.\n\t\nThree.", ["<p>One.</p>", "<p>Two.</p>", "<p>Three.</p>"]),
        ("One.\r\n\r\nTwo.\r\n", ["<p>One.</p>", "<p>Two.</p>"]),
        ("\n\n  One.  \n\nTwo.\n\n\n", ["<p>One.</p>", "<p>Two.</p>"]),
        ("Only one.", ["<p>Only one.</p>"]),
        ("", []),
        ("  \n\n \t \n", []),
    ],
)
def test_pasted_plain_text_keeps_its_paragraphs(raw: str, blocks: list[str]) -> None:
    assert split_blocks(sanitize_html(raw)) == blocks


def test_loose_text_between_blocks_becomes_a_paragraph() -> None:
    raw = "Before <em>it</em>\n<h2>Title</h2>after"

    assert split_blocks(sanitize_html(raw)) == [
        "<p>Before <em>it</em></p>",
        "<h2>Title</h2>",
        "<p>after</p>",
    ]


@pytest.mark.parametrize("empty", ["<p></p>", "<p> </p>", "<p><br></p>", "<h2>\n</h2>"])
def test_a_block_with_no_words_is_not_a_paragraph(empty: str) -> None:
    assert split_blocks(sanitize_html(f"<p>One.</p>{empty}<p>Two.</p>")) == [
        "<p>One.</p>",
        "<p>Two.</p>",
    ]


def test_a_block_inside_a_block_is_unwrapped() -> None:
    assert sanitize_html("<strong>a<p>b</p></strong>") == "<p><strong>ab</strong></p>"
    assert sanitize_html("<blockquote><blockquote>deep</blockquote></blockquote>") == (
        "<blockquote>deep</blockquote>"
    )


def test_whitespace_html_ignores_is_collapsed_and_meaningful_spaces_are_kept() -> None:
    assert sanitize_html("<p>  spaced\n   out  </p>") == "<p>spaced out</p>"
    # A no-break space and an ideographic space mean something; they stay.
    assert sanitize_html("<p>Ông\u00a0Bách</p><p>月の\u3000下</p>") == (
        "<p>Ông\u00a0Bách</p>\n<p>月の\u3000下</p>"
    )


def test_stored_text_is_one_block_per_line_and_comes_out_the_same_when_saved_again() -> None:
    raw = '<p class="a">One.</p>\n\n\n<p>Two <b>bold</b>.</p><hr/><blockquote><p>Q</p></blockquote>'
    stored = sanitize_html(raw)

    assert stored == "<p>One.</p>\n<p>Two <b>bold</b>.</p>\n<hr>\n<blockquote><p>Q</p></blockquote>"
    assert sanitize_html(stored) == stored
    assert split_blocks(stored) == stored.split("\n")


def test_korean_japanese_and_vietnamese_paragraphs_are_kept_character_for_character() -> None:
    paragraphs = [
        "그날 밤, 비가 내렸다. 검사는 다시 길을 떠났다.",
        "月の下で、剣士は立ち止まった。言葉はなかった。",
        "Đêm ấy trời mưa. Người kiếm sĩ lại lên đường.",
    ]
    stored = sanitize_html("".join(f"<p>{text}</p>" for text in paragraphs))

    assert split_blocks(stored) == [f"<p>{text}</p>" for text in paragraphs]
    # No spaces between words to lean on: a paragraph without any is still one.
    assert split_blocks(sanitize_html("月の下で剣士は立ち止まった")) == [
        "<p>月の下で剣士は立ち止まった</p>"
    ]


def test_plain_text_is_the_words_without_markup() -> None:
    stored = sanitize_html("<h2>Tiêu đề</h2><p>Một <strong>hai</strong></p><hr><p>&lt;ba&gt;</p>")

    assert plain_text(stored) == "Tiêu đề\n\nMột hai\n\n<ba>"
    assert plain_text(sanitize_html("<hr><p> </p>")) == ""
