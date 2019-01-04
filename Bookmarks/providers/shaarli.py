# Keypirinha: a fast launcher for Windows (keypirinha.com)
# shaarli bookmark provider by CKolumbus@ac-drexler.de

import keypirinha_net as kpn
import urllib
import json
from .lib.jwt import encode
import calendar, time
import os.path
import configparser
from ._base import Bookmark, BookmarksProviderBase

class ShaarliProvider(BookmarksProviderBase):
    def __init__(self, *args):
        super().__init__(*args)

    def list_bookmarks(self):
        shaarli_url    = self.settings.get("url", self.config_section)
        shaarli_secret = self.settings.get("secret", self.config_section)
        shaarli_proxy  = self.settings.get("proxy", self.config_section)

        bookmarks = []
        try:
            bookmarks += self._read_shaarli_api(shaarli_url, shaarli_secret, shaarli_proxy)
        except Exception as exc:
            self.plugin.warn("Failed to read from shaarli url \"{}\". Error: {}".format(shaarli_url, exc))

        return bookmarks


    def _read_shaarli_api(self, url, secret, proxy):
        """
        Read links from shaarli api
        """
        bookmarks = []

        params = { 'limit': 'all' }
        params_enc = urllib.parse.urlencode( params )

        iat = calendar.timegm(time.gmtime())
        token_enc = encode({'iat': iat}, secret, algorithm='HS512')
        headers = {"Authorization" : "Bearer %s" %  token_enc.decode("utf-8")}

        proxies = {'http': proxy, 'https': proxy } if proxy else None

        opener = kpn.build_urllib_opener(proxies)
        opener.addheaders = [("Authorization", "Bearer %s" %  token_enc.decode("utf-8") )]


        request_uri = url + "/api/v1/links?" + params_enc
        with opener.open(request_uri) as response:
            data = json.loads(response.read())

        for item in data:
            bookmarks.append(Bookmark(self.label, item['title'], item['url']))

        return bookmarks
