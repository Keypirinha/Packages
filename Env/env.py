# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import os

class Env(kp.Plugin):
    """Search your environment variables"""

    ITEM_LABEL_PREFIX = "Env: "
    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 1

    cached_env = {}

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._cache_env()

        self.set_actions(self.ITEMCAT_RESULT, [
            self.create_action(
                name="copy",
                label="Copy",
                short_desc="Copy the full declaration (name and value)"),
            self.create_action(
                name="copy_value",
                label="Copy Value",
                short_desc="Copy the value only"),
            self.create_action(
                name="copy_name",
                label="Copy Name",
                short_desc="Copy the name only")])

    def on_catalog(self):
        self.set_catalog([self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label=self.ITEM_LABEL_PREFIX + "Search",
            short_desc="Search your environment variables",
            target="search",
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS)])

    def on_suggest(self, user_input, items_chain):
        if not items_chain or items_chain[-1].category() != kp.ItemCategory.KEYWORD:
            return

        user_input = user_input.strip()

        suggestions = []
        for name, value in self.cached_env.items():
            suggestions.append(self.create_item(
                category=self.ITEMCAT_RESULT,
                label=name + " = " + value,
                short_desc="Press Enter to copy",
                target=name + "=" + value,
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.IGNORE))

        self.set_suggestions(
            suggestions,
            kp.Match.ANY if not user_input else kp.Match.FUZZY,
            kp.Sort.NONE if not user_input else kp.Sort.SCORE_DESC)

    def on_execute(self, item, action):
        if item and item.category() == self.ITEMCAT_RESULT:
            if action and action.name() == "copy_value":
                elems = item.target().split("=", maxsplit=1)
                kpu.set_clipboard(elems[1])
            elif action and action.name() == "copy_name":
                elems = item.target().split("=", maxsplit=1)
                kpu.set_clipboard(elems[0])
            else:
                kpu.set_clipboard(item.target())

    def on_events(self, flags):
        if flags & kp.Events.ENV:
            self._cache_env()

    def _cache_env(self):
        self.cached_env = {}
        for name, value in os.environ.items():
            self.cached_env[name] = os.path.expandvars(value)
