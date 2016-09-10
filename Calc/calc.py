# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_wintypes as kpwt
import io
import ast
import tokenize
import math
import decimal
import random
import traceback
from .lib import simpleeval

class Number2Decimal(): # Python rocks
    def __init__(self, func):
        self.func = func
    def __call__(self, *args, **kwargs):
        result = self.func(*args, **kwargs)
        if isinstance(result, int):
            return decimal.Decimal(result)
        elif isinstance(result, float):
            return decimal.Decimal(result)
        elif isinstance(result, str) and "." in result:
            return decimal.Decimal(result)
        elif isinstance(result, bytes) and b'.' in result:
            return decimal.Decimal(result.decode("utf-8"))
        else:
            return result

class Calc(kp.Plugin):
    """
    Inline calculator.

    Evaluates a mathematical expression and shows its result.
    """

    DEFAULT_KEYWORD = "="
    DEFAULT_ALWAYS_EVALUATE = True
    DEFAULT_ROUNDING_PRECISION = 5
    DEFAULT_CURRENCY_MODE = "float"
    DEFAULT_CURRENCY_FORMAT = "system"
    DEFAULT_CURRENCY_DECIMALSEP = "."
    DEFAULT_CURRENCY_THOUSANDSEP = ","
    DEFAULT_CURRENCY_PLACES = 2

    MATH_OPERATORS = simpleeval.DEFAULT_OPERATORS

    MATH_CONSTANTS = {
        'pi': decimal.Decimal(math.pi),
        'e': decimal.Decimal(math.e),
        'inf': decimal.Decimal(math.inf),
        'nan': decimal.Decimal(math.nan),
        'ans': 0, # replaced by self.ans at runtime
    }

    MATH_FUNCTIONS = {
        'abs': Number2Decimal(abs),
        'bin': bin,
        'bool': bool,
        'chr': chr,
        'divmod': divmod,
        'float': Number2Decimal(float),
        'hex': hex,
        'int': Number2Decimal(int),
        'len': Number2Decimal(len),
        'min': Number2Decimal(min),
        'max': Number2Decimal(max),
        'oct': oct,
        'ord': ord,
        'pow': Number2Decimal(pow),
        'round': Number2Decimal(round),
        'str': Number2Decimal(str),

        'rand': Number2Decimal(simpleeval.random_int),
        'rand1': Number2Decimal(random.random), # returns [0.0, 1.0)
        'randf': Number2Decimal(random.uniform), # random.uniform(a, b): Return a random floating point number N such that a <= N <= b for a <= b and b <= N <= a for b < a
        'randi': Number2Decimal(random.randint), # returns N where: a <= N <= b

        'acos': Number2Decimal(math.acos),
        'acosh': Number2Decimal(math.acosh),
        'asin': Number2Decimal(math.asin),
        'asinh': Number2Decimal(math.asinh),
        'atan': Number2Decimal(math.atan),
        'atan2': Number2Decimal(math.atan2),
        'atanh': Number2Decimal(math.atanh),
        'ceil': Number2Decimal(math.ceil),
        'cos': Number2Decimal(math.cos),
        'cosh': Number2Decimal(math.cosh),
        'deg': Number2Decimal(math.degrees),
        'exp': Number2Decimal(math.exp),
        'factor': Number2Decimal(math.factorial),
        'floor': Number2Decimal(math.floor),
        'gcd': Number2Decimal(math.gcd),
        'hypot': Number2Decimal(math.hypot),
        'log': Number2Decimal(math.log),
        'rad': Number2Decimal(math.radians),
        'sin': Number2Decimal(math.sin),
        'sinh': Number2Decimal(math.sinh),
        'sqrt': Number2Decimal(math.sqrt),
        'tan': Number2Decimal(math.tan),
        'tanh': Number2Decimal(math.tanh),

        # undocumented
        'Decimal': decimal.Decimal, # see _retokenize()
    }

    TOKENSMAP_OPERATORS = {
        tokenize.CIRCUMFLEX: "**", # '^' (BitXor) will be replaced by DOUBLESTAR (Pow)
        tokenize.TILDE: "^",       # '~' (Invert) will be replaced by CIRCUMFLEX (BitXor)
    }

    TOKENSMAP_NAME_OPERATORS = {
        'or':  "|", # VBAR (BitOr)
        'xor': "^", # CIRCUMFLEX (BitXor)
        'and': "&", # AMPER (BitAnd)
    }

    TOKENSMAP_NUMBER_SUFFIXES = {
        # https://en.wikipedia.org/wiki/Metric_prefix
        # https://en.wikipedia.org/wiki/Hecto-
        'y':  lambda n: decimal.Decimal(n) / 1000 ** 8, # yocto
        'z':  lambda n: decimal.Decimal(n) / 1000 ** 7, # zepto
        'a':  lambda n: decimal.Decimal(n) / 1000 ** 6, # atto
        'f':  lambda n: decimal.Decimal(n) / 1000 ** 5, # femto
        'p':  lambda n: decimal.Decimal(n) / 1000 ** 4, # pico
        'n':  lambda n: decimal.Decimal(n) / 1000 ** 3, # nano
        'u':  lambda n: decimal.Decimal(n) / 1000 ** 2, # micro
        'm':  lambda n: decimal.Decimal(n) / 1000,      # milli
        'c':  lambda n: decimal.Decimal(n) / 100,       # centi
        'd':  lambda n: decimal.Decimal(n) / 10,        # deci
        'da': lambda n:                  n * 10,        # deca
        'h':  lambda n:                  n * 100,       # hecto
        'k':  lambda n:                  n * 1000,      # Kilo
        'M':  lambda n:                  n * 1000 ** 2, # Mega
        'G':  lambda n:                  n * 1000 ** 3, # Giga
        'T':  lambda n:                  n * 1000 ** 4, # Tera
        'P':  lambda n:                  n * 1000 ** 5, # Peta
        'E':  lambda n:                  n * 1000 ** 6, # Exa
        'Z':  lambda n:                  n * 1000 ** 7, # Zetta
        'Y':  lambda n:                  n * 1000 ** 8, # Yotta

        # https://en.wikipedia.org/wiki/Orders_of_magnitude_(data)
        # https://en.wikipedia.org/wiki/Kibibyte
        'Ki': lambda n: n * 1024,      # Kibi
        'Mi': lambda n: n * 1024 ** 2, # Mebi
        'Gi': lambda n: n * 1024 ** 3, # Gibi
        'Ti': lambda n: n * 1024 ** 4, # Tebi
        'Pi': lambda n: n * 1024 ** 5, # Pebi
        'Ei': lambda n: n * 1024 ** 6, # Exbi
        'Zi': lambda n: n * 1024 ** 7, # Zebi
        'Yi': lambda n: n * 1024 ** 8, # Yobi
    }

    always_evaluate = DEFAULT_ALWAYS_EVALUATE
    transmap_input = ""
    transmap_output = ""
    rounding_precision = DEFAULT_ROUNDING_PRECISION
    currency_enabled = True
    currency_float_only = True
    currency_from_system = True
    currency_decsep = DEFAULT_CURRENCY_DECIMALSEP
    currency_thousandsep = DEFAULT_CURRENCY_THOUSANDSEP
    currency_places = DEFAULT_CURRENCY_PLACES

    ans = 0

    def __init__(self):
        super().__init__()

        # add support for bitwise operators
        if ast.LShift not in self.MATH_OPERATORS: # '<<'
            self.MATH_OPERATORS[ast.LShift] = simpleeval.op.lshift
        if ast.RShift not in self.MATH_OPERATORS: # '>>'
            self.MATH_OPERATORS[ast.RShift] = simpleeval.op.rshift
        if ast.BitOr not in self.MATH_OPERATORS: # '|'
            self.MATH_OPERATORS[ast.BitOr] = simpleeval.op.or_
        if ast.BitXor not in self.MATH_OPERATORS: # '^'
            self.MATH_OPERATORS[ast.BitXor] = simpleeval.op.xor
        if ast.BitAnd not in self.MATH_OPERATORS: # '&'
            self.MATH_OPERATORS[ast.BitAnd] = simpleeval.op.and_

        # add support for extra operators
        #if ast.Not not in self.MATH_OPERATORS: # not ('not')
        #    self.MATH_OPERATORS[ast.Not] = simpleeval.op.not_
        if ast.FloorDiv not in self.MATH_OPERATORS: # floordiv ('//')
            self.MATH_OPERATORS[ast.FloorDiv] = simpleeval.op.floordiv

    def on_start(self):
        self._read_config()

    def on_catalog(self):
        self.set_catalog([self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label=self.DEFAULT_KEYWORD,
            short_desc="Evaluate a mathematical expression",
            target=self.DEFAULT_KEYWORD,
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS)])

    def on_suggest(self, user_input, items_chain):
        if not len(user_input):
            return
        if items_chain and (
                items_chain[0].category() != kp.ItemCategory.KEYWORD or
                items_chain[0].target() != self.DEFAULT_KEYWORD):
            return

        eval_requested = False
        if user_input.startswith(self.DEFAULT_KEYWORD):
            # always evaluate if expression is prefixed by DEFAULT_KEYWORD
            user_input = user_input[1:].strip()
            if not len(user_input):
                return
            eval_requested = True
        elif items_chain:
            eval_requested = True
        elif not items_chain and not self.always_evaluate:
            return

        suggestions = []
        try:
            results = self._eval(user_input)
            if not isinstance(results, (tuple, list)):
                results = (results,)
            for res in results:
                res = str(res)
                suggestions.append(self.create_item(
                    category=kp.ItemCategory.EXPRESSION,
                    label="= " + res if not items_chain else res,
                    short_desc="Press Enter to copy the result",
                    target=res,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE))
        except Exception as e:
            if not eval_requested:
                return # stay quiet if evaluation hasn't been explicitly requested
            suggestions.append(self.create_error_item(
                label=user_input,
                short_desc="Error: " + str(e)))

        self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if item and item.category() == kp.ItemCategory.EXPRESSION:
            kpu.set_clipboard(item.target())

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()

    def _read_config(self):
        settings = self.load_settings()

        # [main] always_evaluate
        self.always_evaluate = settings.get_bool(
            "always_evaluate", "main", self.DEFAULT_ALWAYS_EVALUATE)

        # [main] decimal_separator
        DEFAULT_DECIMAL_SEPARATOR = "dot"
        decimal_separator = settings.get_enum(
            "decimal_separator", "main",
            fallback=DEFAULT_DECIMAL_SEPARATOR,
            enum=["dot", "comma", "auto"])
        if decimal_separator == "auto":
            decimal_separator = DEFAULT_DECIMAL_SEPARATOR
            try:
                # use the GetLocaleInfoEx windows api to get the decimal
                # separator configured by system's user
                GetLocaleInfoEx = kpwt.declare_func(
                    kpwt.kernel32, "GetLocaleInfoEx", ret=kpwt.ct.c_int,
                    arg=[kpwt.LPCWSTR, kpwt.DWORD, kpwt.PWSTR, kpwt.ct.c_int])
                LOCALE_SDECIMAL = 0x0000000E
                buf = kpwt.ct.create_unicode_buffer(10)
                res = GetLocaleInfoEx(None, LOCALE_SDECIMAL, buf, len(buf))
                if res == 2 and len(buf.value) == res - 1 and buf.value == ",":
                    decimal_separator = "comma"
            except:
                self.warn(
                    "Failed to get system user decimal separator value. " +
                    "Falling back to default (" + decimal_separator + ")...")
                traceback.print_exc()
            self.info("Using \"{}\" as a decimal separator".format(decimal_separator))
        if decimal_separator == "comma":
            self.transmap_input = str.maketrans(",;", ".,")
            self.transmap_output = str.maketrans(".", ",")
        else:
            self.transmap_input = ""
            self.transmap_output = ""

        # [main] rounding_precision
        if not settings.has("rounding_precision", "main"):
            self.rounding_precision = self.DEFAULT_ROUNDING_PRECISION
        elif None == settings.get_stripped("rounding_precision", "main", fallback=None):
            self.rounding_precision = None # None means "feature disabled"
        else:
            self.rounding_precision = settings.get_int(
                "rounding_precision", "main",
                fallback=self.DEFAULT_ROUNDING_PRECISION,
                min=0, max=16)
            self.rounding_precision += 1

        # [currency] mode
        cfgval = settings.get_enum(
            "mode", "currency",
            fallback=self.DEFAULT_CURRENCY_MODE,
            enum=["on", "float", "off"])
        if cfgval == "off":
            self.currency_enabled = False
            self.currency_float_only = True
        else:
            self.currency_enabled = True
            self.currency_float_only = True if cfgval == "float" else False

        # [currency] format
        cfgval = settings.get_enum(
            "format", "currency",
            fallback=self.DEFAULT_CURRENCY_FORMAT,
            enum=["system", "manual"])
        self.currency_from_system = False if cfgval == "manual" else True

        # [currency] decimal_separator
        self.currency_decsep = settings.get_stripped(
            "decimal_separator", "currency",
            fallback=self.DEFAULT_CURRENCY_DECIMALSEP)
        if len(self.currency_decsep) == 0 or len(self.currency_decsep) > 4:
            self.currency_decsep = self.DEFAULT_CURRENCY_DECIMALSEP

        # [currency] thousand_separator
        self.currency_thousandsep = settings.get(
            "thousand_separator", "currency",
            fallback=self.DEFAULT_CURRENCY_THOUSANDSEP,
            unquote=True)
        if len(self.currency_thousandsep) > 4:
            self.currency_thousandsep = self.DEFAULT_CURRENCY_THOUSANDSEP

        # [currency] places
        self.currency_places = settings.get_int(
            "places", "currency",
            fallback=self.DEFAULT_CURRENCY_PLACES,
            min=0, max=5)

    def _eval(self, expr):
        # We have no other choice here than doing ugly and basic string
        # replacements to apply separator settings (i.e. decimal and list/args
        # separators).
        # This is because in Python, "," and "." operators don't have the same
        # meaning so even if we replace them after having parsed the expression
        # using the "tokenizer" module, the "2,3" expression for example will be
        # parsed as ("2", ",", "3") instead of the representation of the ("2,3")
        # floating point number, which was the initial meaning here from user's
        # stand point.
        # The powerful "ast" module won't help neither here because even if it
        # manages to parse it properly the opportunity we'll have then to
        # replace tokens will be too late in the lexer-parser-compiler chain.
        expr = expr.translate(self.transmap_input)

        # Interpret Calc-specific suffixes
        expr = self._retokenize(expr)

        # Prepare the 'names' dictionary
        own_names = self.MATH_CONSTANTS
        own_names['ans'] = self.ans

        # Evaluate the expression
        # We bypass the SimpleEval.eval() method only for the sake of having a
        # "nice" source *filename* value.
        se = simpleeval.SimpleEval(
            operators=self.MATH_OPERATORS,
            functions=self.MATH_FUNCTIONS,
            names=own_names)
        se.expr = expr # done by SimpleEval.eval()
        self.ans = se._eval(ast.parse(expr, filename="expr").body[0].value)

        # format output according to result's type
        if isinstance(self.ans, bytes):
            self.ans = self.ans.decode("utf-8")

        if isinstance(self.ans, str):
            try:
                if self.ans.lower().startswith("0b"):
                    self.ans = int(self.ans, base=2)
                    return (bin(self.ans), self.ans, hex(self.ans), oct(self.ans)) + self._currencyfmt(self.ans)
                elif self.ans.lower().startswith("0o"):
                    self.ans = int(self.ans, base=8)
                    return (oct(self.ans), self.ans, hex(self.ans), bin(self.ans)) + self._currencyfmt(self.ans)
                elif self.ans.lower().startswith("0x"):
                    self.ans = int(self.ans, base=16)
                    return (hex(self.ans), self.ans, bin(self.ans), oct(self.ans)) + self._currencyfmt(self.ans)
                else:
                    self.ans = int(self.ans)
            except ValueError:
                return self.ans

        if isinstance(self.ans, bool):
            self.ans = int(self.ans)
            return str(self.ans)
        elif isinstance(self.ans, int):
            return (self.ans, hex(self.ans), bin(self.ans), oct(self.ans)) + self._currencyfmt(self.ans)
        elif isinstance(self.ans, float):
            self.ans = decimal.Decimal(self.ans)
        elif isinstance(self.ans, complex):
            return str(self.ans)

        if isinstance(self.ans, decimal.Decimal):
            if not self.ans.is_finite(): # nan or infinity
                return str(self.ans)
            else:
                do_trans = lambda s: str(s).translate(self.transmap_output).lower()
                results = { # note: this is a set!
                    do_trans(self.ans.normalize()),
                    do_trans(self.ans),
                    do_trans(self.ans.to_eng_string())}
                if self.rounding_precision is not None:
                    q = decimal.Decimal(10) ** -self.rounding_precision
                    v = do_trans(self.ans.quantize(q)).rstrip("0").rstrip(".")
                    results.add(v)
                results = list(results)
                results.sort(key=len)
                results += list(self._currencyfmt(self.ans))
                return results

        # duh?!
        return str(self.ans).translate(self.transmap_output)

    def _retokenize(self, expr):
        def _tokenize_number(dest, nstr, force_decimal):
            # convert floats to Decimal only if nstr is a float or if we've
            # had a float already in the expression (Python really rocks)
            if force_decimal or "." in nstr:
                dest.extend([
                    (tokenize.NAME, "Decimal"),
                    (tokenize.NAME, "("),
                    (tokenize.STRING, repr(nstr)),
                    (tokenize.NAME, ")")])
                force_decimal = True
            else:
                dest.append((tokenize.NUMBER, nstr))
            return force_decimal

        trans_tokens = []
        num_tok = None
        has_decimal = False

        # first pass
        tokens = tokenize.tokenize(io.BytesIO(expr.encode('utf-8')).readline)
        prev_tok = None
        for tokinfo in tokens:
            if tokinfo.type == tokenize.NUMBER:
                if "." in tokinfo.string:
                    has_decimal = True
                    break
            elif tokinfo.exact_type == tokenize.SLASH:
                if prev_tok is not None and prev_tok.type == tokenize.NUMBER:
                    has_decimal = True
                    break
            prev_tok = tokinfo

        # second pass
        tokens = tokenize.tokenize(io.BytesIO(expr.encode('utf-8')).readline)
        for tokinfo in tokens:
            push_generic_token = False

            if tokinfo.type == tokenize.NUMBER:
                if num_tok is not None: # weird?!
                    has_decimal = _tokenize_number(trans_tokens, num_tok.string, has_decimal)
                    num_tok = None
                num_tok = tokinfo
            elif tokinfo.type == tokenize.OP:
                if tokinfo.exact_type in self.TOKENSMAP_OPERATORS:
                    if num_tok is not None:
                        has_decimal = _tokenize_number(trans_tokens, num_tok.string, has_decimal)
                        num_tok = None
                    trans_tokens.append((
                        tokinfo.type,
                        self.TOKENSMAP_OPERATORS[tokinfo.exact_type]))
                else:
                    push_generic_token = True
            elif tokinfo.type == tokenize.NAME:
                if num_tok is not None and tokinfo.string in self.TOKENSMAP_NUMBER_SUFFIXES:
                    has_decimal = _tokenize_number(
                        trans_tokens,
                        str(self.TOKENSMAP_NUMBER_SUFFIXES[tokinfo.string](eval(num_tok.string))),
                        has_decimal)
                    num_tok = None
                elif tokinfo.string.lower() in self.TOKENSMAP_NAME_OPERATORS:
                    if num_tok is not None:
                        has_decimal = _tokenize_number(trans_tokens, num_tok.string, has_decimal)
                        num_tok = None
                    trans_tokens.append((
                        tokenize.OP,
                        self.TOKENSMAP_NAME_OPERATORS[tokinfo.string.lower()]))
                else:
                    push_generic_token = True
            else:
                push_generic_token = True

            if push_generic_token:
                if num_tok is not None:
                    has_decimal = _tokenize_number(trans_tokens, num_tok.string, has_decimal)
                    num_tok = None
                trans_tokens.append((tokinfo.type, tokinfo.string))

        return tokenize.untokenize(trans_tokens).decode('utf-8')

    def _currencyfmt(self, value):
        if not self.currency_enabled:
            return ()
        if not isinstance(value, (float, decimal.Decimal)):
            if self.currency_float_only:
                return ()

        value = decimal.Decimal(value)

        if self.currency_from_system:
            value_to_api = str(float(value))
            try:
                # use the GetCurrencyFormatEx windows api to format the value
                GetCurrencyFormatEx = kpwt.declare_func(
                    kpwt.kernel32, "GetCurrencyFormatEx", ret=kpwt.ct.c_int,
                    arg=[kpwt.LPCWSTR, kpwt.DWORD, kpwt.LPCWSTR, kpwt.LPVOID, kpwt.PWSTR, kpwt.ct.c_int])
                buf = kpwt.ct.create_unicode_buffer(128)
                res = GetCurrencyFormatEx(
                    None, 0, value_to_api, None, buf, len(buf))
                if res > 0 and len(buf.value) > 0:
                    return (buf.value, )
            except:
                traceback.print_exc()
                self.info(
                    'Failed to ask system to currency format value "' + str(value_to_api) + '". ' +
                    'Falling back to manual method.')

        # manual mode
        # note that this code block may be used as a fallback method in case the
        # above code failed to ask windows api to format the value
        formatted_value = self._currencyfmt_impl(
            value, places=self.currency_places,
            sep=self.currency_thousandsep, dp=self.currency_decsep)
        return (formatted_value, )

    def _currencyfmt_impl(
            self, value, places=2, curr='', sep=',', dp='.', pos='', neg='-',
            trailneg=''):
        """
        Convert Decimal to a money formatted string.
        Code from: https://docs.python.org/3/library/decimal.html#recipes

        places:  required number of places after the decimal point
        curr:    optional currency symbol before the sign (may be blank)
        sep:     optional grouping separator (comma, period, space, or blank)
        dp:      decimal point indicator (comma or period)
                 only specify as blank when places is zero
        pos:     optional sign for positive numbers: '+', space or blank
        neg:     optional sign for negative numbers: '-', '(', space or blank
        trailneg:optional trailing minus indicator:  '-', ')', space or blank

        >>> d = Decimal('-1234567.8901')
        >>> moneyfmt(d, curr='$')
        '-$1,234,567.89'
        >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
        '1.234.568-'
        >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
        '($1,234,567.89)'
        >>> moneyfmt(Decimal(123456789), sep=' ')
        '123 456 789.00'
        >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
        '<0.02>'
        """
        q = decimal.Decimal(10) ** -places # 2 places --> '0.01'
        sign, digits, exp = value.quantize(q).as_tuple()
        result = []
        digits = list(map(str, digits))
        build, next = result.append, digits.pop
        if sign:
            build(trailneg)
        for i in range(places):
            build(next() if digits else '0')
        if places:
            build(dp)
        if not digits:
            build('0')
        i = 0
        while digits:
            build(next())
            i += 1
            if i == 3 and digits:
                i = 0
                build(sep)
        build(curr)
        build(neg if sign else pos)
        return ''.join(reversed(result))
