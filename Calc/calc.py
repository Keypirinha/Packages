# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_wintypes as kpwt
import io
import ast
import tokenize
import math
import random
import traceback
import os
import re
import json
import keyword
from .lib.number import Number
from .lib import simpleeval

def _safe_abs(x):
    return Number(x).__abs__()

def _safe_bin(x):
    return bin(Number(x).safe_int())

def _safe_bool(x=False):
    return Number(x).__bool__()

def _safe_chr(i):
    return chr(Number(i).safe_int())

def _safe_divmod(a, b):
    return Number(a).__divmod__(b)

def _safe_float(x=None):
    return Number(0) if x is None else Number(x).__float__()

def _safe_hex(x):
    return hex(Number(x).safe_int())

def _safe_int(x=0, base=10):
    try:
        return int(x, base)
    except:
        return Number(x).__int__()

def _safe_min(*args, **kwargs):
    if len(args) == 1:
        converted_args = [Number(x) for x in args[0]]
    else:
        converted_args = [Number(x) for x in args]
    return min(converted_args, **kwargs)

def _safe_max(*args, **kwargs):
    if len(args) == 1:
        converted_args = [Number(x) for x in args[0]]
    else:
        converted_args = [Number(x) for x in args]
    return max(converted_args, **kwargs)

def _safe_oct(x):
    return oct(Number(x).safe_int())

def _safe_ord(x):
    if isinstance(x, str):
        return ord(x)
    else:
        return ord(str(Number(x)))

def _safe_pow(x, y, z=None):
    return Number(x).__pow__(y, z)

def _safe_round(x, ndigits=None):
    return Number(x).__round__(ndigits)


def _safe_custom_rand(top):
    return int(random.random() * Number(top).safe_int())

def _safe_custom_randf(a, b):
    try:
        safe_a = Number(a).safe_int()
    except:
        safe_a = Number(a).__float__()

    try:
        safe_b = Number(b).safe_int()
    except:
        safe_b = Number(b).__float__()

    return random.uniform(safe_a, safe_b)

def _safe_custom_randi(a, b):
    return random.randint(Number(a).safe_int(), Number(b).safe_int())


def _safe_math_exp(x):
    return Number(x).exp()

def _safe_math_gcd(a, b):
    safe_a = Number(a)
    safe_b = Number(b)
    if safe_a == 0 and safe_b == 0:
        return 0
    else:
        return math.gcd(safe_a.safe_int(), safe_b.safe_int())

def _safe_math_sqrt(x):
    return Number(x).sqrt()

class _safe_mathfunc_args2float():
    __slots__ = ('_func')

    def __init__(self, func):
        self._func = func

    def __call__(self, *args, **kwargs):
        converted_args = [Number(a).__float__() for a in args]
        return self._func(*converted_args, **kwargs)

