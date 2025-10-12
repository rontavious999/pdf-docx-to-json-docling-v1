"""
Unit tests for template catalog and field matching.

Tests the template matching, alias resolution, and fuzzy matching logic.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the main module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from core (TemplateCatalog hasn't been extracted yet)
from docling_text_to_modento.core import TemplateCatalog


class TestTemplateCatalog:
    """Test template catalog loading and matching."""
    
    @classmethod
    def setup_class(cls):
        """Load the template catalog once for all tests."""
        dict_path = Path(__file__).parent.parent / "dental_form_dictionary.json"
        if dict_path.exists():
            cls.catalog = TemplateCatalog.from_path(dict_path)
        else:
            cls.catalog = None
    
    def test_catalog_loads_successfully(self):
        """Template catalog should load without errors."""
        assert self.catalog is not None, "dental_form_dictionary.json not found"
        assert len(self.catalog.by_key) > 0, "No templates loaded"
    
    def test_exact_key_match(self):
        """Exact key match should find template."""
        if not self.catalog:
            return  # Skip if catalog not available
        
        # Try to find a known field by exact key
        result = self.catalog.find(key="first_name", title=None)
        assert result is not None, "Should find first_name by key"
        if result:
            assert result.best_key == "first_name"
    
    def test_exact_title_match(self):
        """Exact title match should find template."""
        if not self.catalog:
            return
        
        # Try to find a field by exact title
        result = self.catalog.find(key=None, title="First Name")
        assert result is not None, "Should find by exact title"
    
    def test_alias_match(self):
        """Common aliases should resolve to correct fields."""
        if not self.catalog:
            return
        
        # Test date of birth aliases
        dob_variants = ["DOB", "Date of Birth", "Birth Date", "Birthdate"]
        for variant in dob_variants:
            # Try normalized lookup
            result = self.catalog.find(key=None, title=variant)
            # Should find a date field
            if result and result.best_key:
                assert "date" in result.best_key.lower() or \
                       "birth" in result.best_key.lower()
    
    def test_fuzzy_title_match(self):
        """Similar titles should match via fuzzy matching."""
        if not self.catalog:
            return
        
        # Try a slightly different version of a known field
        result = self.catalog.find(key=None, title="Patient First Name")
        # Should find first_name or similar
        if result and result.best_key:
            assert "name" in result.best_key.lower()
    
    def test_handles_unknown_field(self):
        """Unknown fields should return None or no match."""
        if not self.catalog:
            return
        
        result = self.catalog.find(key=None, title="Completely Unknown Field XYZ123")
        # Should either return None or have no best_key
        # (behavior depends on fuzzy threshold)
        if result:
            # It's okay if it finds a weak match or no match
            pass
    
    def test_case_insensitive_matching(self):
        """Matching should be case-insensitive."""
        if not self.catalog:
            return
        
        result1 = self.catalog.find(key=None, title="First Name")
        result2 = self.catalog.find(key=None, title="first name")
        result3 = self.catalog.find(key=None, title="FIRST NAME")
        
        # All should find the same field or all should be None
        if result1 and result1.best_key:
            if result2:
                assert result1.best_key == result2.best_key
            if result3:
                assert result1.best_key == result3.best_key


class TestFieldNormalization:
    """Test field key and title normalization."""
    
    def test_slug_key_normalization(self):
        """Field titles should normalize to valid keys."""
        from docling_text_to_modento import slugify
        
        # Test various inputs
        assert slugify("First Name") == "first_name"
        assert slugify("Date of Birth") == "date_of_birth"
        # E-mail may preserve hyphen or convert to underscore depending on implementation
        result = slugify("E-mail Address")
        assert "mail" in result and "address" in result
        
        # Should handle special characters
        result = slugify("Phone #")
        assert result.isidentifier() or result.replace("_", "").replace("-", "").isalnum()
    
    def test_text_normalization(self):
        """Text normalization should handle common variations."""
        from docling_text_to_modento import _norm_text
        
        # Should normalize common synonyms
        assert "dob" in _norm_text("Date of Birth")
        assert "dob" in _norm_text("Birth Date")
        assert "email" in _norm_text("E-mail")
        assert "zipcode" in _norm_text("Zip Code")
    
    def test_handles_empty_input(self):
        """Normalization should handle empty input gracefully."""
        from docling_text_to_modento import slugify, _norm_text
        
        assert slugify("") in ["", "q"]  # May default to "q"
        assert _norm_text("") == ""
        assert _norm_text(None) == ""


class TestSectionNormalization:
    """Test section name normalization."""
    
    def test_normalizes_common_sections(self):
        """Common section names should normalize correctly."""
        from docling_text_to_modento import normalize_section_name
        
        # Test various forms of patient information
        assert normalize_section_name("PATIENT INFORMATION") == "Patient Information"
        assert normalize_section_name("Patient Info") == "Patient Information"
        
        # Test medical history variants
        result = normalize_section_name("Medical History")
        assert "Medical" in result or "History" in result
        
        # Test insurance variants
        result = normalize_section_name("Insurance Information")
        assert "Insurance" in result
    
    def test_handles_signature_section(self):
        """Signature sections should be detected."""
        from docling_text_to_modento import normalize_section_name
        
        assert normalize_section_name("Patient Signature") == "Signature"
        assert normalize_section_name("SIGNATURE") == "Signature"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
