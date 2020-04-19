# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha_api
import keypirinha as kp
import keypirinha_util as kpu
import globex
import filefilter

from collections import namedtuple, OrderedDict
import time
import os
import re
import traceback

TEMPLATE_TAG_SEP = ("{", "}")
TEMPLATE_TAG_REGEX = re.compile(
    r"(?:" +
        # {{tag}} form
        r"(?P<escaped_literal_tag>" +
            re.escape(TEMPLATE_TAG_SEP[0]) +
            r"(?P<literal_tag>" +
                re.escape(TEMPLATE_TAG_SEP[0]) +
                r"(?P<literal_tag_name>[a-z0-9_]+)" +
                re.escape(TEMPLATE_TAG_SEP[1]) +
            r")" +
            re.escape(TEMPLATE_TAG_SEP[1]) +
        r")" +
        r"|" +
        # {tag} form
        r"(?P<tag>" +
            re.escape(TEMPLATE_TAG_SEP[0]) +
            r"(?P<tag_name>[a-z0-9_]+)" +
            re.escape(TEMPLATE_TAG_SEP[1]) +
        r")" +
    r")")

ScanProfile = namedtuple("ScanProfile", (
    "label", "paths", "max_depth",
    "include_hidden", "include_dirs", "include_files",
    "filters", "filters_default",
    "trim_extensions",
    "file_item_label", "file_item_desc",
    "dir_item_label", "dir_item_desc",
    "callback", "open_with"))

class LazyItemLabelFormatter:
    def __init__(self, entry, profile, plugin):
        self._entry = entry
        self._profile = profile
        self._plugin = plugin

    @classmethod
    def list_invalid_tags(cls, template):
        invalid_tags = []
        for rem in TEMPLATE_TAG_REGEX.finditer(template):
            pos = rem.start()
            if rem.group("escaped_literal_tag"):
                continue # skip {{name}} form
            if not cls.has_tag(rem.group("tag_name")):
                invalid_tags.append(rem.group("tag"))
        return invalid_tags

    def format(self, template, fallback=""):
        label = ""
        if template:
            copy_start = 0
            for rem in TEMPLATE_TAG_REGEX.finditer(template):
                idx = rem.start()

                # get tag's value
                if rem.group("escaped_literal_tag"):
                    # insert {{name}} form as {name}
                    value = rem.group("literal_tag")
                else:
                    attr = rem.group("tag_name")
                    try:
                        value = self.get_tag_value(attr)
                    except AttributeError:
                        self._plugin.warn(
                            "Invalid tag {}{}{} found in profile {}.".format(
                            TEMPLATE_TAG_SEP[0], rem.group("tag"),
                            TEMPLATE_TAG_SEP[1],
                            self._profile.label))
                        continue

                # copy the preceding content before inserting tag's value
                if copy_start < idx:
                    label += template[copy_start:idx]
                copy_start = rem.end()

                label += value

            if copy_start < len(template):
                label += template[copy_start:]
            label = label.strip()

        return label if label else fallback

    @classmethod
    def has_tag(cls, tag_name):
        return hasattr(cls, "_make_" + tag_name)

    def get_tag_value(self, tag_name):
        if not self.has_tag(tag_name):
            raise AttributeError(tag_name)

        # try to get the cached version first
        try:
            return getattr(self, tag_name)
        except AttributeError:
            pass

        # otherwise, lazy-init then cache it
        try:
            meth = getattr(self, "_make_" + tag_name)
        except AttributeError:
            raise AttributeError(tag_name)
        value = meth()
        setattr(self, tag_name, value)

        return value

    def _make_package(self):
        return self._plugin.package_full_name()

    def _make_profile(self):
        return self._profile.label

    def _make_name(self):
        return self._entry.name

    def _make_clean_name(self):
        # note: trim_extensions is already normalized
        norm_name = os.path.normcase(self._entry.name)
        for ext in self._profile.trim_extensions:
            if norm_name.endswith(ext):
                return self._entry.name[0:-len(ext)]
        return self._entry.name

    def _make_title(self):
        title, ext = os.path.splitext(self._entry.name)
        while ext:
            title, ext = os.path.splitext(title)
        return title

    def _make_titlex(self):
        return os.path.splitext(self._entry.name)[0]

    def _make_ext(self):
        return os.path.splitext(self._entry.name)[1]

    def _make_exts(self):
        exts = ""
        title, ext = os.path.splitext(self._entry.name)
        while 1:
            if not ext:
                break
            exts += ext
            title, ext = os.path.splitext(title)
        return exts

    def _make_drive(self):
        drive = os.path.splitdrive(self._entry.path)[0]
        if drive:
            drive += os.sep # splitdrive() returns "C:", we want "C:\"
        return drive

    def _make_dir(self):
        return os.path.dirname(self._entry.path)

    def _make_dir1(self):
        dirname = os.path.dirname(self._entry.path)
        return os.path.basename(dirname)

    def _make_dir2(self):
        dirname = os.path.dirname(self._entry.path)
        dirname = os.path.dirname(dirname)
        return os.path.basename(dirname)

    def _make_dir3(self):
        dirname = os.path.dirname(self._entry.path)
        dirname = os.path.dirname(dirname)
        dirname = os.path.dirname(dirname)
        return os.path.basename(dirname)

    def _make_2dirs(self):
        return os.path.join(self._make_dir2(), self._make_dir1())

    def _make_3dirs(self):
        return os.path.join(self._make_dir3(), self._make_dir2(),
                            self._make_dir1())

