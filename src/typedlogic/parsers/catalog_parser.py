"""
Catalog parser for orchestrating multiple sub-parsers.

This parser reads catalog files that define collections of resources (schemas, data, etc.)
that should be parsed together and merged into a unified theory.

The primary use case is LinkML schemas with JSON-LD data for validation, but the catalog
format is designed to be extensible for other multi-format scenarios.

Example catalog file:
```yaml
metadata:
  name: "PersonInfo Schema + Data"
  description: "LinkML schema with validation data"
  version: "1.0"
  
resources:
  - path: "schema.yaml"
    format: "linkml"
    type: "schema"
    description: "PersonInfo schema definitions"
    
  - path: "data.jsonld" 
    format: "jsonlog"
    type: "data"
    description: "Sample person instances"
    
  - url: "https://example.com/remote-data.json"
    format: "jsonlog"
    type: "data"
    headers:
      Authorization: "Bearer token"
```

Supported resource types:
- Local file paths (relative to catalog file)
- Remote URLs with optional headers
- Any format supported by TypedLogic parsers
"""

from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, TextIO, Union
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import yaml

from typedlogic import Theory
from typedlogic.parser import Parser, ValidationMessage


class CatalogParser(Parser):
    """
    A parser for catalog files that orchestrate multiple sub-parsers.
    
    Catalog files define collections of resources (schemas, data, etc.)
    that should be parsed together and merged into a unified theory.
    """
    
    default_suffix = "catalog.yaml"
    
    def __init__(self, fail_fast: bool = False, **kwargs):
        """
        Initialize the catalog parser.
        
        Args:
            fail_fast: If True, stop on first resource error. If False, collect all errors.
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.fail_fast = fail_fast
    
    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        """
        Parse a catalog file and return a unified theory from all resources.
        
        Args:
            source: Path to catalog file, catalog content as string, or file-like object
            **kwargs: Additional arguments passed to sub-parsers
            
        Returns:
            Theory object with merged content from all resources
            
        Raises:
            ValueError: If catalog is malformed or resources cannot be loaded
        """
        # Load and parse catalog YAML
        catalog_data = self._load_catalog(source)
        
        # Determine base path for resolving relative paths
        base_path = None
        if isinstance(source, Path):
            base_path = source.parent
        elif isinstance(source, str) and not ('\n' in source or '\t' in source):
            # Likely a file path string
            try:
                base_path = Path(source).parent
            except:
                pass
        
        # Parse all resources
        theories = []
        errors = []
        
        for resource_spec in catalog_data.get('resources', []):
            try:
                theory = self._parse_resource(resource_spec, base_path, **kwargs)
                theories.append(theory)
            except Exception as e:
                error_msg = f"Failed to parse resource {resource_spec}: {str(e)}"
                errors.append(error_msg)
                if self.fail_fast:
                    raise ValueError(error_msg) from e
        
        if not theories and errors:
            # Create empty theory with error annotations if no resources succeeded
            from typedlogic.datamodel import Theory
            merged_theory = Theory()
        else:
            # Merge all successful theories
            merged_theory = self._merge_theories(theories)
        
        # Add catalog metadata to theory
        if 'metadata' in catalog_data:
            metadata = catalog_data['metadata']
            if 'name' in metadata:
                merged_theory.name = metadata['name']
            # Store full metadata in annotations
            if merged_theory._annotations is None:
                merged_theory._annotations = {}
            merged_theory._annotations['catalog_metadata'] = metadata
            if errors:
                merged_theory._annotations['resource_errors'] = errors
        
        return merged_theory
    
    def _load_catalog(self, source: Union[Path, str, TextIO]) -> Dict[str, Any]:
        """
        Load and parse catalog YAML content.
        
        Args:
            source: Catalog source
            
        Returns:
            Parsed catalog data as dictionary
            
        Raises:
            ValueError: If catalog cannot be loaded or parsed
        """
        try:
            if isinstance(source, Path):
                with source.open('r') as f:
                    return yaml.safe_load(f)
            elif isinstance(source, str):
                if '\n' in source or 'metadata:' in source or 'resources:' in source:
                    # String contains catalog content
                    return yaml.safe_load(source)
                else:
                    # String is likely a file path
                    with open(source, 'r') as f:
                        return yaml.safe_load(f)
            elif hasattr(source, 'read'):
                return yaml.safe_load(source)
            else:
                raise ValueError(f"Unsupported source type: {type(source)}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in catalog: {str(e)}") from e
        except FileNotFoundError as e:
            raise ValueError(f"Catalog file not found: {str(e)}") from e
    
    def _parse_resource(self, resource_spec: Dict[str, Any], base_path: Optional[Path], **kwargs) -> Theory:
        """
        Parse a single resource from the catalog.
        
        Args:
            resource_spec: Resource specification from catalog
            base_path: Base path for resolving relative paths
            **kwargs: Additional arguments passed to sub-parser
            
        Returns:
            Theory object from parsing the resource
            
        Raises:
            ValueError: If resource cannot be parsed
        """
        # Load resource content
        content = self._load_resource_content(resource_spec, base_path)
        
        # Determine format
        format_name = resource_spec.get('format')
        if not format_name:
            # Try to guess format from path/url
            resource_path = resource_spec.get('path') or resource_spec.get('url', '')
            if resource_path:
                format_name = self._guess_format_from_path(resource_path)
            else:
                raise ValueError("Resource must specify format or have detectable file extension")
        
        # Get appropriate parser (import here to avoid circular import)
        from typedlogic.registry import get_parser
        try:
            parser = get_parser(format_name)
        except ValueError as e:
            raise ValueError(f"Unknown format '{format_name}' for resource") from e
        
        # Parse using sub-parser
        return parser.parse(content, **kwargs)
    
    def _load_resource_content(self, resource_spec: Dict[str, Any], base_path: Optional[Path]) -> Union[Path, str]:
        """
        Load content from a resource specification.
        
        Args:
            resource_spec: Resource specification with path or url
            base_path: Base path for resolving relative paths
            
        Returns:
            Content ready for sub-parser (Path for local files, str for URL content)
            
        Raises:
            ValueError: If resource cannot be loaded
        """
        if 'path' in resource_spec:
            # Local file path
            path_str = resource_spec['path']
            if base_path:
                path = base_path / path_str
            else:
                path = Path(path_str)
            
            if not path.exists():
                raise ValueError(f"Resource file not found: {path}")
            
            return path
            
        elif 'url' in resource_spec:
            # Remote URL
            url = resource_spec['url']
            headers = resource_spec.get('headers', {})
            
            try:
                request = Request(url)
                for key, value in headers.items():
                    request.add_header(key, value)
                
                with urlopen(request) as response:
                    content = response.read().decode('utf-8')
                    return content
                    
            except (URLError, HTTPError) as e:
                raise ValueError(f"Failed to load URL {url}: {str(e)}") from e
        
        else:
            raise ValueError("Resource must specify either 'path' or 'url'")
    
    def _guess_format_from_path(self, path_str: str) -> str:
        """
        Guess format from file path or URL.
        
        Args:
            path_str: File path or URL
            
        Returns:
            Guessed format name
        """
        # Extract extension
        path = Path(path_str)
        suffix = path.suffix.lower()
        
        # Map extensions to formats
        format_map = {
            '.py': 'python',
            '.yaml': 'yaml',
            '.yml': 'yaml', 
            '.json': 'jsonlog',
            '.jsonld': 'jsonlog',
            '.csv': 'dataframe',
            '.tsv': 'dataframe',
            '.xlsx': 'dataframe',
            '.xls': 'dataframe',
            '.pl': 'prolog',
            '.pro': 'prolog',
            '.owl': 'owl',
            '.rdf': 'rdf',
            '.ttl': 'rdf',
        }
        
        return format_map.get(suffix, 'yaml')  # Default to yaml
    
    def _merge_theories(self, theories: List[Theory]) -> Theory:
        """
        Merge multiple theories into a single unified theory.
        
        Based on the CLI _combine_input_files logic but adapted for Theory objects.
        
        Args:
            theories: List of Theory objects to merge
            
        Returns:
            Merged Theory object
        """
        if not theories:
            return Theory()
        
        if len(theories) == 1:
            return theories[0]
        
        # Start with first theory
        merged = Theory()
        if theories[0].name:
            merged.name = theories[0].name
        
        # Merge all theories
        for theory in theories:
            # Merge sentences (axioms and rules)
            if hasattr(theory, 'sentences') and theory.sentences:
                if merged.sentences is None:
                    merged.sentences = []
                merged.sentences.extend(theory.sentences)
            
            # Merge sentence groups
            if hasattr(theory, 'sentence_groups') and theory.sentence_groups:
                if merged.sentence_groups is None:
                    merged.sentence_groups = []
                merged.sentence_groups.extend(theory.sentence_groups)
            
            # Merge ground terms (facts)
            if hasattr(theory, 'ground_terms') and theory.ground_terms:
                if merged.ground_terms is None:
                    merged.ground_terms = []
                merged.ground_terms.extend(theory.ground_terms)
            
            # Merge predicate definitions (avoid duplicates)
            if hasattr(theory, 'predicate_definitions') and theory.predicate_definitions:
                if merged.predicate_definitions is None:
                    merged.predicate_definitions = []
                
                # Track existing predicates to avoid duplicates
                existing_names = {pd.predicate for pd in merged.predicate_definitions}
                for pd in theory.predicate_definitions:
                    if pd.predicate not in existing_names:
                        merged.predicate_definitions.append(pd)
                        existing_names.add(pd.predicate)
            
            # Merge constants
            if hasattr(theory, 'constants') and theory.constants:
                if merged.constants is None:
                    merged.constants = {}
                merged.constants.update(theory.constants)
            
            # Merge type definitions
            if hasattr(theory, 'type_definitions') and theory.type_definitions:
                if merged.type_definitions is None:
                    merged.type_definitions = {}
                merged.type_definitions.update(theory.type_definitions)
        
        return merged
    
    def validate_iter(self, source: Union[Path, str, TextIO, ModuleType], **kwargs):
        """
        Validate a catalog file and its resources.
        
        Args:
            source: Catalog source to validate
            **kwargs: Additional arguments
            
        Yields:
            ValidationMessage objects for any validation issues
        """
        from typedlogic.parser import ValidationMessage
        
        # Handle ModuleType - not applicable for catalog parser
        if isinstance(source, ModuleType):
            yield ValidationMessage(
                message="Catalog parser does not support Python modules",
                level="error"
            )
            return
        
        try:
            # Load catalog
            catalog_data = self._load_catalog(source)
            
            # Validate required structure
            if 'resources' not in catalog_data:
                yield ValidationMessage(
                    message="Catalog must contain 'resources' section",
                    level="error"
                )
                return
            
            if not isinstance(catalog_data['resources'], list):
                yield ValidationMessage(
                    message="'resources' must be a list",
                    level="error"
                )
                return
            
            if not catalog_data['resources']:
                yield ValidationMessage(
                    message="Catalog contains no resources",
                    level="warning"
                )
            
            # Validate metadata section
            if 'metadata' in catalog_data:
                metadata = catalog_data['metadata']
                if not isinstance(metadata, dict):
                    yield ValidationMessage(
                        message="'metadata' must be a dictionary",
                        level="error"
                    )
                else:
                    # Validate recommended metadata fields
                    if 'name' not in metadata:
                        yield ValidationMessage(
                            message="Metadata should include 'name' field",
                            level="warning"
                        )
            
            # Determine base path
            base_path = None
            if isinstance(source, Path):
                base_path = source.parent
            elif isinstance(source, str) and not ('\n' in source or '\t' in source):
                try:
                    base_path = Path(source).parent
                except:
                    pass
            
            # Validate each resource
            for i, resource_spec in enumerate(catalog_data['resources']):
                if not isinstance(resource_spec, dict):
                    yield ValidationMessage(
                        message=f"Resource {i} must be a dictionary",
                        level="error"
                    )
                    continue
                
                # Check required fields
                if 'path' not in resource_spec and 'url' not in resource_spec:
                    yield ValidationMessage(
                        message=f"Resource {i} must specify either 'path' or 'url'",
                        level="error"
                    )
                    continue
                
                if 'path' in resource_spec and 'url' in resource_spec:
                    yield ValidationMessage(
                        message=f"Resource {i} cannot specify both 'path' and 'url'",
                        level="error"
                    )
                    continue
                
                # Validate format
                format_name = resource_spec.get('format')
                if format_name:
                    try:
                        from typedlogic.registry import get_parser
                        get_parser(format_name)
                    except ValueError:
                        yield ValidationMessage(
                            message=f"Resource {i} specifies unknown format '{format_name}'",
                            level="error"
                        )
                
                # Check resource accessibility
                try:
                    if 'path' in resource_spec:
                        path_str = resource_spec['path']
                        if base_path:
                            path = base_path / path_str
                        else:
                            path = Path(path_str)
                        
                        if not path.exists():
                            yield ValidationMessage(
                                message=f"Resource {i} file not found: {path}",
                                level="error"
                            )
                    
                    elif 'url' in resource_spec:
                        # For URLs, we could optionally check accessibility
                        # but this might be slow and require network access
                        url = resource_spec['url']
                        if not (url.startswith('http://') or url.startswith('https://')):
                            yield ValidationMessage(
                                message=f"Resource {i} URL should use http:// or https://",
                                level="warning"
                            )
                
                except Exception as e:
                    yield ValidationMessage(
                        message=f"Resource {i} validation error: {str(e)}",
                        level="warning"
                    )
        
        except Exception as e:
            yield ValidationMessage(
                message=f"Failed to validate catalog: {str(e)}",
                level="error"
            )