# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_api
from . import providers

class Bookmarks(kp.Plugin):
    """Launch Chrome, Firefox, Internet Explorer and Vivaldi bookmarks."""

    DEFAULT_GROUP_ITEM_LABEL = ""
    DEFAULT_ITEM_LABEL_FORMAT = "Bookmark: {label} ({provider})"

    group_item_label = DEFAULT_GROUP_ITEM_LABEL
    item_label_format = DEFAULT_ITEM_LABEL_FORMAT
    keep_empty_names = True
    keep_auth_url = True
    force_new_window = None
    force_private_mode = None

    bookmarks = []

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_user_config()

    def on_catalog(self):
        # re-read user configuration
        self._read_user_config()

        self.bookmarks = self._create_bookmark_items()

        if self.group_item_label == "" or self.group_item_label.isspace():
            # Build catalog from bookmarks
            self.set_catalog(self.bookmarks)
        else:
            # Create group catalog item
            self.set_catalog([self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label=self.group_item_label,
                short_desc="Search and open browser bookmarks",
                target=str(self.id()),
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS)])

    def on_suggest(self, user_input, items_chain):
        if not items_chain or items_chain[0].category() != kp.ItemCategory.KEYWORD or items_chain[0].target() != str(self.id()):
            return
        self.set_suggestions(self.bookmarks)

    def on_execute(self, item, action):
        if action:
            kpu.execute_default_action(self, item, action)
        else:
            kpu.web_browser_command(
                private_mode=self.force_private_mode,
                new_window=self.force_new_window,
                url=item.target(),
                execute=True)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self.on_catalog()

    def _read_user_config(self):
        settings = self.load_settings()
        self.group_item_label = settings.get(
                                    "group_item_label", "main",
                                    self.DEFAULT_GROUP_ITEM_LABEL,
                                    unquote=True)
        self.item_label_format = settings.get(
                                    "item_label_format", "main",
                                    self.DEFAULT_ITEM_LABEL_FORMAT,
                                    unquote=True)
        self.keep_empty_names = settings.get_bool(
                                    "keep_empty_names", "main", True)
        self.keep_auth_url = settings.get_bool(
                                    "keep_auth_url", "main", True)
        self.force_new_window = settings.get_bool(
                                    "force_new_window", "main", None)
        self.force_private_mode = settings.get_bool(
                                    "force_private_mode", "main", None)

    def _get_bookmarks(self):
        settings = self.load_settings()

        bookmarks = []
        for config_section in settings.sections():
            if not config_section.lower().startswith("provider/"):
                continue
            if not settings.get_bool("enable", config_section, True):
                continue

            provider_name = config_section[len("provider/"):]
            try:
                provider_class = getattr(providers, provider_name + "Provider")
            except AttributeError:
                self.warn("Invalid bookmark provider name:", provider_name)
                continue

            provider = provider_class(
                                self, provider_name, settings, config_section)
            bookmarks += provider.list_bookmarks()

            if self.should_terminate():
                return []

        self.info("Referenced {} bookmark{}".format(
                    len(bookmarks), "s"[len(bookmarks)==1:]))
        return bookmarks

    def _create_bookmark_items(self):
        bookmarks = self._get_bookmarks()

        bookmark_items = []
        for b in bookmarks:
            if isinstance(b, providers.Bookmark):
                if not b.label or not b.url:
                    continue
                if b.empty_label and not self.keep_empty_names:
                    continue
                if b.is_auth and not self.keep_auth_url:
                    continue
                if "script" in b.scheme.lower(): # javascript, vbscript, ...
                    continue
                bookmark_items.append(self.create_item(
                    category=kp.ItemCategory.URL,
                    label=self.item_label_format.format(
                                    label=b.label, provider=b.provider_label),
                    short_desc="",
                    target=b.url,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.NOARGS))
            #elif isinstance(b, keypirinha_api.CatalogItem):
            #    # Notes:
            #    # * We do not have to check items against self.keep_auth_url
            #    #   here because we do not store the URL itself.
            #    # * provider_label is stored in item's short_desc property.
            #    if not b.valid():
            #        continue
            #    if b.category() != kp.ItemCategory.FILE:
            #        self.err("Duh?! #1")
            #        continue
            #    if not b.short_desc(): # where provider_label is expected to be stored
            #        self.err("Duh?! #2")
            #        continue
            #    if not b.label() and not self.keep_empty_names:
            #        continue
            #    provider_label = b.short_desc()
            #    b.set_short_desc("")
            #    b.set_label(self.item_label_format.format(
            #                        label=b.label(), provider=provider_label))
            #    bookmark_items.append(b)
            else:
                self.err("Duh?! #3")
                continue
        return bookmark_items
