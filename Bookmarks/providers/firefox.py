# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha_util as kpu
import os.path
import configparser
import sqlite3
from ._base import Bookmark, BookmarksProviderBase

class FirefoxProfile():
    """Firefox User profile"""
    def __init__(self, id_, path, name=None, is_default=None):
        self.id = id_
        self.path = path
        self.name = name
        self.is_default = is_default

class FirefoxProfilesDb():
    """
    Reads Firefox's profiles.ini file.
    Reference: http://kb.mozillazine.org/Profiles.ini_file
    """
    profiles = []

    def read(self, profiles_file):
        self.profiles = []
        with kpu.chardet_open(profiles_file, mode="rt") as fh:
            ini_parser = configparser.ConfigParser(interpolation=None)
            ini_parser.read_file(fh, source=profiles_file)

            for section in ini_parser.sections():
                if not section.lower().startswith("profile"):
                    continue

                profile = {
                    'id': section[len("profile"):],
                    'path': None,
                    'name': None,
                    'default': None,
                    'isrelative': None}

                # get string values
                for val_name in ("path", "name"):
                    try:
                        profile[val_name] = ini_parser.get(section, val_name)
                    except configparser.Error:
                        pass

                # get int values
                for val_name in ("default", "isrelative"):
                    try:
                        profile[val_name] = ini_parser.getint(section, val_name)
                    except configparser.Error:
                        pass

                # interpret profile data
                if not profile['path']:
                    print('Skipping invalid Firefox profile "{}" from {}'.format(section, profiles_file))
                    continue
                if profile['isrelative']:
                    profile['path'] = os.path.join(
                                os.path.dirname(profiles_file), profile['path'])

                # we've got one!
                self.profiles.append(FirefoxProfile(
                    profile['id'], profile['path'],
                    profile['name'], profile['default']))
        return True

class FirefoxProvider(BookmarksProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def list_bookmarks(self):
        places_files = self.settings.get_multiline(
                                        "places_files", self.config_section)
        if not places_files:
            roaming_app_data_dir = kpu.shell_known_folder_path(
                                    "{3eb685db-65f9-4cf6-a03a-e3ef65729f3d}")
            profiles_file = os.path.join(
                    roaming_app_data_dir, "Mozilla", "Firefox", "profiles.ini")

            if not os.path.isfile(profiles_file):
                return []

            profiles_db = FirefoxProfilesDb()
            try:
                profiles_db.read(profiles_file)
            except Exception as e:
                self.plugin.warn(
                    "Failed to read Firefox's profiles file \"{}\". Error: {}".format(
                        profiles_file, e))
                return []

            places_files = []
            for profile in profiles_db.profiles:
                places_file = os.path.join(profile.path, "places.sqlite")
                if os.path.isfile(places_file):
                    places_files.append(places_file)
                else:
                    self.plugin.warn("places.sqlite file not found in", profile.path)

        bookmarks = []
        for f in places_files:
            try:
                bookmarks += self._read_places_file(os.path.normpath(f))
            except Exception as e:
                self.plugin.warn("Failed to read Firefox's bookmarks file \"{}\". Error: {}".format(f, e))
                continue
        return bookmarks

    def _read_places_file(self, places_file):
        """
        Reads Firefox's places.sqlite file.
        Reference: http://kb.mozillazine.org/Places.sqlite
        """
        formated_db_path = places_file
        formated_db_path = formated_db_path.replace("\\", "/")
        formated_db_path = formated_db_path.replace("?", "%3f")
        formated_db_path = formated_db_path.replace("#", "%23")
        db_uri = "file:/{}?mode=ro".format(formated_db_path)

        bookmarks = []
        db = sqlite3.connect(db_uri, uri=True)
        for row in db.execute(
                        "SELECT b.title, p.url " +
                        "FROM moz_bookmarks AS b " +
                        "JOIN moz_places AS p ON p.id = b.fk AND b.type = 1"):
            (bk_label, bk_url) = row
            if bk_url and not bk_url.lower().startswith("place:"):
                bookmarks.append(Bookmark(self.label, bk_label, bk_url))
        db.close()

        return bookmarks
