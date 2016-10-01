# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import natsort

import collections
import winreg

_KeyPath = collections.namedtuple(
            "KeyPath",
            ("path", "root_name", "root_hkey", "subkey"))

_KeyValue = collections.namedtuple(
            "KeyValue",
            ("name", "data", "data_type"))

class RegBrowser(kp.Plugin):
    """Browse and open Windows Registry keys"""
    ITEMCAT_REGKEY = kp.ItemCategory.USER_BASE + 1
    ITEMCAT_REGVALUE = kp.ItemCategory.USER_BASE + 2

    root_hkeys_dict = {}
    icon_binvalue = None
    icon_strvalue = None

    def __init__(self):
        super().__init__()

    def on_start(self):
        # populate our dict of HKEY_*
        self.root_hkeys_dict = {}
        for name in sorted(dir(winreg)):
            if name.startswith("HKEY_") and name == name.upper():
                value = getattr(winreg, name)

                # full name
                self.root_hkeys_dict[name] = value

                # name without the "HKEY_" prefix
                abbr = name[len("HKEY_"):]
                self.root_hkeys_dict.setdefault(abbr, value)

                # abbreviated name (e.g. "HKCR" for "HKEY_CLASSES_ROOT")
                abbr = "HK" + "".join([x[0] for x in name.split("_")][1:])
                self.root_hkeys_dict.setdefault(abbr, value)

                # value to full name
                self.root_hkeys_dict.setdefault(value, name)

        # load icons
        self.icon_binvalue = self.load_icon(
                    "res://{}/icons/bin.ico".format(self.package_full_name()))
        self.icon_strvalue = self.load_icon(
                    "res://{}/icons/str.ico".format(self.package_full_name()))

    def on_suggest(self, user_input, items_chain):
        suggestions = []

        # initial search
        if not items_chain and len(user_input):
            keypath = self._parse_key(user_input)
            if keypath:
                if self._readable_key(keypath):
                    # the given key path is accessible
                    suggestions, match_method, sort_method = self._enum_key(
                                                                    keypath, "")
                else:
                    # the given key path does not exist or is not readable, in
                    # which case we consider the trailing part of the given path
                    # to be search term that helps matching subkeys by name
                    parent_keypath, search_term = self._parent_key(keypath)
                    if parent_keypath:
                        suggestions, match_method, sort_method = self._enum_key(
                                                    parent_keypath, search_term)

        # key selected, enumerate subkeys and optionally match their name
        # against user_input, if any
        elif items_chain and items_chain[-1].category() == self.ITEMCAT_REGKEY:
            keypath = self._parse_key(items_chain[-1].target())
            if keypath:
                suggestions, match_method, sort_method = self._enum_key(
                                        keypath, user_input, show_error=False)

        if suggestions:
            self.set_suggestions(suggestions, match_method, sort_method)

    def on_execute(self, item, action):
        if item.category() in (self.ITEMCAT_REGKEY, self.ITEMCAT_REGVALUE):
            keypath = self._parse_key(item.target())
            if keypath and item.category() == self.ITEMCAT_REGVALUE:
                keypath = self._parent_key(keypath)[0]

            if keypath and self._readable_key(keypath):
                try:
                    with winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            "Software\\Microsoft\\Windows\\CurrentVersion\\Applets\\Regedit",
                            access=winreg.KEY_WRITE) as hkey:
                        winreg.SetValueEx(
                            hkey, "LastKey", 0, winreg.REG_SZ, keypath.path)
                except OSError as exc:
                    self.warn("Failed to initialize regedit. Error:", str(exc))
                    return

                try:
                    kpu.shell_execute(
                        "regedit.exe", args=("/m", ),
                        try_runas=True, detect_nongui=False)
                except Exception as exc:
                    self.warn("Failed to launch regedit. Error:", str(exc))

    def _parse_key(self, keypath):
        # normalize
        keypath = keypath.lstrip().replace("/", "\\")
        while "\\\\" in keypath:
            keypath = keypath.replace("\\\\", "\\")
        keypath = keypath.strip("\\")

        # extract the root key from the rest of the path...
        rootkey, *subkey = keypath.split("\\", maxsplit=1)
        rootkey = rootkey.upper()
        # subkey is a list if there was no "\\" in keypath
        subkey = "" if not len(subkey) else subkey[0]

        # ... and try to match it
        try:
            rootkey_value = self.root_hkeys_dict[rootkey]
            rootkey_fqname = self.root_hkeys_dict[rootkey_value]
            full_path = "\\".join((rootkey_fqname, subkey)).rstrip("\\")
            return _KeyPath(full_path, rootkey_fqname, rootkey_value, subkey)
        except KeyError:
            return None

    def _parent_key(self, keypath):
        if "\\" in keypath.path:
            elems = keypath.path.split("\\")
            search_term = elems[-1]
            parent_keypath = self._parse_key("\\".join(elems[0:-1]))
            if parent_keypath:
                return (parent_keypath, search_term)
        return (None, None)

    def _readable_key(self, keypath):
        try:
            with winreg.OpenKey(keypath.root_hkey, keypath.subkey) as hkey:
                return True
        except OSError:
            pass
        return False

    def _enum_key(self, keypath, user_input="", show_error=True):
        def _sort(sequence, do_natsort):
            if do_natsort:
                yield from natsort.natsorted(
                    sequence,
                    alg=natsort.ns.GROUPLETTERS | natsort.ns.LOCALE | natsort.ns.IGNORECASE)
            else:
                yield from sequence

        user_input = user_input.strip()
        if not len(user_input):
            user_input = None

        items = []
        if user_input is None:
            match_method = kp.Match.ANY
            sort_method = kp.Sort.NONE
        else:
            match_method = kp.Match.FUZZY
            sort_method = kp.Sort.SCORE_DESC

        # open registry key
        try:
            hkey = winreg.OpenKey(keypath.root_hkey, keypath.subkey)
        except OSError as exc:
            if show_error:
                items.append(self.create_error_item(
                    label=keypath.path,
                    short_desc="Registry key not found: " + keypath.path))
            return (items, kp.Match.ANY, kp.Sort.NONE)

        # enumerate keys and values
        subkeys = []
        values = {}
        try:
            idx = 0
            while True:
                try:
                    name = winreg.EnumKey(hkey, idx)
                    idx += 1
                    if len(name) and (
                            user_input is None or
                            kpu.fuzzy_score(user_input, name) > 0):
                        subkeys.append(name)
                except OSError:
                    break

            # enum values
            idx = 0
            while True:
                try:
                    val = _KeyValue(*winreg.EnumValue(hkey, idx))
                    idx += 1
                    if len(val.name) and (
                            user_input is None or
                            kpu.fuzzy_score(user_input, val.name) > 0):
                        values[val.name] = val
                except OSError:
                    break
        finally:
            hkey.Close()

        for subkey_name in _sort(subkeys, user_input is None):
            full_path = keypath.path + "\\" + subkey_name
            items.append(self.create_item(
                category=self.ITEMCAT_REGKEY,
                label=subkey_name,
                short_desc=full_path,
                target=full_path,
                args_hint=kp.ItemArgsHint.ACCEPTED,
                hit_hint=kp.ItemHitHint.IGNORE,
                loop_on_suggest=True))
        for value_name in _sort(values.keys(), user_input is None):
            full_path = keypath.path + "\\" + value_name
            if values[value_name].data_type in (
                    winreg.REG_SZ, winreg.REG_MULTI_SZ, winreg.REG_EXPAND_SZ,
                    winreg.REG_LINK, winreg.REG_RESOURCE_LIST,
                    winreg.REG_FULL_RESOURCE_DESCRIPTOR,
                    winreg.REG_RESOURCE_REQUIREMENTS_LIST):
                icon = self.icon_strvalue
            else:
                icon = self.icon_binvalue
            items.append(self.create_item(
                category=self.ITEMCAT_REGVALUE,
                label=value_name,
                short_desc=full_path,
                target=full_path,
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.IGNORE,
                loop_on_suggest=False,
                icon_handle=icon))

        return (items, match_method, sort_method)
