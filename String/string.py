# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha_api
import keypirinha as kp
import keypirinha_util as kpu
import codecs
import hashlib
import json
import os
import shlex
import secrets
import traceback
import urllib.parse
import uuid
import zlib
import base64
import binascii
import re
import unicodedata

def i2xx(b, prefix):
    if not isinstance(b, int): raise TypeError
    x = hex(b)[2:]
    while (len(x) % 2): x = "0" + x
    if prefix: x = "0x" + x
    return x

class _Functor:
    __slots__ = ("name", "label", "desc")

    def __init__(self, name, label, desc):
        self.name = name
        self.label = label
        self.desc = desc

    def convert(self, data):
        raise NotImplementedError

class _Functor_ArgQuoteUnix(_Functor):
    def __init__(self):
        super().__init__("arg_quote_unix", "Arg Quote (Unix-style)",
                         "Quote a command line argument (Unix-style)")

    def convert(self, data):
        return (shlex.quote(data), )

class _Functor_ArgQuoteWin(_Functor):
    def __init__(self):
        super().__init__("arg_quote_win", "Arg Quote (Windows-style)",
                         "Quote a command line argument (Windows-style)")

    def convert(self, data):
        return (kpu.cmdline_quote(data), )

class _Functor_ArgSplitUnix(_Functor):
    def __init__(self):
        super().__init__("arg_split_unix", "Arg Split (Unix-style)",
                         "Split a command line (Unix-style)")

    def convert(self, data):
        return shlex.split(data)

class _Functor_ArgSplitWin(_Functor):
    def __init__(self):
        super().__init__("arg_split_win", "Arg Split (Windows-style)",
                         "Split a command line (Windows-style)")

    def convert(self, data):
        return kpu.cmdline_split(data)

class _Functor_CaseConversion(_Functor):
    _algorithms = (
        ("lower", "Lower Case"),
        ("upper", "Upper Case"),
        ("capitalize", "Capitalized"),
        ("title", "Title Case"),
        ("swapcase", "Swapped Case"),
        ("uppercamelcase", "Upper Camel Case"),
        ("lowercamelcase", "Lower Camel Case"),
        ("kebabcase", "Kebab Case"),
        ("snakecase", "Snake Case"),
        ("slug", "Slug Case"))

    def __init__(self):
        super().__init__("case_convert", "Case Conversion",
                         "Change the case of the given string")

    def convert(self, data):
        data = data.strip() if isinstance(data, str) else str(data)

        # We use a set to keep track of the resulting values so that algorithms
        # giving the same result than a previous one is discarded. Otherwise,
        # Keypirinha would merge duplicates with previous items in the
        # suggestions list, resulting in original algo being positioned
        # differently depending on the provided user input.
        #
        # Suggestions without keeping track of targets in a set (arg is "test"):
        #   "test" - "Lower Case"
        #   "Test" - "Title Case"
        #   "TEST" - "Swapped Case"
        #
        # Suggestions made when we keep track of the targets with a set:
        #   "test" - "Lower Case"
        #   "TEST" - "Upper Case"
        #   "Test" - "Capitalized"
        targets = set()

        results = []
        for (algo, desc) in self._algorithms:
            value = getattr(data, algo)() if hasattr(data, algo) else getattr(self, algo)(data)
            if value not in targets:
                targets.add(value)
                results.append({'label': value, 'target': value, 'desc': desc})

        return results

    # Upper camel casing converts above_average to AboveAverage
    def uppercamelcase(self, data):
        splits = re.split(r'[-_]+', data)
        return data if len(splits) < 1 else "".join([s.capitalize() for s in splits])

    # Lower camel casing (or 'drinking camel casing') converts above_average to aboveAverage
    def lowercamelcase(self, data):
        splits = re.split(r'[-_]+', data)
        return data if len(splits) < 1 else splits[0].lower()+"".join([s.capitalize() for s in splits[1:]])

    # Kebab casing (or 'sausage casing') converts AboveAverage to above-average
    def kebabcase(self, data, delim = "-"):
        # For casing treat characters without accents (ÉtéNéerlandais => été-néerlandais)
        ascii_data = ''.join((c for c in unicodedata.normalize('NFD', data) if unicodedata.category(c) != 'Mn'))

        splits = [m.span()[0] for m in re.finditer('[A-Z]+[a-z0-9]*', ascii_data)]+[len(ascii_data)]
        splits = [0] + splits if splits[0] != 0 else splits

        need_prefix = lambda splits, split: split > 0 and data[splits[split]-1].isalnum()
        do_prefix = lambda word, splits, split: (delim if need_prefix(splits,split) else "") + word

        return "".join([do_prefix(data[splits[split]:splits[split+1]].lower(),splits,split) for split in range(len(splits)-1)])

    # Snake casing  converts AboveAverage to above-average
    def snakecase(self, data):
        return self.kebabcase(data, delim = "_")

    # Slug casing  converts `Slug (Casé)` to `slug-case`
    def slug(self, data):
        result = []
        splits = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.;:]+')
        for word in splits.split(data.lower()):
            result.append(unicodedata.normalize('NFKD', word).encode('ascii', 'ignore').decode('ascii'))
        return '-'.join(result)

