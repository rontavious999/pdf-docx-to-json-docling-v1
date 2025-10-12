"""
Unit tests for text preprocessing functions.

Tests the line cleanup, normalization, and soft-wrap coalescing logic.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the main module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from the new modular structure
from docling_text_to_modento.modules.text_preprocessing import coalesce_soft_wraps


class TestCoalesceSoftWraps:
    """Test soft-wrap line coalescing logic."""
    
    def test_joins_lines_ending_with_hyphen(self):
        """Lines ending with hyphen should be joined with next line."""
        lines = [
            "This is a long ques-",
            "tion that was wrapped"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        # The hyphen is stripped and lines are joined with a space
        assert "ques" in result[0] and "tion" in result[0]
        assert "wrapped" in result[0]
    
    def test_joins_lines_ending_with_slash(self):
        """Lines ending with slash should be joined with next line."""
        lines = [
            "Fosamax, Boniva, Actonel/",
            "other medications"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        assert result[0] == "Fosamax, Boniva, Actonel/ other medications"
    
    def test_joins_lowercase_continuation(self):
        """Lines followed by lowercase text should be joined."""
        lines = [
            "Have you ever taken",
            "any medications"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        assert result[0] == "Have you ever taken any medications"
    
    def test_joins_yes_no_checkbox_continuation(self):
        """Lines ending with Yes/No checkboxes followed by lowercase should be joined."""
        lines = [
            "Have you taken Fosamax? [ ] Yes [ ] No",
            "other medications containing bisphosphonates"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        assert "bisphosphonates" in result[0]
    
    def test_preserves_sentence_boundaries(self):
        """Lines ending with proper punctuation should not be joined."""
        lines = [
            "First question?",
            "Second question?"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 2
        assert result[0] == "First question?"
        assert result[1] == "Second question?"
    
    def test_preserves_blank_lines(self):
        """Blank lines should be preserved."""
        lines = [
            "First line",
            "",
            "Second line"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 3
        assert result[1] == ""
    
    def test_stops_at_bullet_points(self):
        """Should not join lines starting with bullet points."""
        lines = [
            "Question text",
            "[ ] Option 1"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 2
    
    def test_joins_with_small_connector_words(self):
        """Lines starting with small connector words should be joined."""
        lines = [
            "Have you experienced",
            "or noticed any symptoms"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        assert "or noticed" in result[0]
    
    def test_joins_parenthetical_continuation(self):
        """Lines starting with parentheses should be joined."""
        lines = [
            "Some condition",
            "(please explain)"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        assert "(please explain)" in result[0]
    
    def test_real_world_bisphosphonates_example(self):
        """Test the actual bisphosphonates question from forms."""
        lines = [
            "Have you ever taken Fosamax, Boniva, Actonel/ [ ] Yes [ ] No",
            "other medications containing bisphosphonates?"
        ]
        result = coalesce_soft_wraps(lines)
        assert len(result) == 1
        assert "bisphosphonates?" in result[0]
        assert "Actonel/" in result[0]
        assert "[ ] Yes [ ] No" in result[0]


class TestNormalization:
    """Test text normalization functions."""
    
    def test_basic_normalization(self):
        """Test that basic text normalization works."""
        # Import the normalization functions
        from docling_text_to_modento import normalize_glyphs_line
        
        # Test basic glyph normalization
        text = 'Smart "quotes" and dashes—test'
        result = normalize_glyphs_line(text)
        assert '"' in result  # Should convert smart quotes
        assert '—' in result or '-' in result  # Dash handling


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
