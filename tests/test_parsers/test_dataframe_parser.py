"""Tests for the DataFrame parser."""

import tempfile
from pathlib import Path
from typing import List

import pytest

from typedlogic import Term

# Check if pandas is available
pandas = pytest.importorskip("pandas")

from typedlogic.parsers.dataframe_parser import DataFrameParser


class TestDataFrameParser:
    """Test cases for DataFrameParser."""
    
    @pytest.fixture
    def parser(self) -> DataFrameParser:
        """Create a parser instance."""
        return DataFrameParser()
    
    def test_parse_csv_from_string(self, parser: DataFrameParser):
        """Test parsing CSV content from string."""
        csv_content = """source,target
CA,NV
NV,AZ
AZ,UT"""
        
        theory = parser.parse(csv_content)
        assert theory.ground_terms is not None
        assert len(theory.ground_terms) == 3
        
        # Check first term
        term = theory.ground_terms[0]
        assert term.predicate == 'fact'  # Default predicate when no filename
        assert term.bindings == {'source': 'CA', 'target': 'NV'}
    
    def test_parse_ground_terms_from_string(self, parser: DataFrameParser):
        """Test parsing ground terms from CSV string."""
        csv_content = """name,age
Alice,25
Bob,30"""
        
        terms = parser.parse_ground_terms(csv_content)
        assert len(terms) == 2
        
        assert terms[0].predicate == 'fact'
        assert terms[0].bindings == {'name': 'Alice', 'age': 25}
        
        assert terms[1].predicate == 'fact'
        assert terms[1].bindings == {'name': 'Bob', 'age': 30}
    
    def test_parse_csv_file(self, parser: DataFrameParser):
        """Test parsing CSV from file with predicate name inference."""
        csv_content = """source,target
CA,NV
NV,AZ"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', prefix='Link.', delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)
        
        try:
            theory = parser.parse(temp_path)
            assert len(theory.ground_terms) == 2
            
            # Should infer 'Link' as predicate from filename
            term = theory.ground_terms[0]
            assert term.predicate == 'Link'
            assert term.bindings == {'source': 'CA', 'target': 'NV'}
            
        finally:
            temp_path.unlink()
    
    def test_parse_tsv_file(self, parser: DataFrameParser):
        """Test parsing TSV (tab-separated) file."""
        tsv_content = """name\tage\toccupation
