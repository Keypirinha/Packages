# Keypirinha: a fast launcher for Windows (keypirinha.com)

import os.path
from .chrome import ChromeProviderBase

class FalkonProvider(ChromeProviderBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.filename = "bookmarks.json"

    def profile_dir_candidates(self):
        candidates = []
        if self.localappdata_dir:
            candidates.append(os.path.join(
                self.localappdata_dir, "falkon", "profiles"))
        return candidates
