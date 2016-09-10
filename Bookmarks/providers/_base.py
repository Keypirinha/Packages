# Keypirinha: a fast launcher for Windows (keypirinha.com)

import urllib.parse

class Bookmark():
    def __init__(self, provider_label, label, url):
        self.provider_label = provider_label
        self.label = label.strip() if isinstance(label, str) else ""
        self.url = url.strip() if isinstance(url, str) else ""

        self.scheme = None
        self.empty_label = False
        self.is_auth = False
        self.pretty_url = self.url

        try:
            parsed = urllib.parse.urlparse(self.url)

            self.scheme = parsed.scheme

            if parsed.username or parsed.password:
                self.is_auth = True

            self.pretty_url = parsed.hostname + parsed.path
            #if parsed.fragment:
            #    self.pretty_url += "#" + parsed.fragment
        except Exception:
            pass

        if not self.label:
            self.empty_label = True
            self.label = self.pretty_url

class BookmarksProviderBase():
    def __init__(self, plugin, label, settings, config_section):
        self.plugin = plugin
        self.label = label
        self.settings = settings
        self.config_section = config_section

    def list_bookmarks(self):
        raise NotImplementedError
