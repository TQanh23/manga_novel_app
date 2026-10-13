"""What counts as a paragraph: reading positions are indexes into this split."""

import pytest

from api.catalogue.text import split_paragraphs


@pytest.mark.parametrize(
    ("body_md", "paragraphs"),
    [
        ("One.\n\nTwo.", ["One.", "Two."]),
        ("One.\n\n\n\n\nTwo.", ["One.", "Two."]),
        # A line of spaces or tabs is a blank line.
        ("One.\n   \nTwo.\n\t\nThree.", ["One.", "Two.", "Three."]),
        ("One.\r\n\r\nTwo.\r\n", ["One.", "Two."]),
        ("\n\n  One.  \n\nTwo.\n\n\n", ["One.", "Two."]),
        ("Only one.", ["Only one."]),
        ("", []),
        ("  \n\n \t \n", []),
    ],
)
def test_a_blank_line_ends_a_paragraph(body_md: str, paragraphs: list[str]) -> None:
    assert split_paragraphs(body_md) == paragraphs


def test_a_single_line_break_stays_inside_its_paragraph() -> None:
    body_md = "A line of verse,\nand the next.\n\nA new paragraph."

    assert split_paragraphs(body_md) == ["A line of verse,\nand the next.", "A new paragraph."]


def test_markdown_is_kept_as_written() -> None:
    body_md = "# Chapter One\n\nShe said **no**, _twice_.\n\n> A quoted line\n\n---"

    assert split_paragraphs(body_md) == [
        "# Chapter One",
        "She said **no**, _twice_.",
        "> A quoted line",
        "---",
    ]


def test_korean_japanese_and_vietnamese_paragraphs_are_kept_character_for_character() -> None:
    paragraphs = [
        "그날 밤, 비가 내렸다. 검사는 다시 길을 떠났다.",
        "月の下で、剣士は立ち止まった。言葉はなかった。",
        "Đêm ấy trời mưa. Người kiếm sĩ lại lên đường.",
    ]

    assert split_paragraphs("\n\n".join(paragraphs)) == paragraphs
    # No spaces between words to lean on: a paragraph without any is still one.
    assert split_paragraphs("月の下で剣士は立ち止まった") == ["月の下で剣士は立ち止まった"]
