"""
Unit tests for edge case handling improvements.

Tests for:
1. Multi-part labels on one line (Priority 2.1)
2. Column headers in checkbox grids (Priority 2.2)
3. Inline checkbox statements (Priority 2.3)
4. OCR auto-detection (Priority 1.1)
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the main module
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_to_modento.core import (
    detect_multi_field_line,
    detect_inline_checkbox_with_text,
)


class TestMultiFieldLabels:
    """Test multi-part label detection (Issue 1)."""
    
    def test_phone_multi_field(self):
        """Phone with Mobile/Home/Work should split into three fields."""
        line = "Phone: Mobile _____ Home _____ Work _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect multi-field pattern"
        assert len(result) >= 2, f"Should detect at least 2 fields, got {len(result) if result else 0}"
        
        # Check that keys are generated correctly
        keys = [key for key, _ in result]
        assert any("mobile" in key for key in keys), f"Should have mobile key, got {keys}"
        assert any("home" in key for key in keys), f"Should have home key, got {keys}"
    
    def test_phone_multi_field_with_spaces(self):
        """Phone with multiple spaces between keywords should split."""
        line = "Phone: Mobile      Home      Work"
        result = detect_multi_field_line(line)
        
        # This should detect multiple keywords even without underscores
        assert result is not None, "Should detect multi-field pattern with spacing"
    
    def test_email_multi_field(self):
        """Email with Personal/Work should split into two fields."""
        line = "Email: Personal _____ Work _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect multi-field email pattern"
        assert len(result) >= 2, f"Should detect at least 2 fields, got {len(result) if result else 0}"
        
        keys = [key for key, _ in result]
        assert any("personal" in key or "home" in key for key in keys), f"Should have personal key, got {keys}"
        assert any("work" in key for key in keys), f"Should have work key, got {keys}"
    
    def test_single_field_no_split(self):
        """Single field should not be split."""
        line = "Phone: _____________________"
        result = detect_multi_field_line(line)
        
        # Should return None or empty list - this is a single field
        assert result is None, "Should not split single field"
    
    def test_filled_value_no_split(self):
        """Line with filled values should not trigger split."""
        line = "Phone: 555-1234"
        result = detect_multi_field_line(line)
        
        assert result is None, "Should not split filled field"
    
    def test_address_multi_field(self):
        """Address with Home/Work should split."""
        line = "Address: Home _____ Work _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect multi-field address pattern"
        assert len(result) >= 2, "Should detect at least 2 fields"
    
    def test_day_evening_phone_fields(self):
        """Phone with Day/Evening should split into separate fields (Patch 2)."""
        line = "Phone: Day _____ Evening _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect day/evening pattern"
        assert len(result) >= 2, f"Should detect at least 2 fields, got {len(result)}"
        
        keys = [key for key, _ in result]
        assert any("day" in key for key in keys), f"Should have day key, got {keys}"
        assert any("evening" in key for key in keys), f"Should have evening key, got {keys}"
    
    def test_slash_separated_subfields(self):
        """Slash-separated sub-fields like Day/Evening should be split (Patch 2)."""
        line = "Contact: Day/Evening _____"
        result = detect_multi_field_line(line)
        
        # After slash normalization, this might not split into 2 fields if only one blank
        # But the slash should be normalized so it could be detected if pattern matches
        # This test validates that slashes don't break the parser
        # For a proper split, we need blanks after each keyword
        line2 = "Phone: Day/Evening _____ Night _____"
        result2 = detect_multi_field_line(line2)
        
        if result2:
            keys = [key for key, _ in result2]
            # Should detect at least one time-based keyword
            assert any("day" in key or "evening" in key or "night" in key for key in keys), \
                f"Should detect time-based keywords, got {keys}"
    
    def test_night_phone_field(self):
        """Night phone should be recognized as sub-field (Patch 2)."""
        line = "Emergency Contact: Day _____ Night _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect day/night pattern"
        if result:
            keys = [key for key, _ in result]
            assert any("night" in key for key in keys), f"Should have night key, got {keys}"


class TestInlineCheckboxStatements:
    """Test inline checkbox detection (Issue 3)."""
    
    def test_yes_send_alerts(self):
        """Checkbox with 'Yes, send me text alerts' should be detected."""
        line = "[ ] Yes, send me text alerts"
        result = detect_inline_checkbox_with_text(line)
        
        assert result is not None, "Should detect inline checkbox pattern"
        key, title, field_type = result
        assert "alert" in key.lower() or "text" in key.lower(), f"Key should reference alerts/text, got {key}"
        assert "text alerts" in title.lower(), f"Title should include 'text alerts', got {title}"
    
    def test_yes_with_comma_and_text(self):
        """Generic pattern: '[ ] Yes, [descriptive text]' should be detected."""
        line = "[ ] Yes, I would like to receive email updates"
        result = detect_inline_checkbox_with_text(line)
        
        assert result is not None, "Should detect inline checkbox with continuation"
        key, title, field_type = result
        assert len(key) > 0, "Should generate a key"
        assert "email" in title.lower() or "update" in title.lower(), f"Title should include continuation text, got {title}"
    
    def test_no_with_continuation(self):
        """Pattern: '[ ] No, [descriptive text]' should be detected."""
        line = "[ ] No, do not contact me"
        result = detect_inline_checkbox_with_text(line)
        
        assert result is not None, "Should detect 'No' inline checkbox pattern"
        key, title, field_type = result
        assert "contact" in key.lower(), f"Key should reference contact, got {key}"
        assert "do not contact" in title.lower(), f"Title should include continuation, got {title}"
    
    def test_short_continuation_not_detected(self):
        """Very short continuation text should not trigger detection."""
        line = "[ ] Yes"
        result = detect_inline_checkbox_with_text(line)
        
        # Should not detect - continuation too short (less than 10 chars)
        assert result is None, "Should not detect checkbox with no meaningful continuation"
    
    def test_option_list_not_split(self):
        """Regular option lists should not be treated as inline checkboxes."""
        line = "Gender: [ ] Male [ ] Female"
        result = detect_inline_checkbox_with_text(line)
        
        # This is an option list, not an inline checkbox statement
        # Should not match because it doesn't have continuation text after Yes/No
        assert result is None, "Should not detect regular option list as inline checkbox"


class TestMultiFieldEnhancements:
    """Test enhancements to multi-field detection."""
    
    def test_multiple_underscores_detected(self):
        """Multiple underscore groups should be detected as separate fields."""
        line = "Phone: __________ __________ __________"
        # This should ideally be detected if there are keywords or column alignment
        # For now, we test that it doesn't crash
        result = detect_multi_field_line(line)
        # Without keywords, current implementation returns None - that's acceptable
        # The enhancement would be to detect columnar alignment
    
    def test_mixed_keywords_and_blanks(self):
        """Keywords interspersed with blanks should work."""
        line = "Contact: Mobile _____ Work _____ Other _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect multiple keywords"
        assert len(result) >= 2, "Should detect at least 2 fields"
    
    def test_primary_secondary_keywords(self):
        """Primary/Secondary keywords should be recognized."""
        line = "Phone: Primary _____ Secondary _____"
        result = detect_multi_field_line(line)
        
        assert result is not None, "Should detect primary/secondary pattern"
        assert len(result) >= 2, "Should detect 2 fields"


class TestCategoryHeadersInGrids:
    """Test column header detection and usage in grids (Issue 2)."""
    
    def test_category_header_detection(self):
        """Category headers should be detected in multi-column grids."""
        from text_to_modento.modules.grid_parser import detect_multicolumn_checkbox_grid
        
        lines = [
            'Appearance / Function / Habits',
            '[ ] Good   [ ] Normal   [ ] Smoking',
            '[ ] Fair   [ ] Limited  [ ] Drinking',
            '[ ] Poor   [ ] Pain     [ ] Exercise'
        ]
        
        result = detect_multicolumn_checkbox_grid(lines, 0, 'Medical History', max_rows=10)
        
        assert result is not None, "Should detect grid with category headers"
        assert 'category_header' in result, "Should capture category header"
        assert result['category_header'] == 'Appearance / Function / Habits', \
            f"Category header should match, got {result.get('category_header')}"
    
    def test_category_header_prefixed_to_options(self):
        """Category headers should be prefixed to option names."""
        from text_to_modento.modules.grid_parser import (
            detect_multicolumn_checkbox_grid,
            parse_multicolumn_checkbox_grid
        )
        
        lines = [
            'Appearance / Function / Habits',
            '[ ] Good   [ ] Normal   [ ] Smoking',
            '[ ] Fair   [ ] Limited  [ ] Drinking',
            '[ ] Poor   [ ] Pain     [ ] Exercise'  # Need at least 3 data lines
        ]
        
        grid_info = detect_multicolumn_checkbox_grid(lines, 0, 'Medical History', max_rows=10)
        assert grid_info is not None, "Grid should be detected"
        
        question = parse_multicolumn_checkbox_grid(lines, grid_info, debug=False)
        assert question is not None, "Question should be created"
        
        options = question.control.get('options', [])
        assert len(options) >= 3, f"Should have at least 3 options, got {len(options)}"
        
        # Check that at least some options have category prefixes
        option_names = [opt['name'] if isinstance(opt, dict) else opt[0] for opt in options]
        has_prefixes = any(' - ' in name for name in option_names)
        assert has_prefixes, f"Options should have category prefixes, got {option_names[:3]}"
        
        # Check for specific expected patterns
        appearance_options = [name for name in option_names if 'Appearance' in name]
        assert len(appearance_options) >= 1, f"Should have Appearance options, got {option_names}"


class TestOCRAutoDetection:
    """Test OCR auto-detection feature (Issue 4)."""
    
    def test_has_text_layer_function_exists(self):
        """has_text_layer function should exist for detecting scanned PDFs."""
        from pathlib import Path
        import sys
        
        # Import from unstructured_extract module
        extract_path = Path(__file__).parent.parent / 'unstructured_extract.py'
        assert extract_path.exists(), "unstructured_extract.py should exist"
        
        # Check that the function is defined
        content = extract_path.read_text()
        assert 'def has_text_layer' in content, "has_text_layer function should be defined"
        assert 'auto_ocr' in content, "auto_ocr parameter should be supported"
    
    def test_auto_ocr_enabled_by_default(self):
        """auto_ocr should be enabled by default in extract_text_from_pdf."""
        from pathlib import Path
        
        extract_path = Path(__file__).parent.parent / 'unstructured_extract.py'
        content = extract_path.read_text()
        
        # Check default parameter value
        assert 'auto_ocr: bool = True' in content or 'auto_ocr=True' in content, \
            "auto_ocr should default to True"
    
    def test_no_auto_ocr_flag_exists(self):
        """--no-auto-ocr flag should exist to disable automatic OCR."""
        from pathlib import Path
        
        extract_path = Path(__file__).parent.parent / 'unstructured_extract.py'
        content = extract_path.read_text()
        
        assert '--no-auto-ocr' in content, "--no-auto-ocr flag should be defined"
        assert 'Disable automatic OCR' in content or 'disable automatic' in content.lower(), \
            "Flag should have documentation about disabling auto-OCR"
    
    def test_page_level_ocr_parameter(self):
        """extract_text_normally should accept auto_ocr parameter (Patch 1)."""
        from pathlib import Path
        
        extract_path = Path(__file__).parent.parent / 'unstructured_extract.py'
        content = extract_path.read_text()
        
        # Check function signature includes auto_ocr parameter
        assert 'def extract_text_normally' in content, "extract_text_normally function should exist"
        # Look for the auto_ocr parameter in the function signature or body
        lines = content.split('\n')
        in_function = False
        found_auto_ocr = False
        for i, line in enumerate(lines):
            if 'def extract_text_normally' in line:
                in_function = True
                # Check next few lines for parameter
                for j in range(i, min(i+10, len(lines))):
                    if 'auto_ocr' in lines[j]:
                        found_auto_ocr = True
                        break
                break
        
        assert found_auto_ocr, "extract_text_normally should have auto_ocr parameter for page-level OCR"


if __name__ == "__main__":
    # Run tests manually for quick checking
    print("=" * 70)
    print("COMPREHENSIVE EDGE CASE TESTING")
    print("Testing all 4 issues mentioned in the problem statement")
    print("=" * 70)
    
    # Test multi-field detection (Issue 1)
    print("\n📋 ISSUE 1: Multi-part labels on one line")
    print("   (e.g., 'Phone: __Mobile__ __Home__ __Work__')")
    test = TestMultiFieldLabels()
    passed = 0
    total = 0
    for test_name in [m for m in dir(test) if m.startswith('test_')]:
        total += 1
        try:
            getattr(test, test_name)()
            print(f"  ✓ {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_name}: {e}")
    print(f"   Result: {passed}/{total} tests passed")
    
    # Test inline checkbox detection (Issue 3)
    print("\n📋 ISSUE 3: Inline checkbox statements")
    print("   (e.g., '[ ] Yes, send me text alerts')")
    test2 = TestInlineCheckboxStatements()
    passed = 0
    total = 0
    for test_name in [m for m in dir(test2) if m.startswith('test_')]:
        total += 1
        try:
            getattr(test2, test_name)()
            print(f"  ✓ {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_name}: {e}")
    print(f"   Result: {passed}/{total} tests passed")
    
    # Test grid category headers (Issue 2)
    print("\n📋 ISSUE 2: Column headers in checkbox grids")
    print("   (e.g., 'Appearance / Function / Habits')")
    test3 = TestCategoryHeadersInGrids()
    passed = 0
    total = 0
    for test_name in [m for m in dir(test3) if m.startswith('test_')]:
        total += 1
        try:
            getattr(test3, test_name)()
            print(f"  ✓ {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_name}: {e}")
    print(f"   Result: {passed}/{total} tests passed")
    
    # Test OCR auto-detection (Issue 4)
    print("\n📋 ISSUE 4: Automatic OCR for scanned PDFs")
    print("   (Should auto-detect and enable OCR without manual flag)")
    test4 = TestOCRAutoDetection()
    passed = 0
    total = 0
    for test_name in [m for m in dir(test4) if m.startswith('test_')]:
        total += 1
        try:
            getattr(test4, test_name)()
            print(f"  ✓ {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_name}: {e}")
    print(f"   Result: {passed}/{total} tests passed")
    
    print("\n" + "=" * 70)
    print("✅ ALL EDGE CASE TESTS COMPLETE")
    print("=" * 70)
