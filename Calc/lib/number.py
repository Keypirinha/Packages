# Keypirinha: a fast launcher for Windows (keypirinha.com)

import decimal
import operator

class Number():
    """
    A flexible :py:class:`decimal.Decimal` class that allows the use of
    "integer-only" operators like `__lshift__` when the represented number is
    safely castable to an integer.
    """
    __slots__ = ("_dec")

    def __init__(self, value="0", **kwargs):
        if isinstance(value, self.__class__):
            self._dec = value._dec
            return
        elif isinstance(value, decimal.Decimal):
            self._dec = value
            return
        elif value is None:
            self._dec = decimal.Decimal(0)
            return
        elif isinstance(value, (int, float)):
            pass
        elif isinstance(value, bool):
            value = 1 if value else 0
        else:
            if isinstance(value, bytes):
                value = value.decode("utf-8")

            if isinstance(value, str):
                v = value.lstrip().lower()
                if v.startswith("0x"):
                    value = int(v, base=16)
                elif v.startswith("0b"):
                    value = int(v, base=2)
                elif v.startswith("0o"):
                    value = int(v, base=8)
            else:
                # note: decimal.Decimal supports value to be a tuple, we do not
                # need this
                raise TypeError("unknown Number input type: " + repr(value))

        self._dec = decimal.Decimal(value, **kwargs)

    def safe_int(self):
        """cast to int only if the Decimal object holds a true integer value"""
        if self._dec.is_zero():
            return 0
        elif self._dec.is_normal() or self._dec.is_subnormal():
            ratio = self._dec.as_integer_ratio()
            if ratio[1] == 1:
                return ratio[0]
            else:
                raise TypeError("Number is not an integer: " + str(self._dec))
        else:
            raise TypeError("Number is not castable to an integer: " +
                            str(self._dec))


    # This default __getattr__() implementation is unsafe here since some
    # methods may require Decimal() input object(s) and might also return
    # Decimal() object(s), which is what we are trying to avoid here.
    # So unfortunately, we are doomed to interface the base method one by one...
    #
    # def __getattr__(self, attr):
    #     return getattr(selv._dec, attr)

    def adjusted(self):
        return Number(self._dec.adjusted())

    def as_integer_ratio(self):
        return Number(self._dec.as_integer_ratio())

    def as_tuple(self):
        # CAUTION: returns a decimal.DecimalTuple named tuple
        return self._dec.as_tuple()

    def canonical(self):
        # note: "Currently, the encoding of a Decimal instance is always
        # canonical, so this operation returns its argument unchanged."
        return self

    def compare(self, other, **kwargs):
        return Number(self._dec.compare(Number(other)._dec, **kwargs))

    def compare_signal(self):
        return Number(self._dec.compare_signal(Number(other)._dec, **kwargs))

    def compare_total(self):
        return Number(self._dec.compare_total(Number(other)._dec, **kwargs))

    def compare_total_mag(self):
        return Number(self._dec.compare_total_mag(Number(other)._dec, **kwargs))

    def conjugate(self):
        return self

    def copy_abs(self):
        return Number(self._dec.copy_abs())

    def copy_negate(self):
        return Number(self._dec.copy_negate())

    def copy_sign(self, other, **kwargs):
        return Number(self._dec.copy_sign(Number(other)._dec, **kwargs))

    def exp(self, **kwargs):
        return Number(self._dec.exp(**kwargs))

    def from_float(self, f):
        return Number(self._dec.from_float(f))

    def fma(self, other, third, **kwargs):
        return Number(self._dec.fma(Number(other)._dec,
                                    Number(third)._dec,
                                    **kwargs))

    def is_canonical(self):
        return self._dec.is_canonical()

    def is_finite(self):
        return self._dec.is_finite()

    def is_infinite(self):
        return self._dec.is_infinite()

    def is_nan(self):
        return self._dec.is_nan()

    def is_normal(self, **kwargs):
        return self._dec.is_normal(**kwargs)

    def is_qnan(self):
        return self._dec.is_qnan()

    def is_signed(self):
        return self._dec.is_signed()

    def is_snan(self):
        return self._dec.is_snan()

    def is_subnormal(self, **kwargs):
        return self._dec.is_subnormal(**kwargs)

    def is_zero(self):
        return self._dec.is_zero()

    def ln(self, **kwargs):
        return Number(self._dec.ln(**kwargs))

    def log10(self, **kwargs):
        return Number(self._dec.log10(**kwargs))

    def logb(self, **kwargs):
        return Number(self._dec.logb(**kwargs))

    def next_minus(self, **kwargs):
        return Number(self._dec.next_minus(**kwargs))

    def next_plus(self, **kwargs):
        return Number(self._dec.next_plus(**kwargs))

    def next_toward(self, other, **kwargs):
        return Number(self._dec.next_toward(Number(other)._dec, **kwargs))

    def normalize(self, **kwargs):
        return Number(self._dec.normalize(**kwargs))

    def number_class(self, **kwargs):
        return self._dec.number_class(**kwargs)

    def quantize(self, exp, **kwargs):
        return Number(self._dec.quantize(Number(exp)._dec, **kwargs))

    def radix(self):
        return Number(self._dec.radix())

    def remainder_near(self, other, **kwargs):
        return Number(self._dec.remainder_near(Number(other)._dec, **kwargs))

    def sqrt(self, **kwargs):
        return Number(self._dec.sqrt(**kwargs))

    def to_eng_string(self, **kwargs):
        return self._dec.to_eng_string(**kwargs)

    def to_integral(self, **kwargs):
        return self._dec.to_integral(**kwargs)

    def to_integral_exact(self, **kwargs):
        return self._dec.to_integral_exact(**kwargs)

    def to_integral_value(self, **kwargs):
        return self._dec.to_integral_value(**kwargs)


    def __hash__(self):
        return self._dec.__hash__()

    def __repr__(self):
        rep = self._dec.__repr__()
        if rep.startswith('Decimal'):
            return "Number" + rep[7:]

    def __str__(self):
        return self._dec.__str__()

    def __format__(self, format_spec):
        return self._dec.__format__(format_spec)


    def __lt__(self, other):
        return self._dec.__lt__(Number(other)._dec)

    def __le__(self, other):
        return self._dec.__le__(Number(other)._dec)

    def __eq__(self, other):
        return self._dec.__eq__(Number(other)._dec)

    def __ne__(self, other):
        return self._dec.__ne__(Number(other)._dec)

    def __gt__(self, other):
        return self._dec.__gt__(Number(other)._dec)

    def __ge__(self, other):
        return self._dec.__ge__(Number(other)._dec)


    def __bool__(self):
        return self._dec.__bool__()

    def __complex__(self):
        return self._dec.__complex__()

    def __int__(self):
        return self._dec.__int__()

    def __float__(self):
        return self._dec.__float__()

    def __round__(self, ndigits=None):
        if ndigits is None:
            return self._dec.__round__()
        else:
            return self._dec.__round__(Number(ndigits).safe_int())

    def __index__(self):
        return self._dec.safe_int()


    def __neg__(self):
        return Number(self._dec.__neg__())

    def __pos__(self):
        return Number(self._dec.__pos__())

    def __abs__(self):
        return Number(self._dec.__abs__())


    def __add__(self, other):
        return Number(self._dec.__add__(Number(other)._dec))

    def __sub__(self, other):
        return Number(self._dec.__sub__(Number(other)._dec))

    def __mul__(self, other):
        return Number(self._dec.__mul__(Number(other)._dec))

    def __truediv__(self, other):
        return Number(self._dec.__truediv__(Number(other)._dec))

    def __floordiv__(self, other):
        return Number(self._dec.__floordiv__(Number(other)._dec))

    def __mod__(self, other):
        return Number(self._dec.__mod__(Number(other)._dec))

    def __divmod__(self, other):
        res = self._dec.__divmod__(Number(other)._dec)
        return (Number(res[0]), Number(res[1]))

    def __pow__(self, other, modulo=None):
        if modulo is None:
            return Number(self._dec.__pow__(Number(other)._dec))
        else:
            return Number(self._dec.__pow__(Number(other).safe_int(),
                                            Number(modulo).safe_int()))

    def __lshift__(self, other):
        return self.safe_int().__lshift__(Number(other).safe_int())

    def __rshift__(self, other):
        return self.safe_int().__rshift__(Number(other).safe_int())

    def __and__(self, other):
        return self.safe_int().__and__(Number(other).safe_int())

    def __xor__(self, other):
        return self.safe_int().__xor__(Number(other).safe_int())

    def __or__(self, other):
        return self.safe_int().__or__(Number(other).safe_int())


    def __radd__(self, other):
        return Number(Number(other)._dec.__add__(self._dec))

    def __rsub__(self, other):
        return Number(Number(other)._dec.__sub__(self._dec))

    def __rmul__(self, other):
        return Number(Number(other)._dec.__mul__(self._dec))

    def __rtruediv__(self, other):
        return Number(Number(other)._dec.__truediv__(self._dec))

    def __rfloordiv__(self, other):
        return Number(Number(other)._dec.__floordiv__(self._dec))

    def __rmod__(self, other):
        return Number(Number(other)._dec.__mod__(self._dec))

    def __rdivmod__(self, other):
        res = Number(other)._dec.__divmod__(self._dec)
        return (Number(res[0]), Number(res[1]))

    def __rpow__(self, other):
        return Number(Number(other)._dec.__pow__(self._dec))

    def __rlshift__(self, other):
        return Number(other).safe_int().__lshift__(self.safe_int())

    def __rrshift__(self, other):
        return Number(other).safe_int().__rshift__(self.safe_int())

    def __rand__(self, other):
        return Number(other).safe_int().__and__(self.safe_int())

    def __rxor__(self, other):
        return Number(other).safe_int().__xor__(self.safe_int())

    def __ror__(self, other):
        return Number(other).safe_int().__or__(self.safe_int())


    def __iadd__(self, other):
        return Number(self._dec.__iadd__(Number(other)._dec))

    def __isub__(self, other):
        return Number(self._dec.__isub__(Number(other)._dec))

    def __imul__(self, other):
        return Number(self._dec.__imul__(Number(other)._dec))

    def __itruediv__(self, other):
        return Number(self._dec.__itruediv__(Number(other)._dec))

    def __ifloordiv__(self, other):
        return Number(self._dec.__ifloordiv__(Number(other)._dec))

    def __imod__(self, other):
        return Number(self._dec.__imod__(Number(other)._dec))

    def __ipow__(self, other, modulo=None):
        if modulo is None:
            return Number(self._dec.__ipow__(Number(other)._dec))
        else:
            return Number(self._dec.__ipow__(Number(other).safe_int(),
                                             Number(modulo).safe_int()))

    def __ilshift__(self, other):
        res = self.safe_int().__lshift__(Number(other).safe_int())
        self._dec = decimal.Decimal(res)
        return self._dec

    def __irshift__(self, other):
        res = self.safe_int().__rshift__(Number(other).safe_int())
        self._dec = decimal.Decimal(res)
        return self._dec

    def __iand__(self, other):
        res = self.safe_int().__and__(Number(other).safe_int())
        self._dec = decimal.Decimal(res)
        return self._dec

    def __ixor__(self, other):
        res = self.safe_int().__xor__(Number(other).safe_int())
        self._dec = decimal.Decimal(res)
        return self._dec

    def __ior__(self, other):
        res = self.safe_int().__or__(Number(other).safe_int())
        self._dec = decimal.Decimal(res)
        return self._dec


