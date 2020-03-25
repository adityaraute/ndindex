import operator

from numpy import ndarray

def ndindex(obj):
    if isinstance(obj, NDIndex):
        return obj

    try:
        # If operator.index() works, use that
        return Integer(obj)
    except TypeError:
        pass

    if isinstance(obj, slice):
        return Slice(obj)

    if isinstance(obj, tuple):
        return Tuple(*obj)

    raise TypeError(f"Don't know how to convert object of type {type(obj)} to an ndindex object")

class NDIndex:
    """
    Represents an index into an nd-array (i.e., a numpy array)
    """
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj.args = args
        return obj

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(map(str, self.args))})"

    def __eq__(self, other):
        return ((isinstance(other, self.__class__)
                 or isinstance(self, other.__eq__))
                and self.args == other.args)

    def __hash__(self):
        return hash(self.args)

    # TODO: Make NDIndex an abstract base class
    @property
    def raw(self):
        raise NotImplementedError

    def reduce(self, shape):
        """
        Simplify an index given that it will be applied to an array of a given shape

        Either returns a new index type, which is equivalent on arrays of
        shape `shape`, or raises IndexError if the index would give index
        error (for instance, out of bounds integer index or too many indices
        for array).
        """
        raise NotImplementedError

class Slice(NDIndex):
    """
    Represents a slice on an axis of an nd-array
    """
    def __new__(cls, start=None, stop=None, step=None):
        if isinstance(start, Slice):
            return start
        if isinstance(start, slice):
            start, stop, step = start.start, start.stop, start.step

        # Canonicalize
        if step is None:
            step = 1
        if step == 0:
            raise ValueError("slice step cannot be zero")
        if start is None and step > 0:
            start = 0

        if start is not None:
            start = operator.index(start)
        if stop is not None:
            stop = operator.index(stop)
        step = operator.index(step)

        if start is not None and stop is not None:
            r = range(start, stop, step)
            # We can reuse some of the logic built-in to range(), but we have to
            # be careful. range() only acts like a slice if the 0 <= start <= stop (or
            # visa-versa for negative step). Otherwise, slices are different
            # because of wrap-around behavior. For example, range(-3, 1)
            # represents [-3, -2, -1, 0] whereas slice(-3, 1) represents the slice
            # of elements from the third to last to the first, which is either an
            # empty slice or a single element slice depending on the shape of the
            # axis.
            if len(r) == 0 and (
                    (step > 0 and start <= stop) or
                    (step < 0 and stop <= start)):
                start, stop, step = 0, 0, 1
            # This is not correct because a slice keeps the axis whereas an
            # integer index removes it.
            # if len(r) == 1:
            #     return Integer(r[0])

        args = (start, stop, step)

        return super().__new__(cls, *args)

    @property
    def raw(self):
        return slice(*self.args)

    @property
    def start(self):
        """
        The start of the slice

        Note that this may be an integer or None.
        """
        return self.args[0]

    @property
    def stop(self):
        """
        The stop of the slice

        Note that this may be an integer or None.
        """
        return self.args[0]

    @property
    def step(self):
        """
        The step of the slice

        This will be a nonzero integer.
        """
        return self.args[0]

    def __len__(self):
        """
        __len__ gives the maximum size of an axis sliced with self

        An actual array may produce a smaller size if it is smaller than the
        bounds of the slice. For instance, [1, 2, 3][2:4] only has 1 element
        but the maximum length of the slice 2:4 is 2.
        """
        start, stop, step = self.args
        error = ValueError("Cannot determine max length of slice")
        # We reuse the logic in range.__len__. However, it is only correct if
        # the slice doesn't use wrap around (see the comment in __init__
        # above).
        if start is stop is None:
            raise error
        if step > 0:
            # start cannot be None
            if stop is None:
                if start >= 0:
                    # a[n:]. Extends to the end of the array.
                    raise error
                else:
                    # a[-n:]. From n from the end to the end. Same as
                    # range(-n, 0).
                    stop = 0
            elif start < 0 and stop >= 0:
                # a[-n:m] indexes from nth element from the end to the
                # m-1th element from the beginning.
                start, stop = 0, min(-start, stop)
            elif start >=0 and stop < 0:
                # a[n:-m]. The max length depends on the size of the array.
                raise error
        else:
            if start is None:
                if stop is None or stop >= 0:
                    # a[:m:-1] or a[::-1]. The max length depends on the size of
                    # the array
                    raise error
                else:
                    # a[:-m:-1]
                    start, stop = 0, -stop - 1
                    step = -step
            elif stop is None:
                if start >= 0:
                    # a[n::-1] (start != None by above). Same as range(n, -1, -1)
                    stop = -1
                else:
                    # a[-n::-1]. From n from the end to the beginning of the
                    # array backwards. The max length depends on the size of
                    # the array.
                    raise error
            elif start < 0 and stop >= 0:
                # a[-n:m:-1]. The max length depends on the size of the array
                raise error
            elif start >=0 and stop < 0:
                # a[n:-m:-1] indexes from the nth element backwards to the mth
                # element from the end.
                start, stop = 0, min(start+1, -stop - 1)
                step = -step

        return len(range(start, stop, step))

    def reduce(self, shape, axis=0):
        """
        Slice.reduce returns a slice where the start and stop are
        canonicalized for an array of the given shape.

        Here, canonicalized means the start and stop are not None.
        Furthermore, start is always nonnegative.

        After running slice.reduce, len() gives the true size of the axis for
        a sliced array of the given shape, and never raises ValueError.

        """
        if isinstance(shape, int):
            shape = (shape,)
        if len(shape) <= axis:
            raise IndexError("too many indices for array")

        size = shape[axis]
        start, stop, step = self.args

        # try:
        #     if len(self) == size:
        #         return self.__class__(None).reduce(shape, axis=axis)
        # except ValueError:
        #     pass
        if size == 0:
            start, stop, step = 0, 0, 1
        elif step > 0:
            # start cannot be None
            if start < 0:
                start = size + start
            if start < 0:
                start = 0

            if stop is None:
                stop = size
            elif stop < 0:
                stop = size + stop
                if stop < 0:
                    stop = 0
            else:
                stop = min(stop, size)
        else:
            if start is None:
                start = size - 1
            if stop is None:
                stop = -size - 1

            if start < 0:
                if start >= -size:
                    start = size + start
                else:
                    start, stop = 0, 0
            if start >= 0:
                start = min(size - 1, start)

            if -size <= stop < 0:
                stop += size
        return self.__class__(start, stop, step)


