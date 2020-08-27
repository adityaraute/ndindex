from numpy import arange, prod

from hypothesis import given
from hypothesis.strategies import integers, one_of

from ..ndindex import ndindex
from ..array import ArrayIndex
from ..booleanarray import BooleanArray
from ..integerarray import IntegerArray
from ..integer import Integer
from ..tuple import Tuple
from .helpers import ndindices, check_same, short_shapes

@given(ndindices, one_of(short_shapes, integers(0, 10)))
def test_broadcast_arrays_hypothesis(idx, shape):
    if isinstance(shape, int):
        a = arange(shape)
    else:
        a = arange(prod(shape)).reshape(shape)

    index = ndindex(idx)

    # It is possible for the original index to give an IndexError, but for
    # broadcast_arrays() may return an index that doesn't (but the other way
    # around should not happen).
    check = True
    try:
        a[index.raw]
    except IndexError as e:
        if "boolean index did not match indexed array" in e.args[0]:
            check = False
        if index.isempty() and "out of bounds" in e.args[0]:
            # Integers are bounds checked even when the resulting index
            # broadcasts to empty (but not so for IntegerArray).
            check = False
    except DeprecationWarning as w:
        if "Out of bound index found. This was previously ignored when the indexing result contained no elements. In the future the index error will be raised. This error occurs either due to an empty slice, or if an array has zero elements even before indexing." in w.args[0]:
            pass
        else:
            raise
    if check:
        check_same(a, index.raw, ndindex_func=lambda a, x:
                   a[x.broadcast_arrays().raw], same_exception=False)

    broadcasted = index.broadcast_arrays()

    if isinstance(index, (Tuple, BooleanArray)):
        assert isinstance(broadcasted, Tuple)
    else:
        assert broadcasted == index

    if isinstance(broadcasted, Tuple):
        arrays = [arg for arg in broadcasted.args if isinstance(arg,
                                                                ArrayIndex)
                  and arg not in [True, False]]
        if arrays:
            assert len(set([i.shape for i in arrays])) == 1
            assert not any(isinstance(i, Integer) for i in broadcasted.args)
            assert all(isinstance(i, IntegerArray) or i in [True, False] for
                       i in arrays)

        assert broadcasted.args.count(True) <= 1
        assert broadcasted.args.count(False) <= 1
        assert not (True in broadcasted.args and False in broadcasted.args)
        if True in broadcasted.args or False in broadcasted.args:
            assert index in [True, False] or True in index.args or False in index.args
    elif index in [True, False]:
        assert broadcasted == Tuple(index)
    elif isinstance(idx, BooleanArray):
        assert all(isinstance(i, IntegerArray) for i in broadcasted.args)
