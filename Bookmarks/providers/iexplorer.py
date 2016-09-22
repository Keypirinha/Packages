# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import sys
import os.path
from ._base import Bookmark, BookmarksProviderBase

class InternetExplorerProvider(BookmarksProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def list_bookmarks(self):
        favorites_dirs = self.settings.get_multiline(
                                        "favorites_dirs", self.config_section)
        if not favorites_dirs:
            favorites_dirs = [kpu.shell_known_folder_path(
                                    "{1777f761-68ad-4d8a-87bd-30b759fa33dd}")]

        bookmarks = []
        for favdir in favorites_dirs:
            favdir = os.path.normpath(favdir)
            try:
                url_files = kpu.scan_directory(
                                    favdir, "*.url", kpu.ScanFlags.FILES, -1)
            except OSError as exc:
                print(self.__class__.__name__ + ":", exc, file=sys.stderr)
                continue
            for url_file in url_files:
                url_file = os.path.join(favdir, url_file)
                #bookmarks.append(self.plugin.create_item(
                #    category=kp.ItemCategory.FILE,
                #    label=os.path.splitext(os.path.basename(url_file))[0],
                #    short_desc=self.label, # trick to transport provider's label
                #    target=url_file,
                #    args_hint=kp.ItemArgsHint.FORBIDDEN,
                #    hit_hint=kp.ItemHitHint.NOARGS))
                try:
                    bk_url = None
                    with kpu.chardet_open(url_file, mode="rt") as fh:
                        in_url_section = False
                        for line in fh:
                            line = line.strip()
                            if not in_url_section:
                                if line.lower() == "[internetshortcut]":
                                    in_url_section = True
                            else:
                                if line.lower().startswith("url="):
                                    bk_url = line[len("url="):].strip()
                                    break
                    if bk_url:
                        bk_label = os.path.splitext(os.path.basename(url_file))[0]
                        bookmarks.append(Bookmark(self.label, bk_label, bk_url))
                except Exception as exc:
                    self.plugin.warn(
                        "Failed to read URL file: {}. Error: {}".format(
                            url_file, exc))
        return bookmarks
