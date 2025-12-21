"""
Tests for the composable Gen class.

These tests verify both the runtime behavior of Gen (for practical use cases)
and ensure the type tracking works correctly for AST parsing.
"""
from typedlogic.generators import Gen, gen_const, gen_list, gen_product, gen_range


class TestGenBasic:
    """Test basic Gen functionality."""

    def test_gen_with_type(self):
        """Test creating a Gen with a type."""
        g = Gen(int)
        assert g.types == (int,)
        assert repr(g) == "Gen(int)"

    def test_gen_with_callable(self):
        """Test creating a Gen with a factory function."""
        g = Gen(lambda: iter([1, 2, 3]))
        result = list(g)
        assert result == [1, 2, 3]

    def test_gen_iteration(self):
        """Test that Gen is iterable."""
        g = gen_range(0, 5)
        result = list(g)
        assert result == [0, 1, 2, 3, 4]


class TestGenComposition:
    """Test Gen composition with operators."""

    def test_mul_two_gens(self):
        """Test cartesian product with * operator."""
        g1 = gen_range(1, 3)
        g2 = gen_range(10, 12)
        combined = g1 * g2

        result = list(combined)
        expected = [(1, 10), (1, 11), (2, 10), (2, 11)]
        assert result == expected

    def test_mul_three_gens_flat(self):
        """Test that chained * produces flat tuples."""
        g1 = gen_range(1, 2)  # [1]
        g2 = gen_range(10, 11)  # [10]
        g3 = gen_range(100, 101)  # [100]
        combined = g1 * g2 * g3

        result = list(combined)
        assert result == [(1, 10, 100)]

    def test_mul_preserves_types(self):
        """Test that * preserves type information."""
        g1 = Gen(int)
        g2 = Gen(str)
        g3 = Gen(float)
        combined = g1 * g2 * g3

        assert combined.types == (int, str, float)

    def test_add_interleave(self):
        """Test interleaving with + operator."""
        g1 = gen_range(1, 4)  # 1, 2, 3
        g2 = gen_range(10, 13)  # 10, 11, 12
        combined = g1 + g2

        result = list(combined)
        assert result == [1, 10, 2, 11, 3, 12]

    def test_add_unequal_lengths(self):
        """Test interleaving with different length generators."""
        g1 = gen_range(1, 3)  # 1, 2
        g2 = gen_range(10, 14)  # 10, 11, 12, 13
        combined = g1 + g2

        result = list(combined)
        assert result == [1, 10, 2, 11, 12, 13]


class TestGenTransformations:
    """Test Gen transformation methods."""

    def test_map(self):
        """Test mapping a function over Gen elements."""
        g = gen_range(1, 4)
        mapped = g.map(lambda x: x * 2)

        result = list(mapped)
        assert result == [2, 4, 6]

    def test_filter(self):
        """Test filtering Gen elements."""
        g = gen_range(1, 10)
        filtered = g.filter(lambda x: x % 2 == 0)

        result = list(filtered)
        assert result == [2, 4, 6, 8]

    def test_take(self):
        """Test taking first n elements."""
        g = gen_range(0, 100)
        taken = g.take(5)

        result = list(taken)
        assert result == [0, 1, 2, 3, 4]

    def test_chained_transformations(self):
        """Test chaining multiple transformations."""
        g = gen_range(1, 20)
        result = list(g.filter(lambda x: x % 2 == 0).map(lambda x: x * 10).take(3))

        assert result == [20, 40, 60]


class TestHelperFunctions:
    """Test helper generator functions."""

    def test_gen_range(self):
        """Test gen_range helper."""
        g = gen_range(5, 10)
        result = list(g)
        assert result == [5, 6, 7, 8, 9]

    def test_gen_list(self):
        """Test gen_list helper with finite iteration."""
        g = gen_list([1, 2, 3])
        result = list(g.take(7))
        assert result == [1, 2, 3, 1, 2, 3, 1]

    def test_gen_list_empty(self):
        """Test gen_list with empty list."""
        g = gen_list([])
        result = list(g)
        assert result == []

    def test_gen_const(self):
        """Test gen_const helper."""
        g = gen_const(42)
        result = list(g.take(5))
        assert result == [42, 42, 42, 42, 42]

    def test_gen_product(self):
        """Test gen_product helper."""
        g = gen_product(gen_range(1, 2), gen_range(10, 11), gen_range(100, 101))
        result = list(g)
        assert result == [(1, 10, 100)]

    def test_gen_product_empty(self):
        """Test gen_product with no arguments."""
        g = gen_product()
        result = list(g)
        assert result == [()]

    def test_gen_product_types_preserved(self):
        """Test that gen_product preserves type information."""
        g = gen_product(Gen(int), Gen(str), Gen(float))
        assert g.types == (int, str, float)


class TestGenRepr:
    """Test Gen string representation."""

    def test_repr_single_type(self):
        """Test repr with single type."""
        g = Gen(int)
        assert repr(g) == "Gen(int)"

    def test_repr_multiple_types(self):
        """Test repr with composed types."""
        g = Gen(int) * Gen(str) * Gen(float)
        assert repr(g) == "Gen(int, str, float)"

    def test_repr_factory(self):
        """Test repr with factory function."""
        g = Gen(lambda: iter([1, 2, 3]))
        assert repr(g) == "Gen(<factory>)"