Alice\t25\tEngineer
Bob\t30\tDoctor"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', prefix='Person.', delete=False) as f:
            f.write(tsv_content)
            temp_path = Path(f.name)
        
        try:
            terms = parser.parse_ground_terms(temp_path)
            assert len(terms) == 2
            
            assert terms[0].predicate == 'Person'
            assert terms[0].bindings == {'name': 'Alice', 'age': 25, 'occupation': 'Engineer'}
            
        finally:
            temp_path.unlink()
    
    def test_predicate_name_extraction(self, parser: DataFrameParser):
        """Test predicate name extraction from various filename patterns."""
        # Test cases: filename -> expected predicate
        test_cases = [
            ('Link.csv', 'Link'),
            ('Person.tsv', 'Person'),
            ('Complex.01.csv', 'Complex'),
            ('data.xlsx', 'data'),
            ('my_facts.json', 'my_facts'),
        ]
        
        for filename, expected_predicate in test_cases:
            path = Path(filename)
            actual_predicate = parser._extract_predicate_name(path)
            assert actual_predicate == expected_predicate
    
    def test_pandas_kwargs(self):
        """Test passing additional pandas arguments."""
        # Create parser with custom pandas options
        parser = DataFrameParser(index_col=0, dtype={'age': str})
        
        csv_content = """name,age
Alice,25
Bob,30"""
        
        # This should work despite pandas kwargs
        terms = parser.parse_ground_terms(csv_content)
        assert len(terms) == 2
        # Age should be string due to dtype specification
        assert isinstance(terms[0].bindings['age'], str)
    
    def test_empty_dataframe(self, parser: DataFrameParser):
        """Test handling of empty CSV file."""
        csv_content = "source,target\n"  # Header only, no data
        
        terms = parser.parse_ground_terms(csv_content)
        assert len(terms) == 0
    
    def test_missing_values(self, parser: DataFrameParser):
        """Test handling of missing values in CSV."""
        csv_content = """name,age,city
Alice,25,SF
Bob,,NYC
Charlie,30,"""
        
        terms = parser.parse_ground_terms(csv_content)
        assert len(terms) == 3
        
        # Bob's age should be NaN (pandas default for missing numeric)
        bob_term = terms[1]
        assert pandas.isna(bob_term.bindings['age'])
        
        # Charlie's city should be NaN
        charlie_term = terms[2]
        assert pandas.isna(charlie_term.bindings['city'])
    
    def test_validation_empty_dataframe(self, parser: DataFrameParser):
        """Test validation of empty DataFrame."""
        csv_content = "source,target\n"  # Header only
        
        validation_messages = list(parser.validate(csv_content))
        
        # Should get warnings about empty DataFrame and empty columns
        assert len(validation_messages) >= 1
        warning_messages = [msg for msg in validation_messages if msg.level == 'warning']
        assert len(warning_messages) >= 1
        
        # Should have a warning about empty DataFrame
        empty_warnings = [msg for msg in warning_messages if 'empty' in msg.message.lower()]
        assert len(empty_warnings) >= 1
    
    def test_validation_duplicate_columns(self, parser: DataFrameParser):
        """Test validation behavior with duplicate column names."""
        csv_content = """name,age,name
Alice,25,Alice2
Bob,30,Bob2"""
        
        validation_messages = list(parser.validate(csv_content))
        
        # Pandas automatically renames duplicate columns (name -> name.1)
        # So we don't expect any errors for this case
        # This test just verifies that the validation doesn't crash
        # and the parser can handle pandas' automatic renaming
        
        # Parse the terms to make sure it works
        terms = parser.parse_ground_terms(csv_content)
        assert len(terms) == 2
        
        # Should have columns: name, age, name.1
        first_term = terms[0]
        assert 'name' in first_term.bindings
        assert 'age' in first_term.bindings
        assert 'name.1' in first_term.bindings
    
    def test_validation_invalid_file(self, parser: DataFrameParser):
        """Test validation of invalid/corrupt file."""
        # Invalid CSV content
        invalid_content = "This is not CSV content at all!"
        
        validation_messages = list(parser.validate(invalid_content))
        
        # Should get error about failed parsing
        error_messages = [msg for msg in validation_messages if msg.level == 'error']
        assert len(error_messages) >= 1
    
    def test_integration_with_cli(self, parser: DataFrameParser):
        """Test that parser works with CLI-style usage."""
        # Create a temporary CSV file like CLI would use
        csv_content = """source,target,weight
A,B,1.0
B,C,2.5
C,D,0.8"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', prefix='Edge.', delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)
        
        try:
            # Test that this integrates with the existing parser infrastructure
            theory = parser.parse(temp_path)
            
            assert theory.ground_terms is not None
            assert len(theory.ground_terms) == 3
            
            # Should have inferred Edge as predicate
            for term in theory.ground_terms:
                assert term.predicate == 'Edge'
                assert 'source' in term.bindings
                assert 'target' in term.bindings
                assert 'weight' in term.bindings
                
        finally:
            temp_path.unlink()


class TestDataFrameParserFormats:
    """Test various file format support."""
    
    @pytest.fixture
    def parser(self) -> DataFrameParser:
        return DataFrameParser()
    
    def test_csv_format(self, parser: DataFrameParser):
        """Test CSV format support."""
        csv_content = "a,b\n1,2\n3,4"
        terms = parser.parse_ground_terms(csv_content)
        assert len(terms) == 2
    
    def test_tab_format(self, parser: DataFrameParser):
        """Test tab-separated format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False) as f:
            f.write("a\tb\n1\t2\n3\t4")
            temp_path = Path(f.name)
        
        try:
            terms = parser.parse_ground_terms(temp_path)
            assert len(terms) == 2
        finally:
            temp_path.unlink()
    
    @pytest.mark.skipif(not hasattr(pandas, 'read_excel'), reason="Excel support not available")
    def test_excel_format_detection(self, parser: DataFrameParser):
        """Test Excel format detection (without actually creating Excel file)."""
        # Test that the format detection logic works
        path = Path("test.xlsx")
        
        # This should not raise an error in format detection
        # (It will fail when trying to read the non-existent file, but that's expected)
        with pytest.raises((FileNotFoundError, ValueError)):
            parser._read_from_path(path)