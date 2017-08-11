# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_net as kpnet
import copy
import json
import os.path
import time
import traceback
import urllib.error
import urllib.parse

try:
    from WebSuggest import websuggest_user_parsers
except ImportError:
    traceback.print_exc()
    websuggest_user_parsers = None

class WebSuggestionsProvider():
    __slots__ = (
        "name", "label",
        "api_base", "api_method", "api_args", "api_headers", "api_parser",
        "browse_base", "browse_args")

    # note: some definitions of providers can be found in Firefox's
    # "searchplugins" registry at resource://search-plugins/

    def __init__(self, name, label):
        self.name = name
        self.label = label
        self.reset()

    def reset(self):
        self.api_base = None
        self.api_method = "get"
        self.api_args = []
        self.api_headers = []
        self.api_parser = self.__class__._api_parser_opensearch

        self.browse_base = None
        self.browse_args = []

    def init_from_config(self, settings, section, key_prefix=""):
        is_init_already = len(key_prefix) > 0

        if not is_init_already:
            self.reset()

        # api_base (required)
        new_api_base = settings.get_stripped(key_prefix + "api_base", section,
                                             fallback=None)
        if new_api_base:
            self.api_base = new_api_base
        elif not is_init_already:
            raise ValueError(
                "missing {}api_base value from config section [{}]".format(
                    key_prefix, section))

        # api_method
        self.api_method = settings.get_stripped(key_prefix + "api_method",
                                                section, fallback="get")
        self.api_method = self.api_method.lower()
        if self.api_method not in ("get", "post"):
            raise ValueError(
                "invalid {}api_method value from config section [{}]".format(
                    key_prefix, section))

        # api_args
        lines = settings.get_multiline(key_prefix + "api_args", section)
        if lines:
            for line in lines:
                if " " not in line:
                    raise ValueError(
                        "malformed {}api_args value from config section [{}]".format(
                            key_prefix, section))
                name, value = line.split(" ", maxsplit=1)
                self.api_args.append((name.strip(), value.strip()))

        # api_headers
        lines = settings.get_multiline(key_prefix + "api_headers", section)
        for line in lines:
            if " " not in line:
                raise ValueError(
                    "malformed {}api_headers value from config section [{}]".format(
                        key_prefix, section))
            name, value = line.split(" ", maxsplit=1)
            self.api_headers.append((name.strip(), value.strip()))

        # api_parser
        api_parser_name = settings.get_stripped(key_prefix + "api_parser",
                                                section, fallback=None)
        if api_parser_name:
            parent_namespace = self.__class__

            if api_parser_name.lower().startswith("user."):
                if not websuggest_user_parsers:
                    raise ValueError(
                        ("invalid {}api_parser value from config section " +
                        "[{}] or websuggest_user_parsers.py is missing").format(
                            key_prefix, section))
                api_parser_name = api_parser_name[len("user."):]
                parent_namespace = websuggest_user_parsers
            else:
                api_parser_name = "_api_parser_" + api_parser_name

            try:
                self.api_parser = getattr(parent_namespace, api_parser_name)
            except AttributeError as exc:
                raise ValueError(
                    ("invalid {}api_parser value from config section [{}]. " +
                    "Error: {}").format(
                        key_prefix, section, str(exc)))

            if not callable(self.api_parser):
                raise ValueError(
                    ("{}api_parser value from config section [{}] " +
                    "does not reference a callable Python object").format(
                        key_prefix, section))

        # browse_base (required)
        new_browse_base = settings.get_stripped(key_prefix + "browse_base",
                                                section)
        if new_browse_base:
            self.browse_base = new_browse_base
        elif not is_init_already:
            raise ValueError(
                "missing {}browse_base value from config section [{}]".format(
                    key_prefix, section))

        # browse_args
        lines = settings.get_multiline(key_prefix + "browse_args", section)
        if lines:
            for line in lines:
                if " " not in line:
                    raise ValueError(
                        "malformed {}browse_args value from config section [{}]".format(
                            key_prefix, section))
                name, value = line.split(" ", maxsplit=1)
                self.browse_args.append((name.strip(), value.strip()))

    def query(self, plugin, search_terms):
        # prepare the connection opener
        opener = kpnet.build_urllib_opener()
        if self.api_headers:
            opener.addheaders = self.api_headers[:] # we slice the list just in case

        # prepare the query
        placeholders = {
            'terms': search_terms,
            'time': str(int(time.time()))}
        url = self._fill_placeholders(self.api_base, urllib.parse.quote,
                                      **placeholders)
        data = None
        if self.api_args:
            cooked_args = self._cook_args(self.api_args, **placeholders)
            if self.api_method.lower() == "post":
                data = cooked_args.encode("utf-8")
            else:
                url += "?" + cooked_args

        # do query
        with opener.open(url, data=data) as conn:
            response = conn.read()

        # parse response to get a list of suggestions (str)
        return self.api_parser(plugin, self, response)

    def build_browse_url(self, search_terms):
        placeholders = {
            'terms': search_terms,
            'time': str(int(time.time()))}
        url = self._fill_placeholders(self.browse_base,
                                      urllib.parse.quote,
                                      **placeholders)
        url += "?" + self._cook_args(self.browse_args, **placeholders)
        return url

    def _cook_args(self, args_list_, **kwargs):
        copied_args = []
        for k, v in args_list_:
            copied_args.append((
                self._fill_placeholders(k, None, **kwargs),
                self._fill_placeholders(v, None, **kwargs)))

        return urllib.parse.urlencode(copied_args)

    def _fill_placeholders(self, value_, encode_, **kwargs):
        value = value_
        for kw_name, kw_value in kwargs.items():
            while "{" + kw_name + "}" in value:
                v = encode_(kw_value) if encode_ else kw_value
                value = value.replace("{" + kw_name + "}", v)
        return value

    @staticmethod
    def _api_parser_opensearch(plugin, provider, response):
        try:
            response = response.decode(encoding="utf-8", errors="strict")
            return json.loads(response)[1]
        except:
            plugin.warn("Failed to parse response from provider {}.".format(
                        provider.label))
            traceback.print_exc()
            return []

    @staticmethod
    def _api_parser_qwant(plugin, provider, response):
        try:
            response = response.decode(encoding="utf-8", errors="strict")
            json_root = json.loads(response)

            if json_root['status'] != "success":
                plugin.warn(
                    "Unexpected status from provider {}. Payload: {}".format(
                        provider.label, response))
                return []

            return [it['value'] for it in json_root['data']['items']]
        except:
            plugin.warn("Failed to parse response from provider {}.".format(
                        provider.label))
            traceback.print_exc()
            return []

