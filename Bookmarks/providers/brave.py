# Keypirinha: a fast launcher for Windows (keypirinha.com)

import os.path
from .chrome import ChromeProviderBase

class BraveProvider(ChromeProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def profile_dir_candidates(self):
        candidates = []
        if self.localappdata_dir:
            candidates.append(os.path.join(
                self.localappdata_dir, "BraveSoftware", "Brave-Browser", "User Data"))
        return candidates
