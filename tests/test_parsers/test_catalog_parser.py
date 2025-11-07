"""Tests for the Catalog parser."""

import tempfile
from pathlib import Path
from typing import List
from unittest.mock import patch, mock_open, MagicMock

import pytest

from typedlogic import Term, Theory

# Import the catalog parser
from typedlogic.parsers.catalog_parser import CatalogParser


class TestCatalogParser:
    """Test cases for CatalogParser."""
    
    @pytest.fixture
    def parser(self) -> CatalogParser:
        """Create a parser instance."""
        return CatalogParser()
    
    @pytest.fixture
    def parser_fail_fast(self) -> CatalogParser:
        """Create a parser instance with fail_fast enabled."""
        return CatalogParser(fail_fast=True)
    
    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Get path to test fixtures directory."""
        return Path(__file__).parent / "fixtures"
    
    def test_parse_basic_catalog(self, parser: CatalogParser, fixtures_dir: Path):
        """Test parsing a basic catalog with local files."""
        catalog_path = fixtures_dir / "catalogs" / "basic_catalog.catalog.yaml"
        
        theory = parser.parse(catalog_path)
        
        # Should have merged content from both CSV and YAML files
        assert theory.ground_terms is not None
        assert len(theory.ground_terms) > 0
        
        # Check that catalog metadata is preserved
        assert theory.name == "Basic Test Catalog"
        assert hasattr(theory, '_annotations')
        assert theory._annotations is not None
        assert 'catalog_metadata' in theory._annotations
        
        metadata = theory._annotations['catalog_metadata']
        assert metadata['name'] == "Basic Test Catalog"
        assert metadata['version'] == "1.0"
    
    def test_parse_catalog_from_string(self, parser: CatalogParser, fixtures_dir: Path):
        """Test parsing catalog content from string."""
        catalog_content = f"""
metadata:
  name: "String Test Catalog"
  
resources:
  - path: "{fixtures_dir / 'csv' / 'simple.csv'}"
    format: "dataframe"
"""
        
        theory = parser.parse(catalog_content)
        
        assert theory.name == "String Test Catalog"
        assert theory.ground_terms is not None
        assert len(theory.ground_terms) == 3  # 3 rows in simple.csv
        
        # Check that facts have correct predicate (filename-based from CSV path)
        first_term = theory.ground_terms[0]
        assert first_term.predicate == 'simple'
    
    def test_parse_ground_terms_method(self, parser: CatalogParser, fixtures_dir: Path):
        """Test parse_ground_terms method specifically."""
        catalog_path = fixtures_dir / "catalogs" / "basic_catalog.catalog.yaml" 
        
        terms = parser.parse_ground_terms(catalog_path)
        
        assert isinstance(terms, list)
        assert len(terms) > 0
        assert all(isinstance(term, Term) for term in terms)
    
    def test_theory_merging(self, parser: CatalogParser):
        """Test theory merging logic with multiple theories."""
        # Create test theories
        theory1 = Theory()
        theory1.ground_terms = [Term("person", "alice"), Term("age", "alice", 25)]
        
        theory2 = Theory() 
        theory2.ground_terms = [Term("person", "bob"), Term("age", "bob", 30)]
        
        # Test merging
        merged = parser._merge_theories([theory1, theory2])
        
        assert len(merged.ground_terms) == 4
        assert Term("person", "alice") in merged.ground_terms
        assert Term("person", "bob") in merged.ground_terms
    
    def test_format_guessing(self, parser: CatalogParser):
        """Test format guessing from file extensions."""
        test_cases = [
            ("data.csv", "dataframe"),
            ("schema.yaml", "yaml"),
            ("rules.py", "python"),
            ("facts.json", "jsonlog"),
            ("unknown.xyz", "yaml"),  # defaults to yaml
        ]
        
        for filename, expected_format in test_cases:
            actual_format = parser._guess_format_from_path(filename)
            assert actual_format == expected_format
    
    def test_resource_loading_local_path(self, parser: CatalogParser, fixtures_dir: Path):
        """Test loading local file resources."""
        resource_spec = {
            "path": "csv/simple.csv",
            "format": "dataframe"
        }
        base_path = fixtures_dir
        
        content = parser._load_resource_content(resource_spec, base_path)
        
        assert isinstance(content, Path)
        assert content.exists()
        assert content.name == "simple.csv"
    
    @patch('typedlogic.parsers.catalog_parser.urlopen')
    def test_resource_loading_url(self, mock_urlopen, parser: CatalogParser):
        """Test loading URL resources."""
        # Mock URL response - need to mock the response.read() method
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"test": "data"}'  # Return bytes
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        resource_spec = {
            "url": "https://example.com/data.json",
            "format": "jsonlog",
            "headers": {"Authorization": "Bearer token123"}
        }
        
        content = parser._load_resource_content(resource_spec, None)
        
        assert isinstance(content, str)
        assert content == '{"test": "data"}'
        
        # Verify request was made with headers
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "https://example.com/data.json"
        assert request.headers.get('Authorization') == 'Bearer token123'
    
    def test_validation_valid_catalog(self, parser: CatalogParser, fixtures_dir: Path):
        """Test validation of a valid catalog."""
        catalog_path = fixtures_dir / "catalogs" / "basic_catalog.catalog.yaml"
        
        validation_messages = list(parser.validate(catalog_path))
        
        # Should have no errors, possibly some warnings
        error_messages = [msg for msg in validation_messages if msg.level == 'error']
        assert len(error_messages) == 0
    
    def test_validation_invalid_catalog(self, parser: CatalogParser, fixtures_dir: Path):
        """Test validation of an invalid catalog."""
        catalog_path = fixtures_dir / "catalogs" / "invalid_catalog.catalog.yaml"
        
        validation_messages = list(parser.validate(catalog_path))
        
        # Should have multiple errors
        error_messages = [msg for msg in validation_messages if msg.level == 'error']
        assert len(error_messages) > 0
        
        # Check for specific expected errors
        error_texts = [msg.message for msg in error_messages]
        assert any("not found" in text for text in error_texts)  # nonexistent file
        assert any("unknown format" in text.lower() for text in error_texts)  # unknown format
    
    def test_validation_missing_resources(self, parser: CatalogParser):
        """Test validation of catalog with missing resources section."""
        catalog_content = """
