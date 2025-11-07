# Parsers

TypedLogic supports parsing from multiple input formats to create logical theories.

::: typedlogic.parser

## Available Parsers

### Core Parsers

- **[Python Parser](python.md)** - Parse Python modules with TypedLogic decorators
- **[YAML Parser](yaml.md)** - Parse YAML files containing logical specifications

### Data Parsers  

- **[DataFrame Parser](dataframe.md)** - Parse CSV, TSV, Excel files using pandas
- **[Catalog Parser](catalog.md)** - Orchestrate multiple parsers for complex datasets

### Integration Parsers

- **[OWL Python Parser](owlpy.md)** - Parse OWL ontologies expressed in Python
- **[RDF Parser](rdf.md)** - Parse RDF/Turtle files and SPARQL endpoints

## Usage

Parsers can be used directly in Python or via the CLI:

```python
from typedlogic.parsers import get_parser

# Get parser by format
parser = get_parser("dataframe")
theory = parser.parse("data.csv")

# Or use specific parser class
from typedlogic.parsers.dataframe_parser import DataFrameParser
parser = DataFrameParser()
theory = parser.parse("data.csv")
```

```bash
# Via CLI - format auto-detected
typedlogic dump data.csv -t yaml

# Or explicitly specify format  
typedlogic dump data.txt --input-format dataframe -t prolog
```