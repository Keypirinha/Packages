# Keypirinha: a fast launcher for Windows (keypirinha.com)
# buku bookmark provider by CKolumbus@ac-drexler.de

import keypirinha_util as kpu
import os
import configparser
import sqlite3
import sys
from ._base import Bookmark, BookmarksProviderBase

class BukuProvider(BookmarksProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def list_bookmarks(self):
        bukudb_files = self.settings.get_multiline(
                                        "bukudb_files", self.config_section)

        if not bukudb_files:
            bukudb_file = self._get_default_db()
            if os.path.isfile(bukudb_file):
                bukudb_files.append(bukudb_file)

        bookmarks = []
        for f in bukudb_files:
            try:
                bookmarks += self._read_buku_db(os.path.normpath(f))
            except Exception as exc:
                self.plugin.warn("Failed to read buku's bookmarks file \"{}\". Error: {}".format(f, exc))
                continue
        return bookmarks

    @staticmethod
    def _get_default_db():
        """Determine the directory path where dbfile will be stored.
        If the platform is Windows, use %APPDATA%
        else if $XDG_DATA_HOME is defined, use it
        else if $HOME exists, use it
        else use the current directory.
        Shamelessly copied from https://github.com/jarun/Buku/blob/master/buku
        Returns
        -------
        str
            Full path to database file.
        """

        data_home = os.environ.get('XDG_DATA_HOME')
        if data_home is None:
            if os.environ.get('HOME') is None:
                if sys.platform == 'win32':
                    data_home = os.environ.get('APPDATA')
                    if data_home is None:
                        return os.path.abspath('.')
                else:
                    return os.path.abspath('.')
            else:
                data_home = os.path.join(os.environ.get('HOME'), '.local', 'share')

        return os.path.join(data_home, 'buku', 'bookmarks.db')

    def _read_buku_db(self, bukudb_file):
        """
        Reads buku's sqlite db file.
        """
        formated_db_path = bukudb_file
        formated_db_path = formated_db_path.replace("\\", "/")
        formated_db_path = formated_db_path.replace("?", "%3f")
        formated_db_path = formated_db_path.replace("#", "%23")
        db_uri = "file:/{}?mode=ro".format(formated_db_path)

        bookmarks = []
        db = sqlite3.connect(db_uri, uri=True)
        for row in db.execute(
                        "SELECT b.metadata, b.url " +
                        "FROM bookmarks AS b " ):
            (bk_label, bk_url) = row
            if bk_url :
                bookmarks.append(Bookmark(self.label, bk_label, bk_url))
        db.close()

        return bookmarks