class Integer(NDIndex):
    """
    Represents an integer index on an axis of an nd-array
    """
    def __new__(cls, idx):
        idx = operator.index(idx)

        return super().__new__(cls, idx)

    def __index__(self):
        return self.raw

    @property
    def raw(self):
        return self.args[0]

    def __len__(self):
        return 1

    def reduce(self, shape, axis=0):
        if isinstance(shape, int):
            shape = (shape,)
        if len(shape) <= axis:
            raise IndexError("too many indices for array")

        size = shape[axis]
        if self.raw >= size or -size > self.raw < 0:
            raise IndexError(f"index {self.raw} is out of bounds for axis {axis} with size {size}")

        if self.raw < 0:
            return self.__class__(size + self.raw)

        return self

class Tuple(NDIndex):
    """
    Represents a tuple of single-axis indices

    Single axis indices are

    - Integer
    - Slice
    - ellipsis
    - Newaxis
    - IntegerArray
    - BooleanArray
    """
    def __new__(cls, *args):
        newargs = []
        for arg in args:
            if isinstance(arg, (tuple, ndarray, type(Ellipsis))):
                raise NotImplementedError(f"{type(arg)} is not yet supported")
            elif isinstance(arg, (int, Integer)):
                newargs.append(Integer(arg))
            elif isinstance(arg, (slice, Slice)):
                newargs.append(Slice(arg))
            else:
                raise TypeError(f"Unsupported index type {type(arg)}")

        if len(newargs) == 1:
            return newargs[0]

        return super().__new__(cls, *newargs)

    @property
    def raw(self):
        return tuple(i.raw for i in self.args)