class WebSuggest(kp.Plugin):
    """Suggestions from online search engines"""

    ITEMCAT_PROFILE = kp.ItemCategory.USER_BASE + 1

    ACTION_BROWSE = "browse"
    ACTION_BROWSE_PRIVATE = "browse_private"
    ACTION_COPY_RESULT = "copy_result"
    ACTION_COPY_URL = "copy_url"

    CONFIG_SECTION_MAIN = "main"
    CONFIG_KEYPREFIX_PROVIDER = "provider."

    DEFAULT_ENABLE_PREDEFINED_PROVIDERS = True
    DEFAULT_ENABLE_PREDEFINED_ITEMS = True
    DEFAULT_WAITING_TIME = 0.25
    DEFAULT_ACTION = ACTION_BROWSE

    actions_names = []
    default_icon = None
    icons = {}
    providers = {}
    profiles = {}
    waiting_time = DEFAULT_WAITING_TIME

    def __init__(self):
        super().__init__()

    def on_start(self):
        # register actions
        actions = [
            self.create_action(
                name=self.ACTION_BROWSE,
                label="Open in browser",
                short_desc="Open your query in Google Translate"),
            self.create_action(
                name=self.ACTION_BROWSE_PRIVATE,
                label="Open in browser (Private Mode)",
                short_desc="Open your query in Google Translate (Private Mode)"),
            self.create_action(
                name=self.ACTION_COPY_RESULT,
                label="Copy result",
                short_desc="Copy result to clipboard"),
            self.create_action(
                name=self.ACTION_COPY_URL,
                label="Copy URL",
                short_desc="Copy resulting URL to clipboard")]
        self.actions_names = []
        for act in actions:
            self.actions_names.append(act.name())
        self.set_actions(self.ITEMCAT_PROFILE, actions)

        self._load_icons()

        # load settings
        # reminder: self.actions_names must be populated before
        self._read_config()

    def on_catalog(self):
        catalog = []
        for profile_name, profile in self.profiles.items():
            catalog.append(self.create_item(
                category=self.ITEMCAT_PROFILE,
                label=profile['label'],
                short_desc="Suggest via {} (default action: {})".format(
                          profile['provider'].label, profile['default_action']),
                target=kpu.kwargs_encode(profile=profile_name),
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS,
                icon_handle=self._find_icon(profile['provider'].browse_base)))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if not items_chain or items_chain[-1].category() != self.ITEMCAT_PROFILE:
            return
        user_input = user_input.strip()
        current_item = items_chain[-1]
        target_props = kpu.kwargs_decode(current_item.target())
        profile_name = target_props['profile']

        try:
            profile = self.profiles[profile_name]
        except KeyError:
            self.warn('Item definition not found in current config: "{}"'.format(profile_name))
            return

        default_item = current_item.clone()
        default_item.set_args(user_input)
        if not user_input:
            default_item.set_short_desc("Open the search engine home page")

        suggestions = [default_item]

        # avoid doing unnecessary network requests in case user is still typing
        if len(user_input) < 2 or self.should_terminate(self.waiting_time):
            self.set_suggestions(suggestions)
            return

        provider_suggestions = []

        try:
            provider_suggestions = profile['provider'].query(self, user_input)
            if self.should_terminate():
                return
        except urllib.error.HTTPError as exc:
            suggestions.append(self.create_error_item(
                label=user_input, short_desc=str(exc)))
        except Exception as exc:
            suggestions.append(self.create_error_item(
                label=user_input, short_desc="Error: " + str(exc)))
            traceback.print_exc()

        for provider_suggestion in provider_suggestions:
            item = current_item.clone()
            item.set_args(provider_suggestion)
            #item.set_data_bag(user_input)
            suggestions.append(item)

        if not provider_suggestions:  # change default item
            suggestions[0].set_short_desc("No suggestions found (default action: {})".format(
                                profile['default_action']))

        self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        target_props = kpu.kwargs_decode(item.target())
        profile_name = target_props['profile']
        args = item.raw_args()

        try:
            profile = self.profiles[profile_name]
        except KeyError:
            self.warn('Item definition not found in current config: "{}"'.format(profile_name))
            return

        if not args:  # open the search engine home page
            base = profile['provider'].browse_base
            try:
                parts = urllib.parse.urlsplit(base)
                url = '{}://{}'.format(parts.scheme, parts.netloc)
            except ValueError:
                url = base
            kpu.web_browser_command(url=url, execute=True)
            return

        # choose action
        action_name = action.name() if action else None
        if not action_name:
            action_name = profile['default_action']
        if action_name and action_name not in self.actions_names:
            self.warn(
                'Unknown action "{}". Falling back to default: {}'.format(
                    action_name, self.DEFAULT_ACTION))
            action_name = self.DEFAULT_ACTION
        if not action_name:
            action_name = self.DEFAULT_ACTION

        # browse or copy url
        if action_name in (self.ACTION_BROWSE, self.ACTION_BROWSE_PRIVATE,
                           self.ACTION_COPY_URL):
            url = profile['provider'].build_browse_url(args)

            # copy url
            if action_name == self.ACTION_COPY_URL:
                kpu.set_clipboard(url)

            # launch browser
            else:
                private_mode = True if action_name == self.ACTION_BROWSE_PRIVATE else None
                kpu.web_browser_command(private_mode=private_mode, url=url, execute=True)

        # default action: copy result (ACTION_COPY_RESULT)
        else:
            kpu.set_clipboard(args)

    def on_events(self, flags):
        if flags & (kp.Events.APPCONFIG | kp.Events.PACKCONFIG |
                    kp.Events.NETOPTIONS):
            self._read_config()
            self.on_catalog()

    def _read_config(self):
        if not self.actions_names:
            raise RuntimeError("empty actions list")

        settings = self.load_settings()

        self._load_icons()
        self.providers = {}
        self.profiles = {}

        # [main]
        default_action = settings.get_enum(
            "default_action", self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ACTION, enum=self.actions_names)
        enable_predefined_providers = settings.get_bool(
            "enable_predefined_providers", self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ENABLE_PREDEFINED_PROVIDERS)
        enable_predefined_items = settings.get_bool(
            "enable_predefined_items", self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_ENABLE_PREDEFINED_ITEMS)
        self.waiting_time = settings.get_float(
            "waiting_time", self.CONFIG_SECTION_MAIN,
            fallback=self.DEFAULT_WAITING_TIME, min=0.25)

        # [predefined_provider/*] and [provider/*] sections
        for section in settings.sections():
            if section.lower().startswith("predefined_provider/"):
                if not enable_predefined_providers:
                    continue
                provider_label = section[len("predefined_provider/"):].strip()
            elif section.lower().startswith("provider/"):
                provider_label = section[len("provider/"):].strip()
            else:
                continue

            provider_name = provider_label.lower()

            if not provider_name:
                self.warn("Skipping empty provider name in config section [{}].".format(section))
                continue
            if provider_name in self.providers:
                self.warn(
                    ('Suggestion provider "{}" declared more than once. ' +
                    'Ignoring subsequent declarations').format(provider_label))
                continue

            try:
                provider_ = WebSuggestionsProvider(provider_name, provider_label)
                provider_.init_from_config(settings, section)
                self.providers[provider_name] = provider_
            except ValueError as exc:
                self.warn(str(exc))
                self.warn("Provider [{}] skipped due to error".format(section))
                continue

        # [predefined_item/*] and [item/*] sections
        for section in settings.sections():
            if section.lower().startswith("predefined_item/"):
                if not enable_predefined_items:
                    continue
                item_label = section[len("predefined_item/"):].strip()
            elif section.lower().startswith("item/"):
                item_label = section[len("item/"):].strip()
            else:
                continue

            item_name = item_label.lower()

            if not item_name:
                self.warn("Skipping empty item name in config section [{}].".format(section))
                continue
            if item_name in self.profiles:
                self.warn(
                    ('Suggestion item "{}" declared more than once. ' +
                    'Ignoring subsequent declarations').format(item_label))
                continue

            # enable
            item_enabled = settings.get_bool("enable", section, fallback=True)
            if not item_enabled:
                continue

            # default_action
            item_default_action = settings.get_enum(
                "default_action", self.CONFIG_SECTION_MAIN,
                fallback=default_action, enum=self.actions_names)

            # provider
            item_provider_name = settings.get_stripped("provider", section)
            if not item_provider_name or item_provider_name not in self.providers:
                self.warn(
                    "Missing or unknown provider in config section [{}]".format(
                        section))
                continue
            item_provider = self.providers[item_provider_name]
            if self._config_section_has_provider_setting(
                    settings, section, self.CONFIG_KEYPREFIX_PROVIDER):
                # copy provider object if we have to change its default settings
                item_provider = copy.copy(self.providers[item_provider_name])

            # override provider's default settings if needed
            try:
                item_provider.init_from_config(
                    settings, section, key_prefix=self.CONFIG_KEYPREFIX_PROVIDER)
            except ValueError as exc:
                self.warn(str(exc))
                self.warn("Item [{}] skipped due to error".format(section))
                continue

            self.profiles[item_name] = {
                'label': item_label,
                'enabled': item_enabled,
                'default_action': item_default_action,
                'provider': item_provider}

    def _config_section_has_provider_setting(self, settings, section, key_prefix):
        key_prefix = key_prefix.lower()
        for key in settings.keys(section):
            if key.lower().startswith(key_prefix):
                return True
        return False

    def _find_icon(self, url):
        try:
            url_netloc = urllib.parse.urlsplit(url).netloc
        except ValueError:
            return self.default_icon
        url_netloc = url_netloc.split("@")[-1] # strip user:pass@* part
        url_netloc = url_netloc.split(":")[0]  # strip *:port part
        url_netloc = url_netloc.lower()

        # find best (longest) match amongst icons' domains
        matched_domain = None
        for icon_domain in self.icons.keys():
            if icon_domain in url_netloc and (
                    not matched_domain or
                    len(icon_domain) > len(matched_domain)):
                matched_domain = icon_domain

        if matched_domain:
            return self.icons[matched_domain]
        else:
            return self.default_icon

    def _load_icons(self):
        if self.default_icon:
            self.default_icon.free()
            self.default_icon = None

        for icon in self.icons.values():
            icon.free()
        self.icons = {}

        # default icon
        args = kpu.web_browser_command()
        if args and os.path.isfile(args[0]):
            self.default_icon = self.load_icon("@{},0".format(args[0]))
            if self.default_icon:
                self.set_default_icon(self.default_icon)

        # find embedded icon resources and group them by network domain name
        resources = self.find_resources("*")
        resources_by_domain = {}
        for file in resources:
            if not file.lower().startswith("icons/"):
                continue
            file_title, file_ext = os.path.splitext(file)
            if file_ext.lower() not in (".ico", ".png", ".jpg", ".jpeg"):
                continue

            netdomain = os.path.basename(file_title).lower()
            try:
                resources_by_domain[netdomain].append(file)
            except KeyError:
                resources_by_domain[netdomain] = [file]

        # load embedded icons
        package_name = self.package_full_name()
        for netdomain, files in resources_by_domain.items():
            resources = ["res://{}/{}".format(package_name, f) for f in files]
            try:
                icon = self.load_icon(resources)
            except:
                self.warn("Failed to load icon from:", ", ".join(resources))
                traceback.print_exc()
                continue

            self.icons[netdomain] = icon
