# Keypirinha: a fast launcher for Windows (keypirinha.com)

import pyesedb
import keypirinha_util as kpu
import os.path
from ._base import Bookmark, BookmarksProviderBase

class EdgeProvider(BookmarksProviderBase):
    localappdata_dir = None

    SPARTAN_FILE_LOCATION = r"Packages\Microsoft.MicrosoftEdge_8wekyb3d8bbwe\AC\MicrosoftEdge\User\Default\DataStore" \
                            r"\Data\nouser1\120712-0049\DBStore\spartan.edb"

    #EDB structure
    FAVORITES_TABLE_NAME = "Favorites"
    TITLE_COLUMN = 17
    URL_COLUMN = 18

    def __init__(self, *args):
        super().__init__(*args)
        try:
            self.localappdata_dir = kpu.shell_known_folder_path(
                                    "{f1b32785-6fba-4fcf-9d55-7b8e7f157091}")
        except OSError:
            self.plugin.warn("Failed to get LocalAppData directory!")

    def list_bookmarks(self):
        bookmarks = []
        try:
            with open(os.path.join(self.localappdata_dir, self.SPARTAN_FILE_LOCATION), 'rb') as spartan_file:
                esedb_file = pyesedb.file()
                esedb_file.open_file_object(spartan_file)
                favorites_table = esedb_file.get_table_by_name(self.FAVORITES_TABLE_NAME)
                for i in range(favorites_table.get_number_of_records()):
                    rec = favorites_table.get_record(i)
                    bookmarks.append(Bookmark(self.label,
                                              rec.get_value_data_as_string(self.TITLE_COLUMN),
                                              rec.get_value_data_as_string(self.URL_COLUMN)))
                esedb_file.close()
        except IOError as e:
            self.plugin.warn("Failed to get Edge bookmarks: {0}".format(str(e)))
        return bookmarks