metadata:
  name: "No Resources Catalog"
"""
        
        validation_messages = list(parser.validate(catalog_content))
        
        error_messages = [msg for msg in validation_messages if msg.level == 'error']
        assert len(error_messages) > 0
        assert any("resources" in msg.message for msg in error_messages)
    
    def test_validation_module_type(self, parser: CatalogParser):
        """Test validation rejects ModuleType input."""
        import sys
        
        validation_messages = list(parser.validate(sys))
        
        error_messages = [msg for msg in validation_messages if msg.level == 'error']
        assert len(error_messages) > 0
        assert any("modules" in msg.message for msg in error_messages)
    
    def test_error_handling_fail_fast_disabled(self, parser: CatalogParser):
        """Test error handling when fail_fast is disabled (default)."""
        catalog_content = """
metadata:
  name: "Mixed Success Catalog"
  
resources:
  - path: "nonexistent.csv"
    format: "dataframe"
  - path: "also_nonexistent.yaml" 
    format: "yaml"
"""
        
        # Should not raise exception, but collect errors
        theory = parser.parse(catalog_content)
        
        # Should have error annotations
        assert hasattr(theory, '_annotations')
        assert theory._annotations is not None
        assert 'resource_errors' in theory._annotations
        assert len(theory._annotations['resource_errors']) == 2
    
    def test_error_handling_fail_fast_enabled(self, parser_fail_fast: CatalogParser):
        """Test error handling when fail_fast is enabled."""
        catalog_content = """
metadata:
  name: "Fail Fast Test"
  
resources:
  - path: "nonexistent.csv"
    format: "dataframe"
"""
        
        # Should raise exception on first error
        with pytest.raises(ValueError, match="Failed to parse resource"):
            parser_fail_fast.parse(catalog_content)
    
    def test_empty_catalog(self, parser: CatalogParser):
        """Test handling of catalog with no resources."""
        catalog_content = """
metadata:
  name: "Empty Catalog"
  
resources: []
"""
        
        theory = parser.parse(catalog_content)
        
        assert theory.name == "Empty Catalog"
        assert theory.ground_terms == [] or theory.ground_terms is None
    
    def test_cli_integration(self, parser: CatalogParser, fixtures_dir: Path):
        """Test integration with CLI format detection."""
        from typedlogic.cli import _guess_format
        
        # Test catalog file detection
        catalog_path = Path("test.catalog.yaml")
        assert _guess_format(catalog_path) == "catalog"
        
        catalog_path2 = Path("test.catalog.yml") 
        assert _guess_format(catalog_path2) == "catalog"
        
        # Test that catalog parser is properly registered
        from typedlogic.registry import get_parser
        catalog_parser = get_parser("catalog")
        assert isinstance(catalog_parser, CatalogParser)


class TestCatalogParserAdvanced:
    """Advanced test cases for CatalogParser."""
    
    @pytest.fixture
    def parser(self) -> CatalogParser:
        return CatalogParser()
    
    def test_complex_catalog_structure(self, parser: CatalogParser):
        """Test parsing a complex catalog with various resource types."""
        catalog_content = """
metadata:
  name: "Complex Catalog"
  description: "Multi-format resource catalog"
  version: "2.0"
  author: "Test Suite"
  tags: ["test", "complex"]
  
resources:
  - path: "schemas/main.yaml"
    format: "linkml"
    type: "schema"
    description: "Main schema"
    
  - path: "data/facts.csv"
    format: "dataframe" 
    type: "facts"
    description: "Tabular facts"
    
  - path: "rules/logic.py"
    format: "python"
    type: "axioms"
    description: "Python logic rules"
