"""Unit tests for the lightweight (non-ML) pipeline pieces."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import collect, preprocess  # noqa: E402


def test_clean_text_collapses_whitespace_and_boilerplate():
    raw = "Real sentence about 4chan.\nSocial Sharing\n©  2023 All rights reserved"
    cleaned = preprocess.clean_text(raw)
    assert "Real sentence about 4chan." in cleaned
    assert "Social Sharing" not in cleaned
    assert "  " not in cleaned


def test_clean_text_handles_none():
    assert preprocess.clean_text(None) == ""


def test_detect_language_en_fr():
    assert preprocess.detect_language("This is clearly an English sentence about memes.") == "en"
    assert preprocess.detect_language("Ceci est une phrase clairement écrite en français.") == "fr"


def test_detect_language_fallback():
    assert preprocess.detect_language("", fallback="en") == "en"


def test_gdelt_query_quotes_multiword_keyword():
    assert collect._gdelt_query("far right", "cbc.ca") == '"far right" domainis:cbc.ca'
    assert collect._gdelt_query("4chan", "cbc.ca") == "4chan domainis:cbc.ca"


def test_normalize_seendate():
    assert collect._normalize_seendate("20230815T120000Z") == "2023-08-15"
    assert collect._normalize_seendate("bad") == "bad"


def test_lang_hint():
    assert collect._lang_hint("English", "fr") == "en"
    assert collect._lang_hint("French", "en") == "fr"
    assert collect._lang_hint("Spanish", "fr") == "fr"  # falls back to outlet default