class CalcVarHandler:
    REGEX_CALC_VAR_EXP = r'^\s*(?P<var1>[a-zA-Z][a-zA-Z0-9]*)?\s*(?P<eq1>=)(?P<expr1>[^=].*)$'
    REGEX_CALC_EXP_VAR = r'^(?P<expr2>.*[^=])(?P<eq2>=)\s*(?P<var2>[a-zA-Z][a-zA-Z0-9]*)?\s*$'
    SAVE_VAR_PARSER    = f"{REGEX_CALC_VAR_EXP}|{REGEX_CALC_EXP_VAR}"
    VAR_CACHE_FILE     = "variables.json"
    calc_vars = {}
    var_to_save = None

    def __init__(self, plugin, constants):
        self.plugin = plugin
        self.constants = constants.copy()
        self.constants.pop(self.plugin.ANSWER_VARIABLE)
        cache_path = self.plugin.get_package_cache_path(create=True)
        self.var_cache_file = os.path.join(cache_path, self.VAR_CACHE_FILE)

    def validate_vars(self):
        forbidden = set()
        for v in self.calc_vars.keys(): # Can't override constants/python keywords
            if v in self.constants or v in keyword.kwlist:
                forbidden.add(v)
        for v in forbidden:
                self.calc_vars.pop(v)

    def load_vars(self):
        self.save_var_parser = re.compile(self.SAVE_VAR_PARSER)

        if os.path.exists(self.var_cache_file):
            try:
                with open(self.var_cache_file) as f:
                    self.calc_vars = json.load(f)
                    self.validate_vars()
            except Exception as e:
                self.plugin.err(f"Error loading variables file '{self.var_cache_file}'. {e}")

    def vars(self):
        return self.calc_vars.copy().items()

    def save_if_var(self, ans):
        if not self.var_to_save:
            return
        if self.var_to_save in self.constants.keys():
            self.plugin.warn(f"A constant, {self.var_to_save}, cannot be modified.")
            return
        if self.var_to_save in keyword.kwlist:
            self.plugin.warn(f"A Python keyword, {self.var_to_save}, cannot be used as variable name.")
            return

        if isinstance(ans, Number):
            ans = ans.__float__()
        self.calc_vars[self.var_to_save] = ans
        self.save()

    def save(self):
        self.validate_vars()
        try:
            with open(self.var_cache_file, 'w') as f:
                json.dump(self.calc_vars, f)
        except Exception as e:
            self.plugin.err(f"Error saving variables file '{self.var_cache_file}'. {e}")

    def expression_to_evaluate(self, user_input, evaluate):
        self.var_to_save = self.plugin.ANSWER_VARIABLE
        suffix = False
        save_var_match = self.save_var_parser.match(user_input)
        if not save_var_match:
            return (user_input if evaluate else None, suffix)
        elif save_var_match["var1"] or save_var_match["eq1"]:
            self.var_to_save = save_var_match["var1"]
            if save_var_match["eq1"]:
                evaluate = True
            expr = save_var_match["expr1"]
        elif save_var_match["var2"] or save_var_match["eq2"]:
            self.var_to_save = save_var_match["var2"]
            if save_var_match["eq2"]:
                evaluate = True
                suffix = True
            expr = save_var_match["expr2"]

        return (expr, suffix)

    def update_calc_vars(self, own_names):
        own_names.update(self.calc_vars)

    def delete_var(self, var, current_vars):
        if var in self.calc_vars:
            self.calc_vars.pop(var)
            current_vars.pop(var)
            self.save()

    def delete_all_vars(self, current_vars):
        for var in [key for key in current_vars.keys()]:
            if not var in self.constants.keys():
                self.calc_vars.pop(var)
                current_vars.pop(var)
        self.save()