"""
        
        with patch.object(parser, '_load_resource_content') as mock_load:
            with patch.object(parser, '_parse_resource') as mock_parse:
                # Mock successful resource parsing
                mock_theory = Theory()
                mock_theory.ground_terms = [Term("test", "data")]
                mock_parse.return_value = mock_theory
                
                theory = parser.parse(catalog_content)
                
                assert theory.name == "Complex Catalog"
                assert theory._annotations is not None
                assert 'catalog_metadata' in theory._annotations
                
                metadata = theory._annotations['catalog_metadata']
                assert metadata['version'] == "2.0" 
                assert metadata['author'] == "Test Suite"
                assert "complex" in metadata['tags']
                
                # Should have called parse_resource for each resource
                assert mock_parse.call_count == 3
    
    @patch('typedlogic.parsers.catalog_parser.urlopen')
    def test_url_error_handling(self, mock_urlopen, parser: CatalogParser):
        """Test URL loading error handling."""
        catalog_content = """
metadata:
  name: "URL Error Test"
  
resources:
  - url: "https://invalid-domain-that-does-not-exist.com/data.json"
    format: "jsonlog"
"""
        # Mock URL error
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("nodename nor servname provided, or not known")
        
        # Should collect URL error but not fail completely
        theory = parser.parse(catalog_content)
        
        assert theory._annotations is not None
        assert 'resource_errors' in theory._annotations
        assert len(theory._annotations['resource_errors']) == 1
        assert "invalid-domain-that-does-not-exist.com" in theory._annotations['resource_errors'][0]
    
    def test_theory_merging_with_conflicts(self, parser: CatalogParser):
        """Test theory merging when there are predicate definition conflicts."""
        # Create theories with overlapping predicate definitions
        from typedlogic.datamodel import PredicateDefinition
        
        theory1 = Theory()
        theory1.predicate_definitions = [
            PredicateDefinition(predicate="Person", arguments={"name": "str", "age": "int"})
        ]
        theory1.ground_terms = [Term("Person", "alice", 25)]
        
        theory2 = Theory()
        theory2.predicate_definitions = [
            PredicateDefinition(predicate="Person", arguments={"name": "str", "city": "str"}),  # Conflict
            PredicateDefinition(predicate="Company", arguments={"name": "str"})
        ]
        theory2.ground_terms = [Term("Company", "TechCorp")]
        
        merged = parser._merge_theories([theory1, theory2])
        
        # Should keep first definition and add non-conflicting ones
        assert len(merged.predicate_definitions) == 2
        predicates = {pd.predicate for pd in merged.predicate_definitions}
        assert "Person" in predicates
        assert "Company" in predicates
        
        # Should merge all ground terms
        assert len(merged.ground_terms) == 2
    
    @patch('typedlogic.parsers.catalog_parser.urlopen')
    def test_url_with_custom_headers(self, mock_urlopen, parser: CatalogParser):
        """Test URL loading with custom headers."""
        catalog_content = """
metadata:
  name: "Header Test"
  
resources:
  - url: "https://api.example.com/data"
    format: "jsonlog"
    headers:
      Authorization: "Bearer secret-token"
      User-Agent: "TypedLogic/1.0"
      Content-Type: "application/json"
"""
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = b'[{"test": "data"}]'  # Return bytes
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Mock the JSON log parser to avoid format issues
        with patch('typedlogic.registry.get_parser') as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = Theory()
            mock_get_parser.return_value = mock_parser
            
            theory = parser.parse(catalog_content)
            
            # Verify request was made with all headers
            mock_urlopen.assert_called_once()
            request = mock_urlopen.call_args[0][0]
            
            assert request.headers.get('Authorization') == 'Bearer secret-token'
            assert request.headers.get('User-agent') == 'TypedLogic/1.0'  # Headers are normalized
            assert request.headers.get('Content-type') == 'application/json'
    
    def test_relative_path_resolution(self, parser: CatalogParser):
        """Test that relative paths are resolved correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a subdirectory and files
            data_dir = temp_path / "data"
            data_dir.mkdir()
            
            csv_file = data_dir / "test.csv"
            csv_file.write_text("name,value\ntest,123")
            
            catalog_file = temp_path / "test.catalog.yaml"
            catalog_content = """
metadata:
  name: "Relative Path Test"
  
resources:
  - path: "data/test.csv"
    format: "dataframe"
"""
            catalog_file.write_text(catalog_content)
            
            # Parse catalog
            theory = parser.parse(catalog_file)
            
            # Should successfully load the relative file
            assert theory.ground_terms is not None
            assert len(theory.ground_terms) == 1  # One row of data
            
            # Check the data was loaded correctly
            term = theory.ground_terms[0]
            assert term.predicate == "test"  # Predicate name inferred from filename
            assert term.bindings["name"] == "test"
            assert term.bindings["value"] == 123


class TestCatalogParserRegistry:
    """Test catalog parser registry integration."""
    
    def test_parser_registration(self):
        """Test that catalog parser is properly registered."""
        from typedlogic.registry import get_parser, all_parser_classes
        
        # Should be able to get catalog parser
        parser = get_parser("catalog")
        assert isinstance(parser, CatalogParser)
        
        # Should appear in all parsers list
        all_parsers = all_parser_classes()
        assert "catalog" in all_parsers
        assert all_parsers["catalog"] == CatalogParser
    
    def test_default_suffix(self):
        """Test default suffix is set correctly."""
        assert CatalogParser.default_suffix == "catalog.yaml"