def default_scan_callback(entry, profile, plugin):
    if not profile.include_hidden and entry.is_hidden():
        return None
    if not profile.include_dirs and entry.is_dir():
        return None
    if not profile.include_files and not entry.is_dir():
        return None

    include = profile.filters_default
    for filter in profile.filters:
        if filter.match(entry):
            include = filter.inclusive
            break
    if not include:
        return None

    if entry.is_dir():
        item_label_tmpl = profile.dir_item_label
        item_desc_tmpl = profile.dir_item_desc
    else:
        item_label_tmpl = profile.file_item_label
        item_desc_tmpl = profile.file_item_desc

    if profile.open_with:
        open_with = profile.open_with.replace('{}', entry.path)
    else:
        open_with = None

    formatter = LazyItemLabelFormatter(entry, profile, plugin)
    item_label = formatter.format(item_label_tmpl, fallback=entry.name)
    item_desc = formatter.format(item_desc_tmpl, fallback="")

    return plugin.create_item(
        category=kp.ItemCategory.FILE,
        label=item_label,
        short_desc=item_desc, # path is displayed on GUI if desc is empty
        target=entry.path,
        args_hint=kp.ItemArgsHint.ACCEPTED,
        hit_hint=kp.ItemHitHint.KEEPALL,
        data_bag=open_with)

try:
    from FilesCatalog import filescatalog_user_callbacks

    # monkey-patch user's module so it easily gets access to some tools
    filescatalog_user_callbacks._filefilter = filefilter
    filescatalog_user_callbacks._globex = globex
    filescatalog_user_callbacks._TEMPLATE_TAG_SEP = TEMPLATE_TAG_SEP
    filescatalog_user_callbacks._TEMPLATE_TAG_REGEX = TEMPLATE_TAG_REGEX
    filescatalog_user_callbacks._LazyItemLabelFormatter = LazyItemLabelFormatter
    filescatalog_user_callbacks._default_scan_callback = default_scan_callback

    # notify user's module that we are done
    try:
        func = getattr(filescatalog_user_callbacks, "on_imported")
        try:
            func()
        except:
            traceback.print_exc()
    except AttributeError:
        pass
except ImportError:
    traceback.print_exc()
    filescatalog_user_callbacks = None

