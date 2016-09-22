# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import os.path
from .lib.alttab import AltTab

class TaskSwitcher(kp.Plugin):
    """
    Task switcher (Alt+Tab equivalent).

    List the currently opened applications and quickly switch to one of them.
    """

    DEFAULT_ITEM_LABEL = "Switch To"
    DEFAULT_ALWAYS_SUGGEST = False
    KEYWORD = "switchto"

    item_label = DEFAULT_ITEM_LABEL
    always_suggest = DEFAULT_ALWAYS_SUGGEST

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_config()

    def on_catalog(self):
        self.set_catalog([self._create_keyword_item(
            label=self.item_label + "...",
            short_desc="Switch to a running application")])

    def on_suggest(self, user_input, items_chain):
        if not items_chain and (not self.always_suggest or len(user_input) == 0):
            return
        if items_chain and (
                items_chain[0].category() != kp.ItemCategory.KEYWORD or
                items_chain[0].target() != self.KEYWORD):
            return

        try:
            handles = AltTab.list_alttab_windows()
        except OSError as exc:
            self.err("Failed to list Alt+Tab windows.", str(exc))
            return

        suggestions = []
        procs = {}
        for hwnd in handles:
            # get window's title and the id of its parent process
            try:
                wnd_title = AltTab.get_window_text(hwnd)
                (_, proc_id) = AltTab.get_window_thread_process_id(hwnd)
                if proc_id == kp.pid():
                    continue # skip any window from main keypirinha's process
            except OSError:
                continue

            # Get the name of its parent process.
            # We have to OpenProcess to do that. Unfortunately, Vista and beyond
            # won't allow us to do so if the remote process has higher
            # privileges than us.
            if proc_id in procs:
                proc_image = procs[proc_id]
            else:
                try:
                    proc_image = AltTab.get_process_image_path(proc_id)
                except OSError:
                    proc_image = None
                procs[proc_id] = proc_image

            # build the final label of the suggestion item
            item_label = wnd_title
            item_short_desc = "{}: {}".format(self.item_label, wnd_title)
            if proc_image is not None:
                proc_name = os.path.splitext(os.path.basename(proc_image))[0]
                item_label += " (" + proc_name + ")"
                item_short_desc += " (" + proc_name + ")"

            # if user_input is empty, just match everything we get
            match_score = 1
            if len(user_input) > 0:
                if items_chain and items_chain[0]:
                    against = item_label
                else:
                    against = self.item_label + " " + item_label
                match_score = kpu.fuzzy_score(user_input, against)
            if match_score:
                suggestion = self._create_keyword_item(self.item_label, item_short_desc)
                suggestion.set_args(str(hwnd), item_label)
                suggestions.append(suggestion)

        if len(suggestions) > 0:
            self.set_suggestions(suggestions)

    def on_execute(self, item, action):
        if (item
                and item.category() == kp.ItemCategory.KEYWORD
                and item.target() == self.KEYWORD):
            try:
                hwnd = int(item.raw_args())
            except (TypeError, ValueError):
                self.warn("Cannot switch to HWND [{}]".format(item.raw_args()))
            AltTab.switch_to_window(hwnd)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()
            self.on_catalog()

    def _read_config(self):
        settings = self.load_settings()
        self.item_label = settings.get_stripped(
            "item_label", "main", self.DEFAULT_ITEM_LABEL)
        self.always_suggest = settings.get_bool(
            "always_suggest", "main", self.DEFAULT_ALWAYS_SUGGEST)

    def _create_keyword_item(self, label, short_desc):
        return self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label=label,
            short_desc=short_desc,
            target=self.KEYWORD,
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS)
