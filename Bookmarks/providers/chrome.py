# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha_util as kpu
import os.path
import json
from ._base import Bookmark, BookmarksProviderBase

class ChromeProviderBase(BookmarksProviderBase):
    localappdata_dir = None

    def __init__(self, *args):
        super().__init__(*args)
        try:
            self.localappdata_dir = kpu.shell_known_folder_path(
                                    "{f1b32785-6fba-4fcf-9d55-7b8e7f157091}")
        except OSError:
            self.plugin.warn("Failed to get LocalAppData directory!")

    def profile_dir_candidates(self):
        raise NotImplementedError

    def list_bookmarks(self):
        bookmarks = []
        bookmarks_files = self.settings.get_multiline(
                                        "bookmarks_files", self.config_section)
        if bookmarks_files:
            for f in bookmarks_files:
                bookmarks += self._read_bookmarks(os.path.normpath(f))
        else:
            srcdir_candidates = self.profile_dir_candidates()
            if not srcdir_candidates:
                return []
            for chrome_dir in srcdir_candidates:
                try:
                    profile_dirs = kpu.scan_directory(
                                        chrome_dir,
                                        flags=kpu.ScanFlags.DIRS, max_level=0)
                except OSError:
                    profile_dirs = []

                for profile_dir in profile_dirs:
                    bookmarks += self._read_bookmarks(os.path.join(
                                        chrome_dir, profile_dir, "Bookmarks"))
        return bookmarks

    def _read_bookmarks(self, bookmarks_file):
        # Chrome's "Bookmarks" file format appears to be JSON currently.
        # According to some feedback, it used to be XML but we do not really
        # have to bother because of Chrome auto-update feature.
        def _extract_bookmarks(node):
            bookmarks = []
            if isinstance(node, (list, tuple)):
                for child_node in node:
                    bookmarks += _extract_bookmarks(child_node)
            elif isinstance(node, dict):
                if "type" in node and node["type"].lower() == "url":
                    try:
                        bookmarks.append(
                            Bookmark(self.label, node["name"], node["url"]))
                    except KeyError:
                        pass
                else:
                    # blind loop to be more flexible about potential format changes
                    for k, child_node in node.items():
                        bookmarks += _extract_bookmarks(child_node)
            return bookmarks

        try:
            fh = kpu.chardet_open(bookmarks_file, mode="rt")
        except OSError as e:
            pass
        except Exception as e:
            self.plugin.warn(
                "Failed to read Bookmarks file: {}. Error: {}".format(
                    bookmarks_file, e))
        else:
            with fh:
                return _extract_bookmarks(json.load(fh))
        return []

class ChromeProvider(ChromeProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def profile_dir_candidates(self):
        candidates = []
        if self.localappdata_dir:
            candidates.append(os.path.join(
                self.localappdata_dir, "Google", "Chrome", "User Data"))
        return candidates

class ChromeCanaryProvider(ChromeProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def profile_dir_candidates(self):
        candidates = []
        if self.localappdata_dir:
            candidates.append(os.path.join(
                self.localappdata_dir, "Google", "Chrome SxS", "User Data"))
        return candidates

class ChromiumProvider(ChromeProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def profile_dir_candidates(self):
        candidates = []
        if self.localappdata_dir:
            candidates.append(os.path.join(
                self.localappdata_dir, "Chromium", "User Data"))
        return candidates