if __name__ == "__main__":
    if not __debug__:
        raise Exception("debug mode not enabled")

    N = Number

    assert repr(N("1.2")) == "Number('1.2')"
    assert str(N("1.2")) == "1.2"
    assert abs(N("1.2")) == N("1.2")
    assert abs(N("-1.2")) == N("1.2")
    assert "{}".format(N("-1.2")) == "-1.2"

    assert N("0") == 0
    assert N("0") == False
    assert N("0") == .0
    assert N("0") == -.0
    assert N("0") == decimal.Decimal("-.0")
    assert not N("0")

    assert 0 == N("0")
    assert False == N("0")
    assert .0 == N("0")
    assert -.0 == N("0")
    assert decimal.Decimal("-.0") == N("0")

    assert N("-1") != 1
    assert N("-1") != 1.0
    assert N("-1") != True
    assert not not N("-1")
    assert N("-1") != False

    assert .1 != N("0")
    assert .1 > N("0")
    assert .1 >= N("0")
    assert N("0") < .1
    assert N("0") <= .1

    assert -N("1.1") == -N("1.1")
    assert -N("1.1") == N("-1.1")

    assert (N("1.1") + N(".1")) == N("1.2")
    assert (N("1.1") - N(".1")) == N("1.0")
    assert (N("1.1") * 2) == N("2.2")
    assert (N("1.1") / 2) == N(".55")
    assert (N("1.1") ** 2) == N("1.21")
    assert (N("1.0") ** N("2.3")) == 1

    assert (N("3") >> 1) == 1
    assert (N("3") << 1) == 6
    assert (N("3") & 2) == 2
    assert (N("2") | 1) == N("3")
    assert (N("2") | 0) == 2

    n = N("3")
    n >>= 1
    assert n == 1