class _Functor_Hashlib(_Functor):
    __slots__ = ("algo")

    def __init__(self, algo):
        self.algo = algo
        super().__init__(algo.lower(), "Hash (" + algo.lower() + ")",
                         "Hash a string with the " + algo + " algorithm")

    def convert(self, data):
        if isinstance(data, str):
            data = data.encode(encoding="utf-8", errors="strict")
        hasher = hashlib.new(self.algo)
        hasher.update(data)
        result = hasher.hexdigest()
        return (result.lower(), result.upper())

class _Functor_Keypirinha(_Functor):
    def __init__(self):
        super().__init__("keypirinha", "Hash (Keypirinha)",
                         "Hash a string with Keypirinha's internal hasher")

    def convert(self, data):
        if not data: return ()
        result = keypirinha_api.hash_string(data)
        return (i2xx(result, False), i2xx(result, True), str(result))

class _Functor_RandBytes(_Functor):
    def __init__(self):
        super().__init__("rand_bytes", "Random Bytes",
                         "Generate a string of random bytes")

    def convert(self, data):
        # data arg is interpreted as the desired count of bytes to generate
        try:
            if not isinstance(data, int):
                data = int(data, base=10)
        except:
            data = 8

        randbytes = os.urandom(data)
        return (
            randbytes.hex(),
            " ".join([i2xx(b, False) for b in randbytes]),
            " ".join([i2xx(b, True) for b in randbytes]))

class _Functor_RandPassword(_Functor):
    def __init__(self):
        super().__init__("rand_password", "Random Password",
                         "Generate a random password")

    def convert(self, data):
        # data arg is interpreted as the desired count of characters to generate
        if not isinstance(data, int):
            try:
                data = int(data, base=10)
            except:
                data = 8
        if not data:
            return ()

        # value returned by secrets.token_urlsafe is base64-encoded so longer
        # than requested
        return (secrets.token_urlsafe(data)[0:data], )

class _Functor_RandUUID(_Functor):
    def __init__(self):
        super().__init__("rand_uuid", "Random UUID/GUID",
                         "Generate a random UUID/GUID")

    def convert(self, data=None):
        obj = uuid.uuid4()
        return (
            str(obj),                     # 4ef6af2f-3f48-4b30-9361-93fee889d94d
            "{" + str(obj) + "}",         # {4ef6af2f-3f48-4b30-9361-93fee889d94d}
            "{" + str(obj).upper() + "}", # {4EF6AF2F-3F48-4B30-9361-93FEE889D94D}
            obj.hex,                      # 4ef6af2f3f484b30936193fee889d94d
            obj.urn,                      # urn:uuid:4ef6af2f-3f48-4b30-9361-93fee889d94d
            str(obj.int))                 # 104960641863412236247170365975433959757

