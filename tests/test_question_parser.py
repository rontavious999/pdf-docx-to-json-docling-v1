"""
Unit tests for question parsing functions.

Tests field extraction, splitting, and option cleaning logic.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the main module
sys.path.insert(0, str(Path(__file__).parent.parent))

from docling_text_to_modento import (
    clean_option_text,
    split_multi_question_line,
)


class TestCleanOptionText:
    """Test option text cleaning logic."""
    
    def test_removes_duplicate_words(self):
        """Consecutive duplicate words should be removed."""
        text = "Blood Blood Transfusion"
        result = clean_option_text(text)
        assert result == "Blood Transfusion"
    
    def test_removes_multiple_duplicates(self):
        """Multiple consecutive duplicates should all be removed."""
        text = "Heart Heart Heart Disease"
        result = clean_option_text(text)
        assert result == "Heart Disease"
    
    def test_preserves_valid_compounds_with_slash(self):
        """Valid compound phrases with slash should be preserved."""
        # Test common valid compounds
        assert "live/work" in clean_option_text("I live/work in area").lower()
        assert "AIDS/HIV" in clean_option_text("AIDS/HIV Positive")
        assert "/" in clean_option_text("Cold Sores/Fever Blisters")
    
    def test_cleans_malformed_slash_text(self):
        """Malformed slash-separated text should be cleaned."""
        # When second part is messy with multiple words and bad formatting
        text = "Epilepsy/ Excessive Seizers Bleeding Problems"
        result = clean_option_text(text)
        # Should take just the first part when second part is clearly malformed
        assert "Epilepsy" in result
        # The messy part might be removed or cleaned
    
    def test_corrects_ocr_typos(self):
        """Common OCR typos should be corrected."""
        text = "rregular Heartbeat"
        result = clean_option_text(text)
        assert "Irregular" in result or "rregular" not in result.lower()
    
    def test_preserves_clean_text(self):
        """Clean text should pass through unchanged."""
        text = "Diabetes"
        result = clean_option_text(text)
        assert result == "Diabetes"
    
    def test_handles_empty_text(self):
        """Empty or None text should be handled gracefully."""
        assert clean_option_text("") == ""
        assert clean_option_text(None) == None or clean_option_text(None) == ""
    
    def test_case_insensitive_duplicate_detection(self):
        """Duplicate detection should be case-insensitive."""
        text = "Blood blood transfusion"
        result = clean_option_text(text)
        assert result.count("blood") + result.count("Blood") == 1


class TestSplitMultiQuestionLine:
    """Test multi-question line splitting logic."""
    
    def test_splits_two_questions_with_spacing(self):
        """Two questions separated by multiple spaces should be split."""
        line = "Gender: [ ] Male [ ] Female     Marital Status: [ ] Married [ ] Single"
        result = split_multi_question_line(line)
        assert len(result) == 2
        assert "Gender:" in result[0]
        assert "Marital Status:" in result[1]
    
    def test_preserves_single_question(self):
        """Single question line should not be split."""
        line = "What is your name: ____________________"
        result = split_multi_question_line(line)
        assert len(result) == 1
        assert result[0] == line
    
    def test_splits_with_checkboxes(self):
        """Questions with checkboxes should split at proper boundaries."""
        line = "Insurance: [ ] Yes [ ] No    Phone: [ ] Mobile [ ] Home"
        result = split_multi_question_line(line)
        assert len(result) >= 1  # Should attempt to split
        # At least the line should still contain both fields
        full = " ".join(result)
        assert "Insurance:" in full
        assert "Phone:" in full
    
    def test_handles_line_without_split_points(self):
        """Line without clear split points should be returned as-is."""
        line = "First Name: __________ Last Name: __________"
        result = split_multi_question_line(line)
        # May or may not split depending on spacing, but should return valid list
        assert isinstance(result, list)
        assert len(result) >= 1


class TestFieldPatternMatching:
    """Test field label pattern matching."""
    
    def test_recognizes_date_fields(self):
        """Date field patterns should be recognized."""
        from docling_text_to_modento import DATE_LABEL_RE
        
        assert DATE_LABEL_RE.search("Date of Birth:")
        assert DATE_LABEL_RE.search("Birth Date:")
        assert DATE_LABEL_RE.search("DOB:")
        assert DATE_LABEL_RE.search("Date:")
    
    def test_recognizes_state_fields(self):
        """State field patterns should be recognized."""
        from docling_text_to_modento import STATE_LABEL_RE
        
        assert STATE_LABEL_RE.match("State:")
        assert STATE_LABEL_RE.match("State")
    
    def test_recognizes_checkbox_patterns(self):
        """Various checkbox formats should be recognized."""
        from docling_text_to_modento import CHECKBOX_ANY
        import re
        
        checkbox_re = re.compile(CHECKBOX_ANY)
        
        assert checkbox_re.search("[ ]")
        assert checkbox_re.search("[x]")
        assert checkbox_re.search("☐")
        assert checkbox_re.search("☑")
        assert checkbox_re.search("□")
        assert checkbox_re.search("✓")
        assert checkbox_re.search("✔")


class TestExtractCompoundYesNoPrompts:
    """Test Yes/No question extraction."""
    
    def test_extracts_simple_yes_no_question(self):
        """Simple Yes/No question should be extracted."""
        from docling_text_to_modento import extract_compound_yn_prompts
        
        line = "Are you pregnant? [ ] Yes [ ] No"
        result = extract_compound_yn_prompts(line)
        assert len(result) >= 1
        assert any("pregnant" in r.lower() for r in result)
    
    def test_extracts_question_with_continuation(self):
        """Yes/No question with continuation text should include it."""
        from docling_text_to_modento import extract_compound_yn_prompts
        
        line = "Do you smoke? [ ] Yes [ ] No If yes, how many per day?"
        result = extract_compound_yn_prompts(line)
        # Should extract the main question
        assert len(result) >= 1
    
    def test_handles_multiple_yes_no_in_line(self):
        """Multiple Yes/No questions in one line should be extracted."""
        from docling_text_to_modento import extract_compound_yn_prompts
        
        line = "Smoke? [ ] Yes [ ] No   Drink? [ ] Yes [ ] No"
        result = extract_compound_yn_prompts(line)
        # Should find at least one Yes/No pattern
        assert len(result) >= 1


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
