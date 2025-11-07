# Catalog Parser

The Catalog parser orchestrates multiple sub-parsers to combine theories and facts from diverse sources into a unified logical theory. It's designed for complex scenarios where you need to merge schemas, data, and constraints from different formats and locations.

::: typedlogic.parsers.catalog_parser.CatalogParser

## Overview

A catalog file is a YAML configuration that specifies:

- **Metadata** about the dataset
- **Resources** to be parsed and combined (local files or remote URLs)  
- **Format specifications** for each resource
- **Custom headers** for URL resources

## Catalog File Format

```yaml
metadata:
  name: "My Dataset"
  description: "Combined schema and data"
  version: "1.0"
  author: "Data Team"
  tags: ["research", "validation"]

resources:
  - path: "schema.yaml"
    format: "linkml"
    type: "schema"
    description: "LinkML schema definition"
    
  - path: "data.json"  
    format: "jsonlog"
    type: "data"
    description: "Instance data"
    
  - url: "https://api.example.com/additional-data"
    format: "jsonlog"
    type: "data"
    headers:
      Authorization: "Bearer token123"
      User-Agent: "TypedLogic/1.0"
```

## Use Cases

### LinkML Schema + Data Validation

The primary use case is combining LinkML schemas with data for validation:

```yaml
metadata:
  name: "Person Dataset"
  description: "LinkML schema with validation data"

resources:
  - path: "person_schema.yaml"
    format: "linkml"
    type: "schema"
    
  - path: "people.json"
    format: "jsonlog" 
    type: "data"
```

### Multi-Format Data Integration

Combine data from various formats:

```yaml
metadata:
  name: "Research Data"
  
resources:
  - path: "participants.csv"
    format: "dataframe"
    
  - path: "constraints.py"
    format: "python"
    
  - path: "metadata.yaml"
    format: "yaml"
```

### Remote Data Sources

Include remote URLs with authentication:

```yaml
metadata:
  name: "External Dataset"
  
resources:
  - url: "https://data.gov/api/dataset.json"
    format: "jsonlog"
    headers:
      Authorization: "Bearer secret-token"
      Accept: "application/json"
```

## CLI Integration

Use catalog files directly with the CLI:

```bash
# Parse and dump combined theory
typedlogic dump dataset.catalog.yaml -t yaml

# Solve with catalog
typedlogic solve dataset.catalog.yaml --solver z3

# Convert to different formats
typedlogic dump dataset.catalog.yaml -t prolog -o combined.pl
```

## Error Handling

The catalog parser provides robust error handling:

- **Partial Success**: Continues processing even if some resources fail
- **Error Collection**: Aggregates all errors in theory annotations
- **Fail-Fast Mode**: Optionally stop on first error

```python
# Graceful error handling (default)
parser = CatalogParser(fail_fast=False)
theory = parser.parse("catalog.yaml")

# Check for errors
if hasattr(theory, '_annotations') and 'resource_errors' in theory._annotations:
    print(f"Errors occurred: {theory._annotations['resource_errors']}")

# Fail-fast mode
parser = CatalogParser(fail_fast=True)  # Raises exception on first error
```

## Advanced Features

### Theory Merging

The parser intelligently merges theories:

- **Ground Terms**: Combined from all data sources
- **Predicate Definitions**: Merged with conflict detection
- **Metadata**: Preserved in theory annotations

### Relative Path Resolution

Paths in catalog files are resolved relative to the catalog file location:

```yaml
resources:
  - path: "data/people.csv"      # Resolved relative to catalog file
  - path: "../shared/schema.yaml" # Parent directory references work
```

### URL Caching

Remote resources are fetched once per parsing session and cached in memory for efficiency.

## Resource Types

While not enforced, resources can be tagged with semantic types:

- `schema`: Schema definitions (LinkML, OWL, etc.)
- `data`: Instance data (CSV, JSON, etc.)  
- `constraints`: Additional logical rules
- `metadata`: Descriptive information

## Configuration

```python
from typedlogic.parsers.catalog_parser import CatalogParser

# Basic usage
parser = CatalogParser()
theory = parser.parse("dataset.catalog.yaml")

# With validation enabled
parser = CatalogParser(auto_validate=True)

# Fail-fast mode  
parser = CatalogParser(fail_fast=True)
```