class _Functor_Rot13(_Functor):
    def __init__(self):
        super().__init__("rot13", "rot13",
                         "rot13 a string (similar to PHP's str_rot13)")

    def convert(self, data):
        # reminder: rot_13 codec is text-to-text
        return (codecs.encode(data, encoding="rot_13", errors="strict"), )


class _Functor_UrlQuote(_Functor):
    def __init__(self):
        super().__init__("url_quote", "URL Quote",
                         "URL-quote a string (including space chars)")

    def convert(self, data):
        return (urllib.parse.quote(data), )

class _Functor_UrlQuotePlus(_Functor):
    def __init__(self):
        super().__init__("url_quote_plus", "URL Quote+",
                         "URL-quote+ a string (space chars to +)")

    def convert(self, data):
        return (urllib.parse.quote_plus(data), )

class _Functor_UrlSplit(_Functor):
    def __init__(self):
        super().__init__("url_split", "URL Split", "Split a URL")

    def convert(self, data):
        # test: https://l0gin:p%4055w0rd@www.example.com:443/%7Ebob/index.html?arg=%20val;a2=test#specific-section
        url = urllib.parse.urlsplit(data)
        unquoted_results = []
        raw_results = []
        for k in ("username", "password", "hostname", "path", "query",
                  "fragment", "port", "scheme", "netloc", "port"):
            v = getattr(url, k)
            if not v: continue

            desc = k + " - press Enter to copy"

            if k == "query":
                unquoted_results.append({
                    'label': v,
                    'target': v,
                    'desc': desc})
                try:
                    json_args = json.dumps(urllib.parse.parse_qs(v))
                    unquoted_results.append({
                        'label': json_args,
                        'target': json_args,
                        'desc': "json " + desc})
                except ValueError:
                    pass
            else:
                v = str(v)
                uv = urllib.parse.unquote(v)

                if uv and uv != v:
                    unquoted_results.append({
                        'label': uv,
                        'target': uv,
                        'desc': desc})
                    raw_results.append({
                        'label': v,
                        'target': v,
                        'desc': "raw " + desc})
                else:
                    unquoted_results.append({
                        'label': v,
                        'target': v,
                        'desc': desc})

        return unquoted_results + raw_results

class _Functor_UrlUnquote(_Functor):
    def __init__(self):
        super().__init__("url_unquote_plus", "URL Unquote",
                         "URL-unquote a string")

    def convert(self, data):
        return (urllib.parse.unquote_plus(data), )

class _Functor_ZLib(_Functor):
    def __init__(self, func_name):
        super().__init__(func_name, "Hash (" + func_name.lower() + ")",
                         "Hash a string with the " + func_name + " algorithm")

    def convert(self, data):
        if isinstance(data, str):
            data = data.encode(encoding="utf-8", errors="strict")
        result = getattr(zlib, self.name)(data)
        return (i2xx(result, False), i2xx(result, True), str(result))

class _Functor_Base64(_Functor):
    def __init__(self):
        super().__init__("base64", "Base64",
                         "Encoding/decoding to printable ASCII characters")

    def convert(self, data):
        if isinstance(data, str):
            data = data.encode()

        encoded = base64.b64encode(data).decode()

        results = [
            {'label': encoded, 'target': encoded, 'desc': 'Encoded string'}
        ]

        try:
            decoded = base64.b64decode(data).decode()
        except (binascii.Error, UnicodeError):
            pass
        else:
            results.append({'label': decoded, 'target': decoded, 'desc': 'Decoded string'})

        return results

class _Functor_Reverse(_Functor):
    def __init__(self):
        super().__init__("reverse", "Reverse",
                         "Reverse a string")

    def convert(self, data):
        return [{'label': data[::-1], 'target': data[::-1], 'desc': 'Reversed string'}]

