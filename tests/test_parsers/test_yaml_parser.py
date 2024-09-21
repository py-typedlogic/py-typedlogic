import pytest

from tests import TEST_THEOREMS_DIR
from typedlogic.parsers.yaml_parser import YAMLParser


@pytest.fixture
def parser() -> YAMLParser:
    return YAMLParser()

@pytest.mark.parametrize("data_path,expected",
    [(TEST_THEOREMS_DIR / "paths_data" / "Link.01.yaml", ['Link(a, b)', 'Link(b, c)', 'Link(c, d)']),
     (TEST_THEOREMS_DIR / "paths_data" / "test.02.yaml", ['Link(a, b)']),
     (TEST_THEOREMS_DIR / "paths_data" / "test.03.yaml", ['Link(a, b)']),
])
def test_parse_data(parser, data_path, expected):
    terms = parser.parse_ground_terms(data_path)
    terms_flat = [str(t) for t in terms]
    assert terms_flat == expected
