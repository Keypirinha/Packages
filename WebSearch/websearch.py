# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import os.path
import time
import urllib.parse

class WebSearch(kp.Plugin):
    """
    Launch a search on any configured web site.

    Search for the "WebSearch" prefix to check what sites are already in the
    Catalog. Additional search sites can be added in package's configuration
    file.
    """

    CONFIG_SECTION_MAIN = "main"
    CONFIG_SECTION_DEFAULTS = "defaults"
    CONFIG_SECTION_PREDEF_SITE = "predefined_site"
    CONFIG_SECTION_SITE = "site"

    DEFAULT_ITEM_LABEL_FORMAT = "WebSearch {site_name}"
    DEFAULT_ENABLE_PREDEFINED_SITES = True
    DEFAULT_MULTI_URL_DELAY = 150
    DEFAULT_NEW_WINDOW = False
    DEFAULT_INCOGNITO = False
    DEFAULT_HISTORY_KEEP = kp.ItemHitHint.NOARGS
    DEFAULT_ARGS_QUOTING = "auto"

    multi_url_delay = DEFAULT_MULTI_URL_DELAY
    default_icon_handle = None
    sites = {}

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._setup_default_icon()

    def on_catalog(self):
        self._setup_default_icon()
        self._read_config()
        catalog = []
        for site_name, site in self.sites.items():
            catalog.append(self.create_item(
                category=kp.ItemCategory.REFERENCE,
                label=site['item_label'],
                short_desc="Search {}".format(site['label']),
                target=kpu.kwargs_encode(site=site_name),
                args_hint=kp.ItemArgsHint.ACCEPTED,
                hit_hint=site['history_keep']))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if items_chain and items_chain[-1].category() == kp.ItemCategory.REFERENCE:
            clone = items_chain[-1].clone()
            clone.set_args(user_input.strip())
            self.set_suggestions([clone])

    def on_execute(self, item, action):
        if item.category() != kp.ItemCategory.REFERENCE:
            return

        try:
            item_target = kpu.kwargs_decode(item.target())
            site_name = item_target['site']
        except Exception as exc:
            self.dbg(str(exc))
            return

        if site_name not in self.sites:
            self.warn('Could not execute item "{}". Site "{}" not found.'.format(item.label(), site_name))
            return

        site = self.sites[site_name]

        if len(item.raw_args()) > 0:
            for url in site['urls']:
                final_url = self._url_build(url, item.raw_args(), site['quoting'])
                kpu.web_browser_command(
                    private_mode=site['incognito'], new_window=site['new_window'],
                    url=final_url, execute=True)
                if len(site['urls']) > 1:
                    time.sleep(self.multi_url_delay)
        else:
            for home_url in site['home_urls']:
                kpu.web_browser_command(
                    private_mode=site['incognito'], new_window=site['new_window'],
                    url=home_url, execute=True)
                if len(site['home_urls']) > 1:
                    time.sleep(self.multi_url_delay)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self.info("Configuration changed, rebuilding catalog...")
            self.on_catalog()

    def _setup_default_icon(self):
        if self.default_icon_handle:
            self.default_icon_handle.free()
            self.default_icon_handle = None

        args = kpu.web_browser_command()
        if args and os.path.isfile(args[0]):
            self.default_icon_handle = self.load_icon("@{},0".format(args[0]))
            if self.default_icon_handle:
                self.set_default_icon(self.default_icon_handle)

    def _url_build(self, url_format, search_terms, quoting='auto', fallback_url=None):
        def _quote(fmt_string, search_terms, quoting):
            if quoting == 'plus':
                return fmt_string.replace(
                    "%s", urllib.parse.quote_plus(search_terms))
            else: # if quoting == 'quote':
                return fmt_string.replace(
                    "%s", urllib.parse.quote(search_terms, safe=''))
        search_terms = search_terms.strip()
        elems = urllib.parse.urlparse(url_format)
        if len(search_terms) > 0 and "%s" in elems.query:
            # The placeholder is in the 'query' part of the URL, search terms
            # are URL-encoded using the urllib.parse.quote_plus() function.
            url_query = _quote(
                elems.query, search_terms,
                'plus' if quoting == 'auto' else quoting)
            return urllib.parse.urlunparse((
                elems.scheme, elems.netloc, elems.path,
                elems.params, url_query, elems.fragment))
        elif len(search_terms) > 0 and "%s" in elems.fragment:
            # The placeholder is in the 'fragment' part of the URL, search terms
            # are URL-encoded using the urllib.parse.quote() function.
            url_fragment = _quote(
                elems.fragment, search_terms,
                'full' if quoting == 'auto' else quoting)
            return urllib.parse.urlunparse((
                elems.scheme, elems.netloc, elems.path,
                elems.params, elems.query, url_fragment))
        elif len(search_terms) > 0 and "%s" in elems.path:
            # The placeholder is in the 'path' part of the URL, search terms
            # are URL-encoded using the urllib.parse.quote() function.
            url_path = _quote(
                elems.path, search_terms,
                'full' if quoting == 'auto' else quoting)
            return urllib.parse.urlunparse((
                elems.scheme, elems.netloc, url_path,
                elems.params, elems.query, elems.fragment))
        else:
            # here, there is no search term or the "%s" placeholder hasn't been
            # found, try to get site's home by removing the "query" part
            if fallback_url is not None:
                return fallback_url
            url_query = ''
            url_path = os.path.split(elems.path.replace("%s", elems.path))[0]
            return urllib.parse.urlunparse((
                elems.scheme, elems.netloc, url_path,
                elems.params, url_query, elems.fragment))

    def _read_config(self):
        self.sites = {}

        supported_history_keep_values = {
            'all': kp.ItemHitHint.KEEPALL,
            'site': kp.ItemHitHint.NOARGS,
            'none': kp.ItemHitHint.IGNORE}
        supported_quoting = ['auto', 'full', 'plus']

        settings = self.load_settings()

        item_label_format = settings.get_stripped(
            "item_label_format",
            section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ITEM_LABEL_FORMAT)

        enable_predefined_sites = settings.get_bool(
            "enable_predefined_sites",
            section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ENABLE_PREDEFINED_SITES)

        self.multi_url_delay = settings.get_int(
            "multi_url_delay",
            section=self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_MULTI_URL_DELAY,
            min=49, max=2000)
        if self.multi_url_delay <= 49:
            self.multi_url_delay = 0
        self.multi_url_delay /= 1000.0 # to seconds

        # read default values to be applied to the 'site' sections
        default_new_window = settings.get_bool(
            "new_window",
            section=self.CONFIG_SECTION_DEFAULTS,
            fallback=self.DEFAULT_NEW_WINDOW)
        default_incognito = settings.get_bool(
            "incognito",
            section=self.CONFIG_SECTION_DEFAULTS,
            fallback=self.DEFAULT_INCOGNITO)
        default_history_keep = settings.get_mapped(
            "history_keep",
            section=self.CONFIG_SECTION_DEFAULTS,
            fallback=self.DEFAULT_HISTORY_KEEP,
            map=supported_history_keep_values)

        # read "site" sections
        for section in settings.sections():
            if section.lower().startswith(self.CONFIG_SECTION_PREDEF_SITE + "/"):
                if not enable_predefined_sites:
                    continue
                site_label = section[len(self.CONFIG_SECTION_PREDEF_SITE) + 1:].strip()
            elif section.lower().startswith(self.CONFIG_SECTION_SITE + "/"):
                site_label = section[len(self.CONFIG_SECTION_SITE) + 1:].strip()
            else:
                continue

            if not len(site_label):
                self.warn('Ignoring empty site name (section "{}").'.format(section))
                continue
            forbidden_chars = (':;,/|\\')
            if any(c in forbidden_chars for c in site_label):
                self.warn(
                    'Forbidden character(s) found in site name "{}". Forbidden characters list "{}"'
                    .format(site_label, forbidden_chars))
                continue
            if site_label.lower() in self.sites.keys():
                self.warn('Ignoring duplicated site "{}" defined in section "{}".'.format(site_label, section))
                continue

            if not settings.get_bool("enable", section=section, fallback=True):
                continue

            site_item_label = item_label_format.format(
                site_name=site_label, plugin_name=self.friendly_name())

            site_home_urls = settings.get_multiline("home_url", section=section)

            site_urls = settings.get_multiline("url", section=section)
            if not len(site_urls):
                self.warn('Site "{}" does not have "url" value. Site ignored.'.format(site_label))
                continue
            invalid_site_urls = False
            for url in site_urls:
                if '%s' not in url and not len(site_home_urls):
                    self.warn('Search-terms placeholder "%s" not found in URL of site "{}" and no home_url specified. Site ignored.'.format(site_label))
                    invalid_site_urls = True
                    break
            if invalid_site_urls:
                continue

            if not len(site_home_urls):
                # if no home url have been provided, try to guess it/them
                for url in site_urls:
                    elems = urllib.parse.urlparse(url)
                    site_home_urls.append(urllib.parse.urlunparse(
                                (elems.scheme, elems.netloc, "", "", "", "")))

            site_new_window = settings.get_bool(
                "new_window", section=section, fallback=default_new_window)

            site_incognito = settings.get_bool(
                "incognito", section=section, fallback=default_incognito)

            site_history_keep = settings.get_mapped(
                "history_keep",
                section=section,
                fallback=default_history_keep,
                map=supported_history_keep_values)

            site_quoting = settings.get_enum(
                "quoting",
                section=section,
                fallback=self.DEFAULT_ARGS_QUOTING,
                enum=supported_quoting)

            self.sites[site_label.lower()] = {
                'label': site_label,
                'urls': site_urls,
                'home_urls': site_home_urls,
                'item_label': site_item_label,
                'new_window': site_new_window,
                'incognito': site_incognito,
                'history_keep': site_history_keep,
                'quoting': site_quoting}