class _Functor_Unescape(_Functor):
    def __init__(self):
        super().__init__("unescape", "Un-escape",
                         "Un-escape a backslash-escaped string")

    def convert(self, data):
        # another method:
        # escaped = data.encode('utf-8').decode('unicode_escape')

        try:
            escaped = codecs.decode(codecs.encode(data, 'latin-1', 'backslashreplace'), 'unicode-escape')
        except UnicodeDecodeError as e:
            return []

        return [{'label': escaped, 'target': escaped, 'desc': 'Un-escaped string'}]

class String(kp.Plugin):
    """
    A multi-purpose plugin for string conversion and generation

    Features:
    * case conversion
    * hash a string using standard algorithms like CRC32, MD5, SHA*, etc...
    * generate a random UUID, also called GUID
    * generate a random password
    * generate random bytes
    * URL-quote a string
    * URL-unquote a string
    * split a URL
    * convert URL arguments to JSON
    * quote a command line argument (Windows & Unix style)
    * split a command line (Windows & Unix style)
    """

    ITEM_LABEL_PREFIX = "String: "
    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 1

    functors = {}

    def __init__(self):
        super().__init__()

    def on_start(self):
        functors_list = [
            _Functor_ArgQuoteUnix(),
            _Functor_ArgQuoteWin(),
            _Functor_ArgSplitUnix(),
            _Functor_ArgSplitWin(),
            _Functor_CaseConversion(),
            _Functor_Keypirinha(),
            _Functor_RandBytes(),
            _Functor_RandPassword(),
            _Functor_RandUUID(),
            _Functor_Rot13(),
            _Functor_UrlQuote(),
            _Functor_UrlQuotePlus(),
            _Functor_UrlSplit(),
            _Functor_UrlUnquote(),
            _Functor_ZLib("adler32"),
            _Functor_ZLib("crc32"),
            _Functor_Base64(),
            _Functor_Reverse(),
            _Functor_Unescape()]

        for algo in hashlib.algorithms_available:
            # some algorithms are declared twice in the list, like 'MD4' and
            # 'md4', in which case we favor uppercased one
            if algo.upper() != algo and algo.upper() in hashlib.algorithms_available:
                continue
            functors_list.append(_Functor_Hashlib(algo))

        self.functors = {}
        for functor in functors_list:
            if functor.name in self.functors:
                self.warn("functor declared twice:", functor.name)
            else:
                self.functors[functor.name] = functor

    def on_catalog(self):
        catalog = []

        for name, functor in self.functors.items():
            catalog.append(self.create_item(
                category=kp.ItemCategory.REFERENCE,
                label=self.ITEM_LABEL_PREFIX + functor.label,
                short_desc=functor.desc,
                target=functor.name,
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS))

        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if not items_chain:
            return

        current_item = items_chain[-1]
        if current_item.category() != kp.ItemCategory.REFERENCE:
            return

        if current_item.target() in self.functors:
            functor = self.functors[current_item.target()]
            suggestions = []

            try:
                results = functor.convert(user_input)
                for res in results:
                    if isinstance(res, dict):
                        pass
                    else: # str
                        target = res
                        res = {'label': target, 'target': target}

                    if not res['target']:
                        continue
                    if 'desc' not in res:
                        res['desc'] = "Press Enter to copy"

                    suggestions.append(self.create_item(
                        category=self.ITEMCAT_RESULT,
                        label=res['label'],
                        short_desc=res['desc'],
                        target=res['target'],
                        args_hint=kp.ItemArgsHint.FORBIDDEN,
                        hit_hint=kp.ItemHitHint.IGNORE))

            except Exception as exc:
                traceback.print_exc()
                suggestions.append(self.create_error_item(
                    label=user_input,
                    short_desc="Error({}): {}".format(functor.name, exc)))

            self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

        else:
            self.set_suggestions(
                self.create_error_item(
                    label=user_input,
                    short_desc="Error: unknown functor: " + current_item.target()),
                kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if item and item.category() == self.ITEMCAT_RESULT:
            kpu.set_clipboard(item.target())
