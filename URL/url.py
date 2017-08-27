# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import re
import socket

class URL(kp.Plugin):
    """Launch URLs"""
    WEB_SCHEMES = ("http", "https", "ftp")
    KNOWN_TLDS = ( # some hard-coded TLDs in case DB resources can't be read
        "ac", "ad", "aero", "ae", "af", "ag", "ai", "al", "am", "an", "ao",
        "aq", "arpa", "ar", "asia", "as", "at", "au", "aw", "ax", "az", "ba",
        "bb", "bd", "be", "bf", "bg", "bh", "biz", "bi", "bj", "bm", "bn", "bo",
        "br", "bs", "bt", "bv", "bw", "by", "bz", "cat", "ca", "cc", "cd", "cf",
        "cg", "ch", "ci", "ck", "cl", "cm", "cn", "coop", "com", "co", "cr",
        "cu", "cv", "cx", "cy", "cz", "de", "dj", "dk", "dm", "do", "dz", "ec",
        "edu", "ee", "eg", "er", "es", "et", "eu", "fi", "fj", "fk", "fm", "fo",
        "fr", "ga", "gb", "gd", "ge", "gf", "gg", "gh", "gi", "gl", "gm", "gn",
        "gov", "gp", "gq", "gr", "gs", "gt", "gu", "gw", "gy", "hk", "hm", "hn",
        "hr", "ht", "hu", "id", "ie", "il", "im", "info", "int", "in", "io",
        "iq", "ir", "is", "it", "je", "jm", "jobs", "jo", "jp", "ke", "kg",
        "kh", "ki", "km", "kn", "kp", "kr", "kw", "ky", "kz", "la", "lb", "lc",
        "li", "lk", "lr", "ls", "lt", "lu", "lv", "ly", "ma", "mc", "md", "me",
        "mg", "mh", "mil", "mk", "ml", "mm", "mn", "mobi", "mo", "mp", "mq",
        "mr", "ms", "mt", "museum", "mu", "mv", "mw", "mx", "my", "mz", "name",
        "na", "nc", "net", "ne", "nf", "ng", "ni", "nl", "no", "np", "nr", "nu",
        "nz", "om", "org", "pa", "pe", "pf", "pg", "ph", "pk", "pl", "pm", "pn",
        "pro", "pr", "ps", "pt", "pw", "py", "qa", "re", "ro", "rs", "ru", "rw",
        "sa", "sb", "sc", "sd", "se", "sg", "sh", "si", "sj", "sk", "sl", "sm",
        "sn", "so", "sr", "st", "su", "sv", "sy", "sz", "tc", "td", "tel", "tf",
        "tg", "th", "tj", "tk", "tl", "tm", "tn", "to", "tp", "travel", "tr",
        "tt", "tv", "tw", "tz", "ua", "ug", "uk", "um", "us", "uy", "uz", "va",
        "vc", "ve", "vg", "vi", "vn", "vu", "wf", "ws", "ye", "yt", "yu", "za",
        "zm", "zw")
    REGEX_URL_PREFIX = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")

    DEFAULT_SCHEME = WEB_SCHEMES[0]
    DEFAULT_SCHEME_PREFIX = DEFAULT_SCHEME + "://"
    DEFAULT_KEEP_HISTORY = True

    keep_history = DEFAULT_KEEP_HISTORY

    known_schemes = set()
    known_tlds = KNOWN_TLDS

    def __init__(self):
        super().__init__()

    def on_start(self):
        self.known_schemes = set()
        self._read_config()
        self._read_tld_databases()
        #self.info("{} TLDs in database".format(len(self.known_tlds)))

    def on_catalog(self):
        self.on_start()

    def on_suggest(self, user_input, items_chain):
        if items_chain:
            return

        url_scheme, corrected_url, default_scheme_applied = self._extract_url_scheme(user_input)
        if not url_scheme:
            return

        if url_scheme not in self.WEB_SCHEMES:
            corrected_url = corrected_url.replace(" ", "%20")

        scheme_registered = self._is_registered_url_scheme(url_scheme)
        if scheme_registered:
            if self.keep_history:
                hit_hint = kp.ItemHitHint.NOARGS
            else:
                hit_hint = kp.ItemHitHint.IGNORE

            suggestions = [self.create_item(
                category=kp.ItemCategory.URL,
                label=corrected_url,
                short_desc="Launch URL: " + corrected_url,
                target=corrected_url,
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=hit_hint)]

            # special case: if scheme is http and was applied by default, offer
            # an https suggestion too
            if default_scheme_applied and url_scheme.lower() == "http":
                https_url = "https" + corrected_url[len(url_scheme):]
                suggestions.append(self.create_item(
                    category=kp.ItemCategory.URL,
                    label=https_url,
                    short_desc="Launch URL: " + https_url,
                    target=https_url,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=hit_hint))

            self.set_suggestions(suggestions)

    def on_execute(self, item, action):
        if item.category() != kp.ItemCategory.URL:
            return

        url_scheme, corrected_url, default_scheme_applied = self._extract_url_scheme(item.target())
        if not url_scheme:
            self.warn("Could not guess URL scheme from URL:", item.target())
            return

        scheme_registered = self._is_registered_url_scheme(url_scheme)
        if not scheme_registered:
            self.warn('URL cannot be launched because its scheme "{}" is not registered'.format(url_scheme))
            return

        if url_scheme in self.WEB_SCHEMES:
            kpu.execute_default_action(self, item, action)
        else:
            kpu.shell_execute(item.target())

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()

    def _read_config(self):
        settings = self.load_settings()
        self.keep_history = settings.get_bool(
            "keep_history", "main", self.DEFAULT_KEEP_HISTORY)

    def _read_tld_databases(self):
        tlds = set()
        for resource in self.find_resources("tld-*.txt"):
            try:
                lines = self.load_text_resource(resource).splitlines()
            except Exception as exc:
                self.warn("Failed to load DB resource \"{}\". Error: {}".format(resource, exc))
                continue
            for line in lines:
                line = line.strip().lower()
                if not line or line[0] in ("#", ";"):
                    continue
                tlds.add(line)

        if not tlds:
            self.warn("Empty TLD database. Falling back to default...")
            self.known_tlds = self.KNOWN_TLDS
        else:
            self.known_tlds = tuple(tlds)

    def _extract_url_scheme(self, user_input):
        user_input = user_input.strip()
        user_input_lc = user_input.lower()

        # does input string starts with a valid scheme name?
        rem = self.REGEX_URL_PREFIX.match(user_input_lc)
        if rem:
            return rem.group(1), user_input, False

        # does input string contain a known ".tld"?
        if any( ("."+tld in user_input_lc for tld in self.known_tlds) ):
            return self.DEFAULT_SCHEME, self.DEFAULT_SCHEME_PREFIX + user_input, True

        # does input string contain a valid IPv4 or IPv6 address?
        groups = re.split(r"/|\[|\]:\d+", user_input)
        for ip_addr in groups:
            if not len(ip_addr):
                continue
            else:
                for af in (socket.AF_INET6, socket.AF_INET):
                    try:
                        socket.inet_pton(af, ip_addr)
                        if af == socket.AF_INET and "." not in ip_addr:
                            # Here, an IPv4 address has been validated but does
                            # not contain any dot. Avoid to pollute the
                            # suggestions list with that.
                            break
                        return self.DEFAULT_SCHEME, self.DEFAULT_SCHEME_PREFIX + user_input, True
                    except OSError:
                        pass
                break

        return None, None, False

    def _is_registered_url_scheme(self, url_scheme):
        if url_scheme in self.known_schemes:
            return True

        if url_scheme in self.WEB_SCHEMES:
            self.known_schemes.add(url_scheme)
            return True

        cmdline, defico = kpu.shell_url_scheme_to_command(url_scheme)
        if cmdline:
            self.known_schemes.add(url_scheme)
            return True

        return False
