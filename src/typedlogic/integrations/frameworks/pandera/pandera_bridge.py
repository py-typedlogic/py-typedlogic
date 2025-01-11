# from typing import Tuple, Collection, Any, List, Dict
#
# import pandera.typing as pa
#
# from typedlogic.datamodel import TermBag, Sentence, Theory
#
#
# def dataframes_to_theory(dfs: Collection[pa.DataFrame]) -> Theory:
#     """
#     Convert a collection of Pandera DataFrames to a Theory.
#
#     :param dfs:
#     :return:
#     """
#     theory = Theory()
#     return theory
#
#
# class DataFrame(pa.DataFrame, TermBag):
#     def __init__(self, *args, **kwargs):
#         if args:
#             kwargs.update(zip(self.model_fields, args, strict=False))
#         super().__init__(**kwargs)
#
#     # Use pa.DataFrame's hash implementation
#     __hash__ = pa.DataFrame.__hash__
#
#     @property
#     def _bindings(self) -> Dict[str, List[Any]]:
#         obj = self.to_dict("list")
#         if any(not isinstance(v, List) for v in obj.values()):
#             raise ValueError("Expected all values to be lists")
#         return obj
#
#     @property
#     def values(self) -> Tuple[List[Any], ...]:
#         return tuple([v for v in self._bindings.values()])
