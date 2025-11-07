# DataFrame Parser

The DataFrame parser allows you to parse structured data from CSV, TSV, Excel, and other tabular formats into TypedLogic theories. It uses pandas for data loading and automatically infers predicate names from filenames.

::: typedlogic.parsers.dataframe_parser.DataFrameParser

## Usage Examples

### Basic CSV Parsing

```python
from typedlogic.parsers.dataframe_parser import DataFrameParser

parser = DataFrameParser()

# Parse CSV file - predicate name inferred from filename
theory = parser.parse("people.csv")  # Creates predicates like people(name, age, city)

# Parse with explicit predicate name
terms = parser.parse_ground_terms("data.csv", predicate="person")
```

### Supported Formats

The DataFrame parser automatically detects and handles:

- **CSV files** (`.csv`)
- **TSV files** (`.tsv`, `.tab`)
- **Excel files** (`.xlsx`, `.xls`)

### Predicate Name Inference

The parser automatically infers predicate names from filenames:

- `people.csv` → `people(...)` predicates
- `Link.csv` → `Link(...)` predicates  
- `data.tsv` → `data(...)` predicates

### Integration with CLI

The DataFrame parser is automatically used when processing CSV/TSV files via the CLI:

```bash
# Convert CSV to other formats
typedlogic dump people.csv -t yaml

# Combine multiple CSV files
typedlogic dump people.csv companies.csv -t prolog

# Use in catalog files
typedlogic dump my_dataset.catalog.yaml
```

## Configuration

The parser accepts standard pandas parameters for customization:

```python
# Custom separator and headers
terms = parser.parse_ground_terms("data.txt", sep="|", header=0)

# Skip rows and handle missing values
terms = parser.parse_ground_terms("messy_data.csv", skiprows=2, na_values=["N/A"])
```