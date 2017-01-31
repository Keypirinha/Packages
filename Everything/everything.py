# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
from .lib import everything_ipc as evipc
import os.path
import threading
import time
import traceback

class Everything(kp.Plugin):
    """Search for files and folders via Everything"""
    CONFIG_SECTION_MAIN = "main"
    CONFIG_SECTION_DEFAULTS = "defaults"
    CONFIG_SECTION_DEFAULT_SEARCH = "default_search"
    CONFIG_SECTION_SEARCH = "search"

    DEFAULT_ITEM_LABEL_FORMAT = "{plugin_name}: {search_name}"
    DEFAULT_ENABLE_DEFAULT_SEARCHES = True
    DEFAULT_ALLOW_EMPTY_SEARCH = False
    DEFAULT_EXPECT_REGEX = False

    mutex = None
    searches = {}

    def __init__(self):
        super().__init__()
        self.mutex = threading.Lock()
        self.searches = {}

    def on_start(self):
        self._read_config()

    def on_catalog(self):
        self._read_config()
        catalog = []
        for search_name, search in self.searches.items():
            catalog.append(self.create_item(
                category=kp.ItemCategory.REFERENCE,
                label=search['item_label'],
                short_desc=search['description'],
                target=search_name,
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS))
        catalog.append(self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label="{}: {}".format(self.friendly_name(), "Rebuild DB"),
            short_desc="Ask Everything to rebuild its database (v1.4+ only)",
            target="rebuild_db",
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.NOARGS))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if not items_chain:
            return

        initial_item = items_chain[0]
        current_item = items_chain[-1]

        # support for pre-2.9 items
        if (current_item.category() == kp.ItemCategory.KEYWORD and
                current_item.target() in ("search", "search_regex")):
            if not len(user_input):
                return
            try:
                with self.mutex:
                    self.set_suggestions(
                        self._search(
                            user_input,
                            current_item.target() == "search_regex"),
                        kp.Match.ANY, kp.Sort.NONE)
            except evipc.EverythingNotFound:
                self.warn("Everything instance not found")
            except:
                self.err("Something bad happened while requesting Everything to perform your search.")
                traceback.print_exc()

        # handle "search" and "default_search" items defined in config
        elif current_item.category() == kp.ItemCategory.REFERENCE:
            if not initial_item.target() in self.searches.keys():
                return

            current_search_name = initial_item.target()
            current_search = self.searches[current_search_name]
            if not current_search:
                return
            if not current_search['allow_empty_search'] and not len(user_input):
                return

            # avoid flooding Everything with too much unnecessary queries in
            # case user is still typing
            if len(user_input) > 0 and self.should_terminate(0.250):
                return

            # query
            search_string = current_search['pattern'].replace("%s", user_input)
            try:
                with self.mutex:
                    self.set_suggestions(
                        self._search(search_string, current_search['is_regex']),
                        kp.Match.ANY, kp.Sort.NONE)
            except evipc.EverythingNotFound:
                self.warn("Everything instance not found")
            except:
                self.err("Something bad happened while requesting Everything to perform your search.")
                traceback.print_exc()

        # handle file system browsing
        elif current_item.category() == kp.ItemCategory.FILE:
            if os.path.isdir(current_item.target()):
                suggestions, match_method, sort_method = self._browse_dir(
                                    current_item.target(), check_base_dir=False,
                                    search_terms=user_input)
                self.set_suggestions(suggestions, match_method, sort_method)
            elif os.path.exists(current_item.target()):
                clone = current_item.clone()
                clone.set_args(user_input)
                clone.set_loop_on_suggest(False)
                self.set_suggestions([clone], kp.Match.ANY, kp.Sort.NONE)
            else:
                self.set_suggestions([self.create_error_item(
                    label=user_input,
                    short_desc="File/Dir not found: " + current_item.target())])

    def on_execute(self, item, action):
        if item.category() == kp.ItemCategory.FILE:
            kpu.execute_default_action(self, item, action)
        elif item.category() == kp.ItemCategory.KEYWORD and item.target() == "rebuild_db":
            with self.mutex:
                try:
                    client = evipc.Client()
                    client.rebuild_db()
                except evipc.EverythingNotFound:
                    self.warn("Everything instance not found")
                except:
                    self.err("Something bad happened while requesting Everything to perform your search.")
                    traceback.print_exc()

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self.on_catalog()

    def _search(self, terms, is_regex=False):
        max_results = kp.settings().get_int("max_results", "gui", 1000, 100, 1000)
        client = evipc.Client()
        res_list = client.query(terms, is_regex=is_regex,
                                max_results=max_results,
                                should_terminate_cb=self.should_terminate)
        catitems = []
        idx = 0
        for item_full_path, item_is_file in res_list:
            item_label = os.path.basename(item_full_path)
            if not item_label:
                item_label = item_full_path
            catitems.append(self.create_item(
                category=kp.ItemCategory.FILE,
                label=item_label,
                short_desc="",
                target=item_full_path,
                args_hint=kp.ItemArgsHint.ACCEPTED,
                hit_hint=kp.ItemHitHint.KEEPALL,
                loop_on_suggest=True))
            idx += 1
            if idx % 10 == 0 and self.should_terminate():
                return []
        return catitems

    def _browse_dir(self, base_dir, check_base_dir=True, search_terms=""):
        return kpu.browse_directory(self,
                                    base_dir,
                                    check_base_dir=check_base_dir,
                                    search_terms=search_terms,
                                    show_dirs_first=True,
                                    show_hidden_files=True,
                                    show_system_files=True)

    def _read_config(self):
        self.searches = {}

        settings = self.load_settings()

        # [main]
        item_label_format = settings.get_stripped(
            "item_label_format",
            section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ITEM_LABEL_FORMAT)
        enable_default_searches = settings.get_bool(
            "enable_default_searches",
            section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ENABLE_DEFAULT_SEARCHES)

        # [default]
        default_allow_empty_search = settings.get_bool(
            "allow_empty_search",
            section=self.CONFIG_SECTION_DEFAULTS,
            fallback=self.DEFAULT_ALLOW_EMPTY_SEARCH)
        default_is_regex = settings.get_bool(
            "is_regex",
            section=self.CONFIG_SECTION_DEFAULTS,
            fallback=self.DEFAULT_EXPECT_REGEX)

        # read [search/*] and [default_search/*] sections
        for section in settings.sections():
            if section.lower().startswith(self.CONFIG_SECTION_DEFAULT_SEARCH + "/"):
                if not enable_default_searches:
                    continue
                search_label = section[len(self.CONFIG_SECTION_DEFAULT_SEARCH) + 1:].strip()
            elif section.lower().startswith(self.CONFIG_SECTION_SEARCH + "/"):
                search_label = section[len(self.CONFIG_SECTION_SEARCH) + 1:].strip()
            else:
                continue

            if not len(search_label):
                self.warn('Ignoring empty search name (section "{}").'.format(section))
                continue
            forbidden_chars = ":;,/|\\"
            if any(c in forbidden_chars for c in search_label):
                self.warn('Forbidden character(s) found in search name "{}". Forbidden characters list "{}"'.format(search_label, forbidden_chars))
                continue
            if search_label.lower() in self.searches.keys():
                self.warn('Ignoring duplicated search "{}" defined in section "{}".'.format(search_label, section))
                continue

            if not settings.get_bool("enable", section=section, fallback=True):
                continue

            search_item_label_format = settings.get_stripped(
                "item_label_format", section=section, fallback=item_label_format)
            search_item_label = search_item_label_format.format(
                search_name=search_label, plugin_name=self.friendly_name())

            search_pattern = settings.get_stripped("pattern", section=section)
            if not len(search_pattern):
                self.warn('Search "{}" does not have "pattern" value. Search ignored.'.format(search_label))
                continue
            if '%s' not in search_pattern:
                self.warn('Search-terms placeholder "%s" not found in pattern of search "{}". Search ignored.'.format(search_label))
                continue

            search_description = settings.get_stripped(
                "description", section=section, fallback="Search {}".format(search_label))
            search_allow_empty_search = settings.get_bool(
                "allow_empty_search", section=section, fallback=default_allow_empty_search)
            search_is_regex = settings.get_bool(
                "is_regex", section=section, fallback=default_is_regex)

            self.searches[search_label.lower()] = {
                'pattern': search_pattern,
                'item_label': search_item_label,
                'allow_empty_search': search_allow_empty_search,
                'is_regex': search_is_regex,
                'description': search_description}