class FilesCatalog(kp.Plugin):
    """A plugin to catalog items from the file system"""

    CONFIG_SECTION_MAIN = "main"
    CONFIG_SECTION_BROWSING = "browsing"
    CONFIG_SECTION_PROFILE = "profile/"

    MAX_PROFILE_INHERITANCE_DEPTH = 5

    DEFAULT_CATALOG_LIMIT = 100_000
    DEFAULT_CONFIG_DEBUG = False
    DEFAULT_ITEM_LABEL = "{clean_name}"
    DEFAULT_SHOW_DIRS_FIRST = True
    DEFAULT_SHOW_HIDDEN_FILES = False
    DEFAULT_SHOW_SYSTEM_FILES = False

    catalog_limit = DEFAULT_CATALOG_LIMIT
    config_debug = DEFAULT_CONFIG_DEBUG
    show_dirs_first = DEFAULT_SHOW_DIRS_FIRST
    show_hidden_files = DEFAULT_SHOW_HIDDEN_FILES
    show_system_files = DEFAULT_SHOW_SYSTEM_FILES
    profiles = OrderedDict()

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_config()

    def on_catalog(self):
        start = time.perf_counter()
        catalog = []
        scanned_profiles = OrderedDict()

        if self.profiles:
            self.info("Cataloging {} profile{}...".format(
                      len(self.profiles), "s"[len(self.profiles)==1:]))

        for profile_name, profile in self.profiles.items():
            items_count = 0
            sub_start = time.perf_counter()

            for pattern in profile.paths:
                # we call splitdrive() because a UNC may have a '?' char in it
                # like in \\?\C:\dir\file
                has_magic = globex.has_magic(os.path.splitdrive(pattern)[1])

                # if this is not a pattern, warn the user in case path is not
                # found/readable
                if not has_magic:
                    is_dir = os.path.isdir(pattern)
                    if not is_dir and not os.path.exists(pattern):
                        self.warn("Path not found in profile {}: {}".format(
                                  profile.label, pattern))
                        continue

                    # If path points to a directory, assume only its direct
                    # content must be scanned.  Also, globex.iglobex() would
                    # return *pattern* as-is if no wildcard were appended.
                    if is_dir:
                        pattern = os.path.join(pattern, "*")

                for entry in globex.iglobex(
                        pattern,
                        recursivity=profile.max_depth,
                        include_hidden=profile.include_hidden):
                    item = profile.callback(entry, profile, self)
                    if item and isinstance(item, keypirinha_api.CatalogItem):
                        catalog.append(item)
                        items_count += 1
                        if len(catalog) >= self.catalog_limit:
                            self.warn((
                                'Stopping scan of profile "{}" due to ' +
                                'catalog_limit reached ({} items).').format(
                                profile.label, self.catalog_limit))
                            break

            scanned_profiles[profile.label] = (items_count,
                                               time.perf_counter() - sub_start)

        if self.profiles:
            for label, (count, elapsed) in scanned_profiles.items():
                self.info(
                    "Profile {}: found {} item{} in {:.1f} seconds".format(
                    label, count, "s"[count==1:], elapsed))

        sub_start = time.perf_counter()
        self.set_catalog(catalog)

        if self.profiles:
            if catalog:
                self.info("Cataloged {} item{} in {:.1f} seconds".format(
                          len(catalog), "s"[len(catalog)==1:],
                          time.perf_counter() - sub_start))
            self.info(
                "Total: {} item{} found and cataloged in {:.1f} seconds".format(
                len(catalog), "s"[len(catalog)==1:],
                time.perf_counter() - start))

    def on_suggest(self, user_input, items_chain):
        if items_chain and items_chain[-1].category() == kp.ItemCategory.FILE:
            current_item = items_chain[-1]
            path = current_item.target()
            if os.path.isdir(path):
                # File is a directory
                suggestions, match_method, sort_method = self._browse_dir(path)
                self.set_suggestions(suggestions, match_method, sort_method)
            elif os.path.splitext(path)[1].lower() == ".lnk":
                # File is a link
                try:
                    link_props = kpu.read_link(path)
                    if os.path.isdir(link_props['target']):
                        # Link points to a directory
                        dir_target = link_props['target']
                        suggestions, match_method, sort_method = self._browse_dir(
                                            dir_target, check_base_dir=False)
                        self.set_suggestions(suggestions, match_method, sort_method)
                except:
                    pass
            else:
                clone = items_chain[-1].clone()
                clone.set_args(user_input)
                self.set_suggestions([clone])

    def on_execute(self, item, action):
        if item.data_bag():
            # open with a custom command
            parts = re.findall(r'(?=\s|\A)\s*([^" ]+|"[^"]*")(?=\s|\Z)', item.data_bag(), re.U)
            if len(parts) > 0:
                command, *params = parts
                kpu.shell_execute(command, params)
            else:
                self.info("Cannot open item with: '%s', parsed as %s" % (item.data_bag(), parts))
        else:
            kpu.execute_default_action(self, item, action)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            if self._read_config():
                self.on_catalog()

    def _read_config(self):
        config_changed = False
        settings = self.load_settings()
        profiles_map = OrderedDict() # profile name -> profile label
        profiles_def = OrderedDict() # profile name -> settings dict

        old_profiles = self.profiles
        self.profiles = OrderedDict()

        # main
        self.config_debug = settings.get_bool(
            "debug", section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_CONFIG_DEBUG)
        catalog_limit = settings.get_int(
            "catalog_limit", section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_CATALOG_LIMIT, min=5_000, max=300_000)
        if catalog_limit != self.catalog_limit:
            self.catalog_limit = catalog_limit
            config_changed = True

        # Ideally, changing these settings shouldn't trigger recatalogging.
        # However, this seems to be necessary due to the way that filter
        # comparison works.
        # If config_changed is omitted for these settings an error will be
        # thrown by filefilter.py. Still don't fully understand why.
        old_browsing_defaults = [
            self.show_dirs_first,
            self.show_hidden_files,
            self.show_system_files]
        self.show_dirs_first = settings.get_bool(
            "show_dirs_first", "browsing", self.DEFAULT_SHOW_DIRS_FIRST)
        self.show_hidden_files = settings.get_bool(
            "show_hidden_files", "browsing", self.DEFAULT_SHOW_HIDDEN_FILES)
        self.show_system_files = settings.get_bool(
            "show_system_files", "browsing", self.DEFAULT_SHOW_SYSTEM_FILES)
        browsing_defaults = [
            self.show_dirs_first,
            self.show_hidden_files,
            self.show_system_files]
        if not config_changed and old_browsing_defaults != browsing_defaults:
            config_changed = True

        # read profiles names and validate them
        # note: ini section names in Keypirinha are case-sensitive, we want
        # profile names to be case-insensitive
        for section_name in settings.sections():
            if not section_name.lower().startswith(self.CONFIG_SECTION_PROFILE):
                continue

            profile_label = section_name[len(self.CONFIG_SECTION_PROFILE):]
            profile_label = profile_label.strip()
            profile_name = profile_label.lower()

            if not profile_name:
                self.warn('Ignoring empty profile name (section "{}").'.format(
                    section_name))
                continue

            forbidden_chars = ":;,/|\\"
            if any(c in forbidden_chars for c in profile_label):
                self.warn((
                    'Forbidden character(s) found in profile name "{}". ' +
                    'Forbidden characters list "{}"').format(
                    profile_label, forbidden_chars))
                continue

            if profile_name in profiles_map:
                self.warn('Ignoring "{}" defined twice.'.format(
                    section_name))
                continue

            profiles_map[profile_name] = section_name
            profiles_def[profile_name] = {}

            profiles_def[profile_name]['label'] = profile_label

            profiles_def[profile_name]['inherit'] = settings.get_stripped(
                "inherit", section=section_name, fallback="").strip().lower()
            if not profiles_def[profile_name]['inherit']:
                profiles_def[profile_name]['inherit'] = None

        # read and check profiles inheritance
        for profile_name, section_name in profiles_map.items():
            inheritance = [profile_name]
            current_profile = profile_name
            while 1:
                if not profiles_def[current_profile]['inherit']:
                    break

                if profiles_def[current_profile]['inherit'] not in profiles_map:
                    self.err((
                        'Unknown profile to inherit from found in "{}". ' +
                        'Please reconfigure.').format(
                        section_name))
                    return None

                if profiles_def[current_profile]['inherit'] in inheritance:
                    self.err((
                        'Infinite inheritance loop detected in "{}". ' +
                        'Please reconfigure.').format(
                        section_name))
                    return None

                inheritance.append(profiles_def[current_profile]['inherit'])

                if len(inheritance) > self.MAX_PROFILE_INHERITANCE_DEPTH:
                    self.err((
                        'Too deep inheritance depth detected in "{}". ' +
                        'Please reconfigure.').format(
                        section_name))
                    return None

                # go up in the inheritance lineage
                current_profile = profiles_def[current_profile]['inherit']

            profiles_def[profile_name]['inherit'] = tuple(inheritance[1:])

        # read profiles settings
        for profile_name, section_name in profiles_map.items():
            profdef = profiles_def[profile_name]

            # activated
            profdef['enabled'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_bool", "activate", fallback=False)

            # paths
            profdef['paths'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_multiline", "paths", fallback=[],
                keep_empty_lines=False)
            if not profdef['paths'] and profdef['enabled']:
                profdef['enabled'] = False
                self.warn(
                    'Deactivate "{}" because its paths value is empty'.format(
                        section_name))
            if profdef['paths']:
                paths = profdef['paths']
                profdef['paths'] = []

                for p in paths:
                    p = os.path.normpath(p)
                    if not os.path.splitdrive(p)[0]:
                        self.warn((
                            'Skipping non-absolute path specified in "{}": ' +
                            '{}').format(section_name, p))
                    else:
                        profdef['paths'].append(p)

                profdef['paths'] = tuple(profdef['paths'])

            # max_depth
            profdef['max_depth'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_int", "max_depth", fallback=None)
            if profdef['max_depth'] is None:
                profdef['max_depth'] = -1
            elif profdef['max_depth'] < -1:
                profdef['max_depth'] = -1

            # include_hidden
            profdef['include_hidden'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_bool", "include_hidden", fallback=False)

            # include_dirs
            profdef['include_dirs'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_bool", "include_dirs", fallback=False)

            # include_files
            profdef['include_files'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_bool", "include_files", fallback=True)

            # file_item_label, file_item_desc, dir_item_label and dir_item_desc
            # CAUTION: order of the keys in the loop matters to apply defaults
            for key in ("file_item_label", "file_item_desc",
                        "dir_item_label", "dir_item_desc"):
                profdef[key] = self._read_profile_setting(
                    profiles_map, profiles_def, settings,
                    profile_name, "get_stripped", key, fallback=None)

                if profdef[key] and "{" not in profdef[key]:
                    self.warn((
                        '{} value of "{}" does not contain any placeholder. ' +
                        'Falling back to default').format(key, section_name))
                    profdef[key] = None

                # apply defaults
                if not profdef[key]:
                    if key == "file_item_label":
                        profdef[key] = "{clean_name}"

                        # DEBUG
                        #tags = (
                        #    "{package}", "{profile}",
                        #    "{clean_name}", "{name}", "{title}", "{titlex}",
                        #    "{ext}", "{exts}",
                        #    "{drive}", "{dir}", "{dir1}", "{dir2}", "{dir3}",
                        #    "{2dirs}", "{3dirs}")
                        #profdef[key] = "{{ {} }} {{} " # to test parser
                        #profdef[key] += " ".join(
                        #    ["{" + t + "}[" + t + "]" for t in tags])
                    elif key.startswith("dir_"):
                        from_key = "file_" + key[len("dir_"):]
                        profdef[key] = profdef[from_key]
                    else:
                        profdef[key] = None

                if profdef[key]:
                    invalid_tags = \
                        LazyItemLabelFormatter.list_invalid_tags(profdef[key])
                    if invalid_tags:
                        self.warn((
                            "Invalid tag(s) found in {}: {}. " +
                            "Falling back to default").format(
                            section_name, ", ".join(invalid_tags)))
                        profdef[key] = None

            # filters
            filters = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_multiline", "filters", fallback=[],
                keep_empty_lines=False)
            profdef['filters'] = []
            for expression in filters:
                if not expression:
                    continue
                try:
                    profdef['filters'].append(
                        filefilter.create_filter(expression))
                except ValueError as exc:
                    self.warn((
                        'Ignoring invalid filter "{}" from "{}". ' +
                        'Error: {}').format(expression, section_name, str(exc)))
                    continue

            # filters - define the default filtering behavior
            # We stick to the following rules for that:
            # * if *filters* is empty, items are INCLUDED
            # * if *filters* contains only negative filters, non-matching items
            #   are INCLUDED
            # * otherwise, default behavior is to EXCLUDE non-matching items
            profdef['filters_default'] = True # if empty or has negative
            if profdef['filters']:
                for flt in profdef['filters']:
                    if flt.inclusive:
                        profdef['filters_default'] = False
                        break

            # filters - cleanup according to the rules stated above
            # * this allows to optimize (speed) filtering
            # * if filters list is not empty and contains mixed filters, we
            #   can remove all the trailing negative filters if any
            if not profdef['filters_default']: # if "non-empty and mixed filters"
                count = 0
                while profdef['filters'] and not profdef['filters'][-1].inclusive:
                    profdef['filters'].pop()
                    count += 1
                if count:
                    self.warn((
                        'Ignoring trailing negative filter(s) from "{}". ' +
                        'Read the inline documentation of the "filters" ' +
                        'setting for more info').format(section_name))

            profdef['filters'] = tuple(profdef['filters']) # memory usage

            # trim_extensions
            # note: we do not use PATHEXT as a default because user may need to
            # differentiate between an exe file and a script with the same name
            # for example.
            trim_extensions = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_stripped", "trim_extensions",
                fallback=".lnk") # + os.environ.get("PATHEXT", ""))
            trim_extensions = trim_extensions.strip()
            trim_extensions = os.path.normcase(trim_extensions)
            if os.sep in trim_extensions:
                profdef['trim_extensions'] = ()
                self.warn(
                    'Ignoring incorrect trim_extensions in "{}"'.format(
                        section_name))
            else:
                profdef['trim_extensions'] = frozenset(
                    filter(None, re.split(r'[\s\;]+', trim_extensions)))

            # open_with
            profdef['open_with'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_stripped", "open_with",
                fallback="").strip()
            if not profdef['open_with']:
                profdef['open_with'] = None

            # python_callback
            profdef['callback'] = self._read_profile_setting(
                profiles_map, profiles_def, settings,
                profile_name, "get_stripped", "python_callback",
                fallback="").strip()
            if not profdef['callback']:
                profdef['callback'] = None
            else:
                try:
                    profdef['callback'] = getattr(filescatalog_user_callbacks,
                                                  profdef['callback'])
                    if not callable(profdef['callback']):
                        profdef['callback'] = None
                        self.warn((
                            'Ignoring incorrect python_callback in "{}". ' +
                            'Not a callable.').format(section_name))
                except AttributeError:
                    profdef['callback'] = None
                    self.warn(
                        'Ignoring incorrect python_callback in "{}"'.format(
                        section_name))
            if not profdef['callback']:
                profdef['callback'] = default_scan_callback

        # create profile objects...
        # ... now that we have roughly validated the settings
        self.profiles = OrderedDict()
        for profile_name, profile_def in profiles_def.items():
            if profile_def['enabled']:
                del profile_def['enabled']
                del profile_def['inherit']
                self.profiles[profile_name] = ScanProfile(**profile_def)

        # print profiles settings
        if self.config_debug and self.profiles:
            self._print_profiles()

        if not config_changed and self.profiles != old_profiles:
            config_changed = True

        return config_changed

    def _read_profile_setting(self, profiles_map, profiles_def, settings,
                              profile_name, meth, key, *, fallback=None,
                              **kwargs):
        meth = getattr(settings, meth)

        if key in ("activate", "inherit"): # non-inheritable settings
            profile_names = (profile_name, )
        else:
            profile_names = (profile_name, ) + \
                            profiles_def[profile_name]['inherit']

        for sub_profile_name in profile_names:
            sub_profile_section = profiles_map[sub_profile_name]
            if settings.has(key, section=sub_profile_section):
                return meth(key=key, section=sub_profile_section,
                            fallback=fallback, **kwargs)

        return fallback

    def _print_profiles(self):
        indent = 3
        max_key_len = len(max(("internal_name", ) + ScanProfile._fields,
                          key=len))

        def _sprint_pair(name, value=None):
            out = " " * indent

            if name is not None:
                out += name

            if value is not None:
                padding = max_key_len - (len(name) if name else 0)
                if padding < 0:
                    padding = 0
                out += " " * (padding + 1)
                if isinstance(value, str):
                    out += value
                else:
                    out += str(value)

            return out

        log = "Activated profiles ({}):\n".format(len(self.profiles))
        for name, profile in self.profiles.items():
            log += '{} Profile "{}":\n'.format("*" * (indent - 1),
                                               profile.label)
            log += _sprint_pair("internal_name", '"{}"'.format(name)) + "\n"

            profile_dict = profile._asdict()
            for key in ("include_hidden", "include_dirs", "include_files",
                        "max_depth", "trim_extensions",
                        "file_item_label", "file_item_desc",
                        "dir_item_label", "dir_item_desc",
                        "callback"):
                value = profile_dict[key]
                if value is None:
                    value = "<none>"
                elif isinstance(value, bool):
                    value = "no" if not value else "yes"
                elif isinstance(value, int):
                    pass
                elif isinstance(value, str):
                    value = '"{}"'.format(value)
                elif isinstance(value, (list, tuple, set, frozenset)):
                    value = [repr(v) for v in value]
                    value = "(" + ", ".join(value) + ")"
                elif callable(value):
                    try:
                        value = value.__name__
                    except AttributeError:
                        value = repr(value)
                else:
                    value = str(value)
                log += _sprint_pair(key, value) + "\n"

            for key in ("paths", "filters"):
                profile_attr = profile_dict[key]
                if not profile_attr:
                    log += _sprint_pair(key, "<none>") + "\n"
                else:
                    log += _sprint_pair(key, profile_attr[0]) + "\n"
                    for idx in range(1, len(profile_attr)):
                        log += _sprint_pair(None, profile_attr[idx]) + "\n"

            log +=  "\n"

        self.info(log)

    def _browse_dir(self, base_dir, check_base_dir=True, search_terms="", store_score=False):
        base_dir = self._safe_normpath(base_dir)
        return kpu.browse_directory(self,
                                    base_dir,
                                    check_base_dir=check_base_dir,
                                    search_terms=search_terms,
                                    store_score=store_score,
                                    show_dirs_first=self.show_dirs_first,
                                    show_hidden_files=self.show_hidden_files,
                                    show_system_files=self.show_system_files)

    def _safe_normpath(self, path):
        # If the given path is not a complete UNC yet, os.path.normpath() will
        # reduce the trailing \\ prefix to \. Here, we want to preserve the
        # meaning of the prefix specified by the user.
        #
        # Examples:
        #   os.path.normpath("//server/share") == "\\\\server\\share"
        #   os.path.normpath("\\\\server") == "\\server"
        #   os.path.normpath("\\\\\\server\\share") == "\\server\\share" (WRONG)
        prefix_seps = 0
        for idx in range(min(2, len(path))):
            if path[idx] not in (os.sep, os.altsep):
                break
            prefix_seps += 1

        path = os.path.normpath(path)
        if prefix_seps > 1:
            path = (os.sep * 2) + path.lstrip(os.sep)

        return path