class Calc(kp.Plugin):
    """
    Inline calculator.

    Evaluates a mathematical expression and shows its result.
    """
    ITEMCAT_VAR = kp.ItemCategory.USER_BASE + 1
    VARS_KEYWORD = "Calc: Variables"
    DEFAULT_KEYWORD = "="
    DEFAULT_ALWAYS_EVALUATE = True
    DEFAULT_ROUNDING_PRECISION = 5
    DEFAULT_BASE_CONVERSION = True
    DEFAULT_CURRENCY_MODE = "float"
    DEFAULT_CURRENCY_FORMAT = "system"
    DEFAULT_CURRENCY_DECIMALSEP = "."
    DEFAULT_CURRENCY_THOUSANDSEP = ","
    DEFAULT_CURRENCY_PLACES = 2

    ANSWER_VARIABLE = 'ans'

    MATH_OPERATORS = simpleeval.DEFAULT_OPERATORS

    MATH_CONSTANTS = {
        'pi': math.pi,
        'e': math.e,
        'inf': math.inf,
        'nan': math.nan,
        ANSWER_VARIABLE: 0, # replaced by self.ans at runtime
    }

    MATH_FUNCTIONS = {
        'abs': _safe_abs,
        'bin': _safe_bin,
        'bool': _safe_bool,
        'chr': _safe_chr,
        'divmod': _safe_divmod,
        'float': _safe_float,
        'hex': _safe_hex,
        'int': _safe_int,
        'len': len,
        'min': _safe_min,
        'max': _safe_max,
        'oct': _safe_oct,
        'ord': _safe_ord,
        'pow': _safe_pow,
        'round': _safe_round,
        'str': str,

        'rand': _safe_custom_rand,
        'rand1': random.random, # returns [0.0, 1.0)
        'randf': _safe_custom_randf, # random.uniform(a, b): Return a random floating point number N such that a <= N <= b for a <= b and b <= N <= a for b < a
        'randi': _safe_custom_randi, # returns N where: a <= N <= b

        'acos': _safe_mathfunc_args2float(math.acos),
        'acosh': _safe_mathfunc_args2float(math.acosh),
        'asin': _safe_mathfunc_args2float(math.asin),
        'asinh': _safe_mathfunc_args2float(math.asinh),
        'atan': _safe_mathfunc_args2float(math.atan),
        'atan2': _safe_mathfunc_args2float(math.atan2),
        'atanh': _safe_mathfunc_args2float(math.atanh),
        'ceil': _safe_mathfunc_args2float(math.ceil),
        'cos': _safe_mathfunc_args2float(math.cos),
        'cosh': _safe_mathfunc_args2float(math.cosh),
        'deg': _safe_mathfunc_args2float(math.degrees),
        'exp': _safe_math_exp,
        'factor': _safe_mathfunc_args2float(math.factorial),
        'floor': _safe_mathfunc_args2float(math.floor),
        'gcd': _safe_math_gcd,
        'hypot': _safe_mathfunc_args2float(math.hypot),
        'log': _safe_mathfunc_args2float(math.log),
        'rad': _safe_mathfunc_args2float(math.radians),
        'sin': _safe_mathfunc_args2float(math.sin),
        'sinh': _safe_mathfunc_args2float(math.sinh),
        'sqrt': _safe_math_sqrt,
        'tan': _safe_mathfunc_args2float(math.tan),
        'tanh': _safe_mathfunc_args2float(math.tanh),

        # undocumented
        'Number': Number, # see _retokenize()
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
        'y':  lambda n: n / 1000 ** 8, # yocto
        'z':  lambda n: n / 1000 ** 7, # zepto
        'a':  lambda n: n / 1000 ** 6, # atto
        'f':  lambda n: n / 1000 ** 5, # femto
        'p':  lambda n: n / 1000 ** 4, # pico
        'n':  lambda n: n / 1000 ** 3, # nano
        'u':  lambda n: n / 1000 ** 2, # micro
        'm':  lambda n: n / 1000,      # milli
        'c':  lambda n: n / 100,       # centi
        'd':  lambda n: n / 10,        # deci
        'da': lambda n: n * 10,        # deca
        'h':  lambda n: n * 100,       # hecto
        'k':  lambda n: n * 1000,      # Kilo
        'M':  lambda n: n * 1000 ** 2, # Mega
        'G':  lambda n: n * 1000 ** 3, # Giga
        'T':  lambda n: n * 1000 ** 4, # Tera
        'P':  lambda n: n * 1000 ** 5, # Peta
        'E':  lambda n: n * 1000 ** 6, # Exa
        'Z':  lambda n: n * 1000 ** 7, # Zetta
        'Y':  lambda n: n * 1000 ** 8, # Yotta

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
    decimal_separator = "."
    thousand_separator = ","
    transmap_input = ""
    transmap_output = ""
    rounding_precision = DEFAULT_ROUNDING_PRECISION
    base_conversion = DEFAULT_BASE_CONVERSION
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
        self.var_handler = CalcVarHandler(self, self.MATH_CONSTANTS)
        self._read_config()
        self.set_actions(self.ITEMCAT_VAR, [
            self.create_action(
                name="copy",
                label="Copy",
                short_desc="Press Enter to copy this varible"),
            self.create_action(
                name="delete",
                label="Delete",
                short_desc="Press Enter to delete this variable"),
            self.create_action(
                name="delete_all",
                label="Delete All",
                short_desc="Press Enter to delete all variables")
        ])

    def on_catalog(self):
        self.set_catalog([
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label=self.DEFAULT_KEYWORD,
                short_desc="Evaluate a mathematical expression",
                target=self.DEFAULT_KEYWORD,
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS),
            self.create_item(
                category=self.ITEMCAT_VAR,
                label=self.VARS_KEYWORD,
                short_desc="Display Calc variables",
                target=self.VARS_KEYWORD,
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS)])

    def on_suggest(self, user_input, items_chain):
        if items_chain and items_chain[0].category() == self.ITEMCAT_VAR:
            suggestions = []
            for i,(var,val) in enumerate(self.var_handler.vars()):
                suggestions.append(self.create_item(
                    category=self.ITEMCAT_VAR,
                    label=f"{var} = {val}",
                    short_desc="Press Enter to copy the result",
                    target=str(val),
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE,
                    data_bag = var))
            self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.LABEL_ASC)
            return

        if not len(user_input):
            return
        if items_chain and (
                items_chain[0].category() != kp.ItemCategory.KEYWORD or
                items_chain[0].target() != self.DEFAULT_KEYWORD):
            return

        eval_requested = False
        expression, suffix = self.var_handler.expression_to_evaluate(user_input, self.always_evaluate)
        if expression:
            # always evaluate if an assignment is made or = (DEFAULT_KEYWORD) is used
            eval_requested = True
        elif items_chain:
            eval_requested = True
        elif not items_chain and not self.always_evaluate:
            return

        suggestions = []
        try:
            results = self._eval(expression)
            if not isinstance(results, (tuple, list)):
                results = (results,)
            for res in results:
                res = str(res)
                short_desc="Press Enter to copy the result"
                if res.startswith("0b"):
                    tmp = res[2:]
                    width = 0 if tmp == "0" else len(tmp)
                    short_desc = "{}-bit wide ({})".format(width, short_desc)
                suggestions.append(self.create_item(
                    category=kp.ItemCategory.EXPRESSION,
                    label="= " + res if not items_chain else res,
                    short_desc=short_desc,
                    target=res,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE))
        except Exception as exc:
            if suffix or not eval_requested or self.var_handler.var_to_save == self.ANSWER_VARIABLE:
                # stay quiet if evaluation hasn't been explicitly requested or
                # if suffix format to avoid getting exceptions of things like:
                # https://www.youtube.com/watch?v=abcdef
                return

            suggestions.append(self.create_error_item(
                label=expression,
                short_desc="Error: " + str(exc)))

        self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if item and item.category() == kp.ItemCategory.EXPRESSION:
            kpu.set_clipboard(item.target())
            self.var_handler.save_if_var(self.ans)
        elif item and (item.category() == self.ITEMCAT_VAR):
            if action and action.name() == "copy":
                kpu.set_clipboard(item.target())
            elif action and action.name() == "delete":
                self.var_handler.delete_var(item.data_bag(), self.MATH_CONSTANTS)
            elif action and action.name() == "delete_all":
                self.var_handler.delete_all_vars(self.MATH_CONSTANTS)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()

    def _read_config(self):
        settings = self.load_settings()
        self.var_handler.load_vars()

        # [main] always_evaluate
        self.always_evaluate = settings.get_bool(
            "always_evaluate", "main", self.DEFAULT_ALWAYS_EVALUATE)

        # [main] decimal_separator
        DEFAULT_DECIMAL_SEPARATOR = "dot"
        self.decimal_separator = "."
        self.thousand_separator = ","
        config_decsep = settings.get_enum(
            "decimal_separator", "main",
            fallback=DEFAULT_DECIMAL_SEPARATOR,
            enum=["dot", "comma", "auto"])
        if config_decsep == "auto":
            config_decsep = DEFAULT_DECIMAL_SEPARATOR
            try:
                # use the GetLocaleInfoEx windows api to get the decimal and
                # thousand separators configured by system's user
                GetLocaleInfoEx = kpwt.declare_func(
                    kpwt.kernel32, "GetLocaleInfoEx", ret=kpwt.ct.c_int,
                    args=[kpwt.LPCWSTR, kpwt.DWORD, kpwt.PWSTR, kpwt.ct.c_int])
                LOCALE_SDECIMAL = 0x0000000E
                LOCALE_STHOUSAND = 0x0000000F

                # decimal separator
                buf = kpwt.ct.create_unicode_buffer(10)
                res = GetLocaleInfoEx(None, LOCALE_SDECIMAL, buf, len(buf))
                if res == 2 and len(buf.value) == res - 1 and buf.value == ",":
                    config_decsep = "comma"

                # thousand separator
                # quite awful to have a try block here but we take advantage of
                # having GetLocaleInfoEx already defined
                try:
                    buf = kpwt.ct.create_unicode_buffer(10)
                    res = GetLocaleInfoEx(None, LOCALE_STHOUSAND, buf, len(buf))
                    if res > 0:
                        self.thousand_separator = buf
                except:
                    traceback.print_exc()
            except:
                self.warn(
                    "Failed to get system user decimal and thousand separators. " +
                    "Falling back to default (" + config_decsep + ")...")
                traceback.print_exc()
            self.info("Using \"{}\" as a decimal separator".format(config_decsep))
        if config_decsep == "comma":
            self.decimal_separator = ","
            self.thousand_separator = " "
            self.transmap_input = str.maketrans(",;", ".,")
            self.transmap_output = str.maketrans(".", ",")
        else:
            self.decimal_separator = "."
            self.thousand_separator = ","
            self.transmap_input = ""
            self.transmap_output = ""

        # [main] base conversion
        self.base_conversion = settings.get_bool(
            "base_conversion", "main", self.DEFAULT_BASE_CONVERSION)

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
        own_names[self.ANSWER_VARIABLE] = self.ans
        self.var_handler.update_calc_vars(own_names)

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
                    if self.base_conversion:
                        return (bin(self.ans), self.ans, hex(self.ans), oct(self.ans)) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
                    else:
                        return (bin(self.ans), ) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
                elif self.ans.lower().startswith("0o"):
                    self.ans = int(self.ans, base=8)
                    if self.base_conversion:
                        return (oct(self.ans), self.ans, hex(self.ans), bin(self.ans)) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
                    else:
                        return (oct(self.ans), ) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
                elif self.ans.lower().startswith("0x"):
                    self.ans = int(self.ans, base=16)
                    if self.base_conversion:
                        return (hex(self.ans), self.ans, bin(self.ans), oct(self.ans)) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
                    else:
                        return (hex(self.ans), ) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
                else:
                    self.ans = int(self.ans)
            except ValueError:
                return self.ans

        if isinstance(self.ans, bool):
            self.ans = int(self.ans)
            return str(self.ans)
        elif isinstance(self.ans, int):
            if self.base_conversion:
                return (self.ans, hex(self.ans), bin(self.ans), oct(self.ans)) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
            else:
                return (self.ans, ) + self._numberfmt(self.ans) + self._currencyfmt(self.ans)
        elif isinstance(self.ans, float):
            self.ans = Number(self.ans)
        elif isinstance(self.ans, complex):
            return str(self.ans)

        if isinstance(self.ans, Number):
            if not self.ans.is_finite(): # nan or infinity
                return str(self.ans)
            else:
                def do_trans(val):
                    val = str(val).translate(self.transmap_output).lower()
                    if self.decimal_separator in val:
                        val = val.rstrip("0").rstrip(self.decimal_separator)
                        if not len(val):
                            val = "0"
                    return val
                results = { # note: this is a set!
                    do_trans(self.ans.normalize()),
                    do_trans(self.ans),
                    do_trans(self.ans.to_eng_string())}

                if self.rounding_precision is not None:
                    q = Number(10) ** -self.rounding_precision
                    v = do_trans(self.ans.quantize(q))
                    results.add(v)
                results = list(results)
                results.sort(key=len)

                if self.base_conversion:
                    try:
                        intval = self.ans.safe_int()
                        for v in (str(intval), hex(intval), bin(intval), oct(intval)):
                            if v not in results:
                                results.append(v)
                    except:
                        pass

                for v in self._numberfmt(self.ans):
                    results.append(v)
                results += list(self._currencyfmt(self.ans))
                return results

        # duh?!
        return str(self.ans).translate(self.transmap_output)

    def _retokenize(self, expr):
        def _tokenize_number(dest, nstr, force_decimal):
            # convert floats to Number only if nstr is a float or if we've
            # had a float already in the expression (Python really rocks)
            if force_decimal or "." in nstr:
                dest.extend([
                    (tokenize.NAME, "Number"),
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

    def _numberfmt(self, value):
        if not isinstance(value, (int, float, Number)):
            return ()
        if -999 <= value <= 999:
            return ()
        formatted_value = self._currencyfmt_impl(
            Number(value), places=self.rounding_precision, curr="",
            sep=self.thousand_separator, dp=self.decimal_separator,
            neg="-", trailneg="")
        if self.decimal_separator in formatted_value:
            formatted_value = formatted_value.rstrip("0").rstrip(self.decimal_separator)
            if not len(formatted_value):
                formatted_value = "0"
        return (formatted_value, )

    def _currencyfmt(self, value):
        if not self.currency_enabled:
            return ()
        if not isinstance(value, (float, Number)):
            if self.currency_float_only:
                return ()

        value = Number(value)

        if self.currency_from_system:
            value_to_api = str(float(value))
            try:
                # use the GetCurrencyFormatEx windows api to format the value
                GetCurrencyFormatEx = kpwt.declare_func(
                    kpwt.kernel32, "GetCurrencyFormatEx", ret=kpwt.ct.c_int,
                    args=[kpwt.LPCWSTR, kpwt.DWORD, kpwt.LPCWSTR, kpwt.LPVOID, kpwt.PWSTR, kpwt.ct.c_int])
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
        if self.currency_decsep in formatted_value:
            formatted_value = formatted_value.rstrip("0").rstrip(self.currency_decsep)
            if not len(formatted_value):
                formatted_value = "0"
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
        q = Number(10) ** -places # 2 places --> '0.01'
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
