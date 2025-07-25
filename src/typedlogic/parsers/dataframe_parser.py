"""
DataFrame parser for CSV, TSV, and other tabular data formats.

This parser uses pandas to read tabular data files and converts them to logical facts.
It only parses ground terms (facts), not rules or axioms.

The predicate name is inferred from the filename (e.g., Link.csv -> Link predicate).
Column names become field names in the resulting terms.

Supported formats:
- CSV (comma-separated values)
- TSV (tab-separated values) 
- Excel files (.xlsx, .xls)
- Any format supported by pandas.read_csv() with appropriate parameters

Example:
    Link.csv with contents:
    ```
    source,target
    CA,NV
    NV,AZ
    ```
    
    Will produce terms:
    - Link(source='CA', target='NV')
    - Link(source='NV', target='AZ')
"""

from io import StringIO, TextIOWrapper
from pathlib import Path
from types import ModuleType
from typing import List, Optional, TextIO, Union

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

from typedlogic import Term, Theory
from typedlogic.integrations.frameworks.pandas.pandas_utils import dataframe_to_terms
from typedlogic.parser import Parser


class DataFrameParser(Parser):
    """
    A parser for tabular data files using pandas.
    
    This parser reads CSV, TSV, Excel and other tabular formats
    and converts rows to logical facts (ground terms).
    """
    
    default_suffix = "csv"
    
    def __init__(self, **pandas_kwargs):
        """
        Initialize the parser.
        
        Args:
            **pandas_kwargs: Additional keyword arguments passed to pandas read functions
        """
        super().__init__()
        if pd is None:
            raise ImportError(
                "pandas is required for DataFrameParser. "
                "Install it with: pip install pandas"
            )
        self.pandas_kwargs = pandas_kwargs
    
    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        """
        Parse tabular data into a Theory containing only ground terms.
        
        Since this parser only handles facts (not rules), it returns a Theory
        with empty sentences but populated ground_terms.
        
        Args:
            source: Path to file, file content as string, or file-like object
            **kwargs: Additional arguments passed to pandas
            
        Returns:
            Theory object with ground terms from the tabular data
        """
        ground_terms = self.parse_ground_terms(source, **kwargs)
        
        # Create a minimal theory with just the ground terms
        theory = Theory()
        theory.ground_terms = ground_terms
        return theory
    
    def parse_ground_terms(self, source: Union[Path, str, TextIO], **kwargs) -> List[Term]:
        """
        Parse tabular data and return a list of ground terms (facts).
        
        Args:
            source: Path to file, file content as string, or file-like object
            **kwargs: Additional arguments passed to pandas
            
        Returns:
            List of Term objects representing the rows as facts
        """
        # Determine predicate name from filename
        predicate_name = None
        if isinstance(source, Path):
            predicate_name = self._extract_predicate_name(source)
        elif isinstance(source, str) and not '\n' in source and not '\t' in source and not ',' in source:
            # Likely a filename string, not data content
            try:
                path = Path(source)
                if path.exists():
                    predicate_name = self._extract_predicate_name(path)
            except:
                pass
        
        # Read the data using pandas
        df = self._read_dataframe(source, **kwargs)
        
        # Convert to terms using existing utility
        if predicate_name:
            terms = dataframe_to_terms(df, predicate=predicate_name)
        else:
            # Fallback: use 'fact' as default predicate name
            terms = dataframe_to_terms(df, predicate='fact')
            
        return terms
    
    def _extract_predicate_name(self, path: Path) -> str:
        """
        Extract predicate name from file path.
        
        Takes the stem (filename without extension) and uses it as predicate name.
        Handles compound names like "Link.01" -> "Link"
        
        Args:
            path: Path object
            
        Returns:
            Predicate name extracted from filename
        """
        stem = path.stem
        # Handle cases like "Link.01.csv" -> "Link"
        return stem.split('.')[0]
    
    def _read_dataframe(self, source: Union[Path, str, TextIO], **kwargs) -> "pd.DataFrame":
        """
        Read data into a pandas DataFrame, auto-detecting format.
        
        Args:
            source: Data source
            **kwargs: Additional pandas arguments
            
        Returns:
            pandas DataFrame with the loaded data
        """
        # Merge parser-level pandas_kwargs with call-level kwargs
        read_kwargs = {**self.pandas_kwargs, **kwargs}
        
        if isinstance(source, Path):
            return self._read_from_path(source, **read_kwargs)
        elif isinstance(source, str):
            if '\n' in source or '\t' in source or ',' in source:
                # String contains data content
                return pd.read_csv(StringIO(source), **read_kwargs)
            else:
                # String is likely a file path
                return self._read_from_path(Path(source), **read_kwargs)
        elif isinstance(source, (TextIOWrapper, TextIO)):
            return pd.read_csv(source, **read_kwargs)
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")
    
    def _read_from_path(self, path: Path, **kwargs) -> "pd.DataFrame":
        """
        Read DataFrame from a file path, auto-detecting format based on extension.
        
        Args:
            path: Path to the data file
            **kwargs: Additional pandas arguments
            
        Returns:
            pandas DataFrame with the loaded data
        """
        suffix = path.suffix.lower()
        
        if suffix == '.csv':
            return pd.read_csv(path, **kwargs)
        elif suffix in ['.tsv', '.tab']:
            # Override separator for TSV files
            kwargs['sep'] = kwargs.get('sep', '\t')
            return pd.read_csv(path, **kwargs)
        elif suffix in ['.xlsx', '.xls']:
            return pd.read_excel(path, **kwargs)
        elif suffix in ['.json']:
            return pd.read_json(path, **kwargs)
        elif suffix in ['.parquet']:
            return pd.read_parquet(path, **kwargs)
        else:
            # Default to CSV reader for unknown extensions
            return pd.read_csv(path, **kwargs)
    
    def validate_iter(self, source: Union[Path, str, TextIO, ModuleType], **kwargs):
        """
        Validate the tabular data file.
        
        Checks that the file can be read by pandas and contains valid tabular data.
        
        Args:
            source: Data source to validate
            **kwargs: Additional arguments
            
        Yields:
            ValidationMessage objects for any validation issues
        """
        from typedlogic.parser import ValidationMessage
        
        # Handle ModuleType - not applicable for DataFrame parser
        if isinstance(source, ModuleType):
            yield ValidationMessage(
                message="DataFrame parser does not support Python modules",
                level="error"
            )
            return
        
        try:
            df = self._read_dataframe(source, **kwargs)
            
            # Check if DataFrame is empty
            if df.empty:
                yield ValidationMessage(
                    message="DataFrame is empty - no facts will be generated",
                    level="warning"
                )
            
            # Check for completely empty columns (all NaN)
            empty_cols = df.columns[df.isnull().all()].tolist()
            if empty_cols:
                yield ValidationMessage(
                    message=f"Columns contain only missing values: {empty_cols}",
                    level="warning"
                )
                
            # Note: pandas automatically handles duplicate columns by renaming them
            # (e.g., 'name' becomes 'name', 'name.1', 'name.2', etc.)
            # So we don't need to check for duplicates - pandas handles this gracefully
            
        except Exception as e:
            yield ValidationMessage(
                message=f"Failed to read tabular data: {str(e)}",
                level="error"
            )