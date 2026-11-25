import pytest
from typedlogic.parsers.yaml_parser import YAMLParser

from tests import TEST_THEOREMS_DIR


@pytest.fixture
def parser() -> YAMLParser:
    return YAMLParser()


@pytest.mark.parametrize(
    "data_path,expected",
    [
        (TEST_THEOREMS_DIR / "paths_data" / "Link.01.yaml", ["Link(a, b)", "Link(b, c)", "Link(c, d)"]),
        (TEST_THEOREMS_DIR / "paths_data" / "test.02.yaml", ["Link(a, b)"]),
        (TEST_THEOREMS_DIR / "paths_data" / "test.03.yaml", ["Link(a, b)"]),
    ],
)
def test_parse_data(parser, data_path, expected):
    terms = parser.parse_ground_terms(data_path)
    terms_flat = [str(t) for t in terms]
    assert terms_flat == expected


def test_parse_from_text_stream_and_path(tmp_path):
    """Any text stream is accepted, and ground-term files take their predicate from the file name."""
    import io

    from typedlogic import Term, Theory
    from typedlogic.parsers.yaml_parser import YAMLParser

    parser = YAMLParser()
    assert isinstance(parser.parse(io.StringIO("type: Theory\nname: t\n")), Theory)
    path = tmp_path / "Link.01.yaml"
    path.write_text("- [a, b]\n- {source: b, target: c}\n")
    assert parser.parse_ground_terms(path) == [Term("Link", "a", "b"), Term("Link", "b", "c")]
