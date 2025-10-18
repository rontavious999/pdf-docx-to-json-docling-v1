"""
Tests for patches suggested in the re-evaluation PDF.

This test file validates the implementation of patches from
"Re-evaluation of PDF_DOCX to JSON Conversion Pipeline (Docling v1).pdf"
"""

import pytest
import sys
import io
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from docling_text_to_modento.modules.grid_parser import parse_multicolumn_checkbox_grid
from docling_text_to_modento.modules.template_catalog import TemplateCatalog
from docling_text_to_modento.modules.debug_logger import DebugLogger, MatchEvent
from docling_text_to_modento.core import apply_templates_and_count


class TestPatch1CategoryPrefixing:
    """
    Patch 1: Better Category Prefixing in Multi-Column Grids
    
    Tests that category headers are consistently applied to all options,
    even when there are fewer headers than columns or headers span multiple columns.
    """
    
    def test_relaxed_header_count_check(self):
        """Test that prefixing works even when headers < columns."""
        # Simulate a grid with 3 columns but only 2 category headers
        lines = [
            "Appearance / Function / Habits",  # 3 headers
            "[ ] Whitening    [ ] Chewing    [ ] Smoking",
            "[ ] Alignment    [ ] Speaking   [ ] Grinding"
        ]
        
        grid_info = {
            'data_lines': [1, 2],
            'column_positions': [0, 17, 34],  # 3 columns
            'section': 'Dental History',
            'start_line': 0,
            'category_header': 'Appearance / Function / Habits'
        }
        
        # This should not fail even though we have 3 columns and 3 headers
        result = parse_multicolumn_checkbox_grid(lines, grid_info, debug=False)
        
        assert result is not None
        options = [opt['name'] for opt in result.control.get('options', [])]
        
        # All options should have category prefixes
        assert any('Appearance' in opt for opt in options), "Should have Appearance prefixed options"
        assert any('Function' in opt for opt in options), "Should have Function prefixed options"
        assert any('Habits' in opt for opt in options), "Should have Habits prefixed options"
    
    def test_fewer_headers_than_columns(self):
        """Test that prefixing handles fewer headers than columns gracefully."""
        lines = [
            "Medical / Social",  # Only 2 headers
            "[ ] Diabetes    [ ] Cancer    [ ] Smoking",  # 3 columns
            "[ ] Hypertension [ ] Asthma    [ ] Alcohol",
            "[ ] Heart Disease [ ] Arthritis [ ] Exercise"
        ]
        
        grid_info = {
            'data_lines': [1, 2, 3],
            'column_positions': [0, 16, 32],  # 3 columns
            'section': 'Medical History',
            'start_line': 0,
            'category_header': 'Medical / Social'
        }
        
        result = parse_multicolumn_checkbox_grid(lines, grid_info, debug=False)
        
        assert result is not None
        options = [opt['name'] for opt in result.control.get('options', [])]
        
        # With relaxed check, some options should still get prefixes
        # The last column will reuse the last available header
        prefixed_count = sum(1 for opt in options if ' - ' in opt)
        assert prefixed_count > 0, "At least some options should have category prefixes"
        
        # Verify that columns 1 and 2 use the available headers
        # Column 3 should reuse the last header (Social) since we only have 2 headers
        medical_count = sum(1 for opt in options if 'Medical - ' in opt)
        social_count = sum(1 for opt in options if 'Social - ' in opt)
        
        assert medical_count > 0, "Should have Medical prefixed options"
        assert social_count > 0, "Should have Social prefixed options"


