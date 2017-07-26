# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_wintypes as kpwt

import ctypes as ct
import natsort
import os
import stat
import string
import winreg

class FileBrowser(kp.Plugin):
    """Browse the filesystem as you type"""
    DEFAULT_SHOW_RECENTS = True
    DEFAULT_SHOW_DIRS_FIRST = True
    DEFAULT_SHOW_HIDDEN_FILES = False
    DEFAULT_SHOW_SYSTEM_FILES = False
    DEFAULT_SHOW_NETWORK_FILES = False
    DEFAULT_FOLLOW_SHELL_LINKS = True
    DEFAULT_HOME_TRIGGER = "~"

    show_recents = DEFAULT_SHOW_RECENTS
    show_dirs_first = DEFAULT_SHOW_DIRS_FIRST
    show_hidden_files = DEFAULT_SHOW_HIDDEN_FILES
    show_system_files = DEFAULT_SHOW_SYSTEM_FILES
    show_network_files = DEFAULT_SHOW_NETWORK_FILES
    follow_shell_links = DEFAULT_FOLLOW_SHELL_LINKS
    home = []
    home_trigger = DEFAULT_HOME_TRIGGER

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_config()

    def on_suggest(self, user_input, items_chain):
        orig_user_input = user_input
        if len(user_input) > 0:
            user_input = os.path.normpath(user_input)

        # initial search, home dir(s)
        if (not items_chain and
                len(self.home_trigger) > 0 and
                orig_user_input.lower().startswith(self.home_trigger.lower())):
            suggestions, match_method, sort_method = self._home_suggestions(orig_user_input[len(self.home_trigger):])
            self.set_suggestions(suggestions, match_method, sort_method)

        # initial search, "\" or "/"
        elif not items_chain and user_input == os.sep:
            suggestions = self._drives_suggestions()
            match_method = kp.Match.ANY
            sort_method = kp.Sort.LABEL_ASC
            if self.show_recents:
                self._insert_recents(suggestions, match_method, sort_method)
            self.set_suggestions(suggestions, match_method, sort_method)

        # initial search, user_input format is like "X:"
        elif not items_chain and (
                len(user_input) == 2 and user_input[1] == ":" and
                user_input[0].upper() in string.ascii_uppercase):
            suggestions, match_method, sort_method = self._browse_dir(user_input + os.sep)
            if self.show_recents:
                self._insert_recents(suggestions, match_method, sort_method, user_input)
            self.set_suggestions(suggestions, match_method, sort_method)

        # initial search, user_input is an absolute path, or a UNC
        # Notes:
        #   os.path.isabs("\\\\server\\share") == False
        #   os.path.ismount("\\\\server\\share") == True
        #   os.path.isabs("\\\\server\\share\\file") == True
        #   os.path.ismount("\\\\server\\share\\file") == False
        elif not items_chain and (
                os.path.isabs(os.path.expandvars(user_input)) or
                os.path.ismount(os.path.expandvars(user_input))):
            user_input = os.path.expandvars(user_input)
            if user_input.endswith(os.sep):
                # path is expected to be a directory
                suggestions, match_method, sort_method = self._browse_dir(user_input)
                if self.show_recents:
                    self._insert_recents(suggestions, match_method, sort_method, user_input)
                self.set_suggestions(suggestions, match_method, sort_method)
            elif os.path.isdir(user_input):
                # path is a directory
                suggestions, match_method, sort_method = self._browse_dir(user_input, check_base_dir=False)
                if self.show_recents:
                    self._insert_recents(suggestions, match_method, sort_method, user_input)
                self.set_suggestions(suggestions, match_method, sort_method)
            elif os.path.exists(user_input):
                # user_input is an item of the filesystem
                self.set_suggestions(
                    [self.create_item(
                        category=kp.ItemCategory.FILE,
                        label=os.path.basename(user_input),
                        short_desc="",
                        target=user_input,
                        args_hint=kp.ItemArgsHint.ACCEPTED,
                        hit_hint=kp.ItemHitHint.KEEPALL,
                        loop_on_suggest=True)],
                    kp.Match.ANY,
                    kp.Sort.NONE)
            else:
                # path is expected to be a directory suffixed by search terms
                base_dir, search_terms = os.path.split(user_input)
                suggestions, match_method, sort_method = self._browse_dir(
                        base_dir, search_terms=search_terms, store_score=True)
                if len(search_terms) > 0:
                    # Because of the self.home_trigger prefix, the user_input cannot
                    # be matched against files names. So we have to sort the
                    # suggestions by ourselves.
                    self._sort_matched_suggestions(suggestions)
                    match_method = kp.Match.ANY
                    sort_method = kp.Sort.NONE
                if self.show_recents:
                    self._insert_recents(suggestions, match_method, sort_method, user_input)
                self.set_suggestions(suggestions, match_method, sort_method)

        # current item is a FILE
        elif items_chain and items_chain[-1].category() == kp.ItemCategory.FILE:
            current_item = items_chain[-1]

            # check file's attributes
            if os.path.isdir(current_item.target()):
                dir_target = current_item.target()
                exists = True
            elif os.path.exists(current_item.target()):
                dir_target = None
                exists = True
                # check if file is a link pointing to a directory, in which case
                # we want to browse it
                if self.follow_shell_links and os.path.splitext(
                        current_item.target())[1].lower() == ".lnk":
                    try:
                        link_props = kpu.read_link(current_item.target())
                        if os.path.isdir(link_props['target']):
                            dir_target = link_props['target']
                    except:
                        pass
            else:
                dir_target = None
                exists = False

            if dir_target is not None:
                suggestions, match_method, sort_method = self._browse_dir(
                                    dir_target, check_base_dir=False,
                                    search_terms=os.path.expandvars(user_input))
                self.set_suggestions(suggestions, match_method, sort_method)
            elif exists:
                clone = current_item.clone()
                clone.set_args(orig_user_input)
                clone.set_loop_on_suggest(False)
                self.set_suggestions([clone], kp.Match.ANY, kp.Sort.NONE)
            else:
                self.set_suggestions([self.create_error_item(
                    label=orig_user_input,
                    short_desc="File/Dir not found: " + current_item.target())])

    def on_execute(self, item, action):
        if item.category() == kp.ItemCategory.FILE:
            kpu.execute_default_action(self, item, action)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()

    def _read_config(self):
        settings = self.load_settings()

        self.show_recents = settings.get_bool(
            "show_recents", "main", self.DEFAULT_SHOW_RECENTS)
        self.show_dirs_first = settings.get_bool(
            "show_dirs_first", "main", self.DEFAULT_SHOW_DIRS_FIRST)
        self.show_hidden_files = settings.get_bool(
            "show_hidden_files", "main", self.DEFAULT_SHOW_HIDDEN_FILES)
        self.show_system_files = settings.get_bool(
            "show_system_files", "main", self.DEFAULT_SHOW_SYSTEM_FILES)
        self.show_network_files = settings.get_bool(
            "show_network_files", "main", self.DEFAULT_SHOW_NETWORK_FILES)
        self.follow_shell_links = settings.get_bool(
            "follow_shell_links", "main", self.DEFAULT_FOLLOW_SHELL_LINKS)

        self.home_trigger = settings.get_stripped(
            "trigger", "home", self.DEFAULT_HOME_TRIGGER)

        self.home = []
        if len(self.home_trigger) > 0:
            home_value_lines = settings.get_multiline("home", "home", [])

            # apply default "home" value if needed
            if not home_value_lines:
                try:
                    home_value_lines = [
                        kpwt.get_known_folder_path(kpwt.FOLDERID.Profile)]
                except OSError as exc:
                    self.warn(str(exc))
                    home_value_lines = []

            for idx in range(len(home_value_lines)):
                home_dir = home_value_lines[idx].replace("/", os.sep)

                # If home_dir is prefixed by a "::{guid}" sequence
                if home_dir.startswith('::') and len(home_dir) >= 38:
                    (guid, tail) = (home_dir[2:].split(os.sep, maxsplit=1) + [None] * 2)[:2]
                    try:
                        kf_path = kpu.shell_known_folder_path(guid)
                        if tail is not None:
                            self.home.append(os.path.join(kf_path, tail))
                        else:
                            self.home.append(kf_path)
                    except OSError:
                        self.warn("Failed to get path of known folder from setting \"{}\"".format(home_dir))
                        continue

                # Otherwise, home_dir is assumed to be a valid path to a
                # directory. In order to be as flexible as possible, we must
                # not assume it already exists.
                else:
                    self.home.append(os.path.normpath(home_dir))


    def _drives_suggestions(self):
        suggestions = []
        for drv_letter in kpwt.get_logical_drives():
            drv_path = drv_letter + ":" + os.sep
            drv_type = kpwt.kernel32.GetDriveTypeW(drv_path)
            if drv_type == kpwt.DRIVE_NO_ROOT_DIR:
                continue
            elif drv_type == kpwt.DRIVE_REMOTE:
                if not self.show_network_files:
                    continue
            else:
                # try to open the drive to see if it's ready
                with kpwt.ScopedSysErrorMode():
                    disk_bytes = kpwt.ULARGE_INTEGER(0)
                    if kpwt.kernel32.GetDiskFreeSpaceExW(
                            drv_path, None, ct.byref(disk_bytes), None):
                        suggestions.append(self.create_item(
                            category=kp.ItemCategory.FILE,
                            label=drv_path,
                            short_desc="",
                            target=drv_path,
                            args_hint=kp.ItemArgsHint.ACCEPTED,
                            hit_hint=kp.ItemHitHint.KEEPALL,
                            loop_on_suggest=True))
        return suggestions

    def _home_suggestions(self, search_terms):
        # suggest only existing home dirs
        existing_home_dirs = []
        for home_dir in self.home:
            if os.path.isdir(home_dir):
                existing_home_dirs.append(home_dir)

        # If only one home dir remains, directly browse its content and filter
        # the results using search_terms, if any.
        if len(existing_home_dirs) == 1:
            suggestions, match_method, sort_method = self._browse_dir(
                                    existing_home_dirs[0], check_base_dir=False,
                                    search_terms=search_terms, store_score=True)
            if len(search_terms) > 0:
                # Because of the self.home_trigger prefix, the user_input cannot
                # be matched against files names. So we have to sort the
                # suggestions by ourselves.
                self._sort_matched_suggestions(suggestions)
                return suggestions, kp.Match.ANY, kp.Sort.NONE
            else:
                return suggestions, match_method, sort_method

        # Otherwise, we must first offer the list of available "home"
        # directories. Here again, we filter them by using search_terms if
        # needed.
        else:
            suggestions = []
            for home_dir in existing_home_dirs:
                match_score = None
                if len(search_terms) > 0:
                    match_score = kpu.fuzzy_score(search_terms,
                                                  os.path.basename(home_dir))
                    if not match_score:
                        continue
                    match_score = str(match_score)
                suggestions.append(self.create_item(
                    category=kp.ItemCategory.FILE,
                    label=os.path.basename(home_dir),
                    short_desc="",
                    target=home_dir,
                    args_hint=kp.ItemArgsHint.ACCEPTED,
                    hit_hint=kp.ItemHitHint.KEEPALL,
                    loop_on_suggest=True,
                    data_bag=match_score))

            if len(search_terms) > 0:
                # Because of the self.home_trigger prefix, the user_input cannot be
                # matched against files names. So we have to sort the suggestions by
                # ourselves.
                self._sort_matched_suggestions(suggestions)

            return suggestions, kp.Match.ANY, kp.Sort.NONE

    def _sort_matched_suggestions(self, suggestions):
        # sort suggestion using the score that is stored in the data_bag member,
        # then clear it to avoid polluting the Catalog and the History
        def _sortkey(item):
            score = item.data_bag()
            item.set_data_bag("")
            return score
        suggestions.sort(key=_sortkey, reverse=True)

    def _browse_dir(self, base_dir, check_base_dir=True, search_terms="", store_score=False):
        base_dir = os.path.normpath(base_dir)
        return kpu.browse_directory(self,
                                    base_dir,
                                    check_base_dir=check_base_dir,
                                    search_terms=search_terms,
                                    store_score=store_score,
                                    show_dirs_first=self.show_dirs_first,
                                    show_hidden_files=self.show_hidden_files,
                                    show_system_files=self.show_system_files)

    def _insert_recents(self, suggestions, match_method=kp.Match.ANY,
                        sort_method=kp.Sort.NONE, search_terms=""):
        recents = []
        if search_terms:
            search_terms = os.path.normcase(os.path.normpath(search_terms))

        try:
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\TypedPaths") as hkey:
                url_idx = 0
                while True:
                    (name, value, typ) = winreg.EnumValue(hkey, url_idx)
                    url_idx += 1
                    if typ == winreg.REG_SZ and name.lower().startswith("url"):
                        # we must check that value is a path since value can
                        # also be the name of a known folder like "Computer"
                        value = os.path.normpath(value)
                        if not (os.path.isabs(value) or os.path.ismount(value)):
                            continue

                        if search_terms and not os.path.normcase(value).startswith(search_terms):
                            continue

                        if match_method == kp.Match.FUZZY:
                            score = str(kpu.fuzzy_score(search_terms, value))
                        else:
                            score = None

                        recents.append(self.create_item(
                            category=kp.ItemCategory.FILE,
                            label=value,
                            short_desc="",
                            target=value,
                            args_hint=kp.ItemArgsHint.ACCEPTED,
                            hit_hint=kp.ItemHitHint.KEEPALL,
                            loop_on_suggest=True,
                            data_bag=score))
        except OSError as exc:
            pass

        if sort_method == kp.Sort.NONE:

            def _find_same_item(target, lst):
                target = os.path.normpath(target)
                for idx in range(len(lst)):
                    if target == os.path.normpath(lst[idx].target()):
                        return idx
                return None

            # remove duplicates by ourselves so Keypirinha does not try to merge
            # them, which may alter the desired positioning of items
            for recent_item in recents:
                match_idx = _find_same_item(recent_item.target(), suggestions)
                if match_idx is not None:
                    suggestions.pop(match_idx)

            recents = natsort.natsorted(recents, key=lambda x: x.label(),
                alg=natsort.ns.PATH | natsort.ns.LOCALE | natsort.ns.IGNORECASE)

            # prepend the recents list to the suggestions
            # but always keep the "." item at the top
            if len(suggestions) > 0 and suggestions[0].label() == ".":
                suggestions[1:0] = recents
            else:
                suggestions[:0] = recents

        else:
            # note: Keypirinha will take care of removing duplicates
            suggestions += recents
