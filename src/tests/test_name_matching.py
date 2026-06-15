"""Unit tests for the fuzzy name-matching utilities."""
import pytest

from ..utils.name_matching import normalize_name, names_match, get_player_name


class TestNormalizeName:
    def test_lowercases_and_strips(self):
        assert normalize_name("  John SMITH  ") == "john smith"

    def test_removes_commas_and_periods(self):
        assert normalize_name("Smith, John.") == "smith john"

    def test_collapses_repeated_whitespace(self):
        assert normalize_name("John    Smith") == "john smith"

    def test_standardizes_jr_suffix(self):
        assert normalize_name("John Smith, Jr.") == "john smith jr"

    def test_maps_junior_to_jr(self):
        assert normalize_name("John Smith Junior") == "john smith jr"

    def test_maps_roman_numeral_suffix(self):
        assert normalize_name("Sammy Davis III") == "sammy davis 3"

    def test_empty_string(self):
        assert normalize_name("") == ""


class TestNamesMatch:
    def test_exact_after_normalization(self):
        result = names_match("John Smith Jr.", "john smith junior")
        assert result["match"] is True
        assert result["exact_match"] is True
        assert result["similarity"] == 1.0

    def test_fuzzy_match_tolerates_typo(self):
        result = names_match("Jon Travolta", "John Travolta")
        assert result["match"] is True
        assert result["exact_match"] is False
        assert result["similarity"] >= 0.85

    def test_below_threshold_does_not_match(self):
        result = names_match("Robert Downey", "Madonna Ciccone")
        assert result["match"] is False
        assert result["similarity"] < 0.85

    def test_short_names_skip_fuzzy(self):
        # Both shorter than min_length_for_fuzzy (4) and not equal -> no match.
        result = names_match("Li", "Lo")
        assert result["match"] is False
        assert result["similarity"] == 0.0

    def test_custom_threshold_can_loosen_match(self):
        loose = names_match("Robert Downey", "Robert Downer", threshold=0.5)
        assert loose["match"] is True

    def test_both_empty_strings_match_exactly(self):
        result = names_match("", "")
        assert result["match"] is True
        assert result["exact_match"] is True


class TestGetPlayerName:
    def test_joins_first_and_last(self):
        assert get_player_name({"FirstName": "John", "LastName": "Smith"}) == "John Smith"

    def test_handles_missing_fields(self):
        assert get_player_name({"FirstName": "Cher"}) == "Cher"
        assert get_player_name({}) == ""