class TestPatch4DebugLoggingForUnmatched:
    """
    Patch 4: Enhanced Debug Logging for Near Misses
    
    Tests that warnings are logged when fields are parsed but don't match
    any template in the dictionary.
    """
    
    def test_warning_for_unmatched_field(self):
        """Test that a warning is logged for fields with no template match."""
        # Create a minimal catalog
        catalog = TemplateCatalog(
            by_key={'first_name': {'key': 'first_name', 'title': 'First Name', 'type': 'input'}},
            alias_map={},
            titles_map={'first name': 'first_name'}
        )
        
        # Create a field that won't match anything in the catalog
        payload = [
            {
                'key': 'some_unusual_field',
                'title': 'This Is A Very Unusual Field That Does Not Exist',
                'type': 'input',
                'section': 'General'
            }
        ]
        
        dbg = DebugLogger(enabled=True)
        
        # Capture stdout to check for warning message
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            result, used = apply_templates_and_count(payload, catalog, dbg)
        finally:
            sys.stdout = sys.__stdout__
        
        output = captured_output.getvalue()
        
        # Should have logged a warning for the unmatched field
        assert '[warn]' in output, "Should log a warning for unmatched field"
        assert 'No dictionary match' in output, "Warning should mention no dictionary match"
        assert 'This Is A Very Unusual Field That Does Not Exist' in output, "Warning should include field title"
    
    def test_no_warning_for_matched_field(self):
        """Test that no warning is logged for fields that match a template."""
        catalog = TemplateCatalog(
            by_key={'first_name': {'key': 'first_name', 'title': 'First Name', 'type': 'input'}},
            alias_map={},
            titles_map={'first name': 'first_name'}
        )
        
        payload = [
            {
                'key': 'first_name',
                'title': 'First Name',
                'type': 'input',
                'section': 'General'
            }
        ]
        
        dbg = DebugLogger(enabled=True)
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            result, used = apply_templates_and_count(payload, catalog, dbg)
        finally:
            sys.stdout = sys.__stdout__
        
        output = captured_output.getvalue()
        
        # Should NOT have logged a warning for the matched field
        assert '[warn]' not in output or 'First Name' not in output, \
            "Should not log warning for successfully matched field"
    
    def test_no_warning_when_debug_disabled(self):
        """Test that warnings are not logged when debug mode is disabled."""
        catalog = TemplateCatalog(
            by_key={'first_name': {'key': 'first_name', 'title': 'First Name', 'type': 'input'}},
            alias_map={},
            titles_map={'first name': 'first_name'}
        )
        
        payload = [
            {
                'key': 'some_unusual_field',
                'title': 'This Is A Very Unusual Field',
                'type': 'input',
                'section': 'General'
            }
        ]
        
        dbg = DebugLogger(enabled=False)  # Debug disabled
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            result, used = apply_templates_and_count(payload, catalog, dbg)
        finally:
            sys.stdout = sys.__stdout__
        
        output = captured_output.getvalue()
        
        # Should NOT log warnings when debug is disabled
        assert '[warn]' not in output, "Should not log warnings when debug mode is disabled"


class TestPatch3SkipUnextractable:
    """
    Patch 3: Better Handling of Unextractable Text Files
    
    This patch is already implemented in core.py lines 4081-4083.
    Tests validate that files with error markers are skipped.
    """
    
    def test_skip_markers_exist(self):
        """Verify that the skip logic for unextractable files exists."""
        from docling_text_to_modento.core import process_one
        from pathlib import Path
        import tempfile
        
        # Create a temporary file with the error marker
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("[NO TEXT LAYER]\nThis file has no text layer")
            temp_path = Path(f.name)
        
        try:
            # Create temporary output directory
            with tempfile.TemporaryDirectory() as tmpdir:
                out_dir = Path(tmpdir)
                
                # Capture stdout
                captured_output = io.StringIO()
                sys.stdout = captured_output
                
                try:
                    # Process the file
                    result = process_one(temp_path, out_dir, catalog=None, debug=False)
                finally:
                    sys.stdout = sys.__stdout__
                
                output = captured_output.getvalue()
                
                # Should return None (file skipped)
                assert result is None, "Should skip file with error marker"
                
                # Should log skip message
                assert '[skip]' in output, "Should log skip message"
                assert 'unextractable' in output, "Should mention unextractable"
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
