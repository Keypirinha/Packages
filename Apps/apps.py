# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_wintypes as kpwt
import os
import glob
import re
import time
import traceback

class _BasePlugin(kp.Plugin):
    ITEMCAT_CUSTOMCMD = kp.ItemCategory.USER_BASE + 1

    CONFIG_SECTION_MAIN = "main"
    CONFIG_SECTION_CUSTOMCMD_DEFAULTS = "custom_commands"
    CONFIG_SECTION_CUSTOMCMD = "cmd"

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_config()

    def on_suggest(self, user_input, items_chain):
        if items_chain and items_chain[-1].category() in (
                kp.ItemCategory.FILE, self.ITEMCAT_CUSTOMCMD):
            clone = items_chain[-1].clone()
            clone.set_args(user_input)
            self.set_suggestions([clone])

    def on_execute(self, item, action):
        kpu.execute_default_action(self, item, action)

    def _read_config(self):
        raise NotImplementedError

    def _log_catalog_duration(self, start_time, items_count):
        elapsed = time.perf_counter() - start_time
        self.info("Cataloged {} item{} in {:.1f} seconds".format(
                        items_count, "s"[items_count==1:], elapsed))

    def _read_env_path(self):
        path_str = os.getenv("PATH", "")
        path = [
            os.path.expandvars(p.strip())
                for p in path_str.split(";") if p.strip() ]

        return (path_str, path)

    def _read_env_pathext(self):
        # get PATHEXT
        # real life examples of PATHEXT value:
        #   * WinXP machine: .COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH
        #   * Win8 machine: .COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC
        pathext_str = os.getenv("PATHEXT", "")
        pathext = [
            "*" + p.strip() for p in
                pathext_str.split(";")
                    if p.strip() and p.strip()[0] == "."]
        if not pathext:
            pathext = [
                "*.COM", "*.EXE", "*.BAT", "*.CMD", "*.VBS", "*.VBE", "*.JS",
                "*.JSE", "*.WSF", "*.WSH", "*.MSC"]

        return (pathext_str, pathext)

    def _catalog_knownfolder(self, kf_guid, kf_label, kf_desc, recursive_scan):
        try:
            kf_path = kpu.shell_known_folder_path(kf_guid)
        except OSError:
            self.warn("Failed to get path of known folder {}".format(kf_label))
            return []

        if self.should_terminate():
            return []

        max_scan_level = -1 if recursive_scan else 0
        try:
            files = kpu.scan_directory(
                kf_path, ('*'), flags=kpu.ScanFlags.FILES,
                max_level=max_scan_level)
        except IOError:
            return []

        if self.should_terminate():
            return []

        catalog = []
        for relative in files:
            f = os.path.normpath(os.path.join(kf_path, relative))
            label = os.path.splitext(os.path.basename(f))[0]
            desc = os.path.dirname(relative)

            if not len(desc):
                desc = os.path.basename(kf_path)
            if not len(desc):
                desc = label
            desc = kf_desc + ": " + desc

            catalog.append(self.create_item(
                category=kp.ItemCategory.FILE,
                label=label,
                short_desc=desc,
                target=f,
                args_hint=kp.ItemArgsHint.ACCEPTED,
                hit_hint=kp.ItemHitHint.KEEPALL))

        return catalog


class StartMenu(_BasePlugin):
    """Scan files in user's Start Menu"""

    DEFAULT_SCAN_START_MENU = True

    scan_start_menu = DEFAULT_SCAN_START_MENU

    def __init__(self):
        super().__init__()

    def on_catalog(self):
        if not self.scan_start_menu:
            self.set_catalog([])
            return

        known_folders = (
            # folder, scan recursively
            (kpwt.FOLDERID.CommonStartup, True),
            (kpwt.FOLDERID.Startup, True),
            (kpwt.FOLDERID.StartMenu, True),
            (kpwt.FOLDERID.CommonStartMenu, True))

        catalog = []
        for kf in known_folders:
            catalog.extend(self._catalog_knownfolder(
                kf[0].value, kf[0].name, "Start Menu", kf[1]))
            if self.should_terminate():
                return

        self.set_catalog(catalog)

    def on_events(self, flags):
        must_catalog = False

        if flags & kp.Events.PACKCONFIG:
            if self._read_config():
                must_catalog = True

        if (flags & kp.Events.STARTMENU) and self.scan_start_menu:
            must_catalog = True

        if must_catalog:
            self.on_catalog()

    def _read_config(self):
        new_scan_start_menu = self.load_settings().get_bool(
            "scan_start_menu",
            self.CONFIG_SECTION_MAIN,
            self.DEFAULT_SCAN_START_MENU)
        config_changed = new_scan_start_menu != self.scan_start_menu
        self.scan_start_menu = new_scan_start_menu
        return config_changed


class Desktop(_BasePlugin):
    """Scan files in user's Desktop"""

    DEFAULT_SCAN_DESKTOP = True

    scan_desktop = DEFAULT_SCAN_DESKTOP

    def __init__(self):
        super().__init__()

    def on_catalog(self):
        if not self.scan_desktop:
            self.set_catalog([])
            return

        known_folders = (
            # folder, scan recursively
            (kpwt.FOLDERID.PublicDesktop, False),
            (kpwt.FOLDERID.Desktop, False))

        catalog = []
        for kf in known_folders:
            catalog.extend(self._catalog_knownfolder(
                kf[0].value, kf[0].name, "Desktop", kf[1]))
            if self.should_terminate():
                return

        self.set_catalog(catalog)

    def on_events(self, flags):
        must_catalog = False

        if flags & kp.Events.PACKCONFIG:
            if self._read_config():
                must_catalog = True

        if (flags & kp.Events.DESKTOP) and self.scan_desktop:
            must_catalog = True

        if must_catalog:
            self.on_catalog()

    def _read_config(self):
        new_scan_desktop = self.load_settings().get_bool(
            "scan_desktop",
            self.CONFIG_SECTION_MAIN,
            self.DEFAULT_SCAN_DESKTOP)
        config_changed = new_scan_desktop != self.scan_desktop
        self.scan_desktop = new_scan_desktop
        return config_changed


class EnvPath(_BasePlugin):
    """Scan executables in current PATH"""

    DEFAULT_SCAN_ENV_PATH = True

    scan_env_path = DEFAULT_SCAN_ENV_PATH

    pathext_str = ""
    pathext = []
    path_str = ""
    path = []

    def __init__(self):
        super().__init__()

    def on_catalog(self):
        if not self.scan_env_path:
            self.set_catalog([])
            return

        start = time.perf_counter()
        self.path_str, self.path = self._read_env_path()
        self.pathext_str, self.pathext = self._read_env_pathext()

        catalog = []
        for path_dir in self.path:
            try:
                entries = kpu.scan_directory(
                    path_dir, self.pathext, kpu.ScanFlags.FILES,
                    max_level=0)
            except OSError as exc:
                #self.dbg("Exception raised while scanning PATH:", exc)
                continue

            if self.should_terminate():
                return

            for entry in entries:
                entry_path = os.path.normpath(os.path.join(path_dir, entry))
                catalog.append(self.create_item(
                    category=kp.ItemCategory.FILE,
                    label=os.path.basename(entry),
                    short_desc="",
                    target=entry_path,
                    args_hint=kp.ItemArgsHint.ACCEPTED,
                    hit_hint=kp.ItemHitHint.KEEPALL))

        self.set_catalog(catalog)
        self._log_catalog_duration(start, len(catalog))

    def on_events(self, flags):
        must_catalog = False

        if flags & kp.Events.PACKCONFIG:
            if self._read_config():
                must_catalog = True

        if (flags & kp.Events.ENV) and self.scan_env_path and (
                os.getenv("PATH", "") != self.path_str or
                os.getenv("PATHEXT", "") != self.pathext_str):
            self.info("PATH changed, rebuilding catalog...")
            must_catalog = True

        if must_catalog:
            self.on_catalog()

    def _read_config(self):
        new_scan_env_path = self.load_settings().get_bool(
            "scan_env_path",
            self.CONFIG_SECTION_MAIN,
            self.DEFAULT_SCAN_ENV_PATH)
        config_changed = new_scan_env_path != self.scan_env_path
        self.scan_env_path = new_scan_env_path
        return config_changed


class ExtraPaths(_BasePlugin):
    """Scan files pointed at by the extra_paths setting"""

    pathext_str = ""
    pathext = []
    extra_paths = []

    def __init__(self):
        super().__init__()

    def on_catalog(self):
        start = time.perf_counter()
        self.pathext_str, self.pathext = self._read_env_pathext()

        catalog = []
        for user_extra_path in self.extra_paths:
            user_extra_path = user_extra_path.replace("/", os.sep)
            has_trailing_sep = user_extra_path.endswith(os.sep)

            if user_extra_path.startswith('::') and len(user_extra_path) >= 38:
                (guid, tail) = (user_extra_path[2:].split(os.sep, maxsplit=1) + [None] * 2)[:2]
                try:
                    kf_path = kpu.shell_known_folder_path(guid)
                    if tail is not None:
                        user_extra_path = os.path.normpath(os.path.join(kf_path, tail))
                    else:
                        user_extra_path = kf_path
                except OSError:
                    self.warn("Failed to get path of known folder from setting \"{}\"".format(user_extra_path))
                    continue
            else:
                user_extra_path = os.path.normpath(user_extra_path)

            #user_extra_path = os.path.expandvars(user_extra_path) # not needed
            if has_trailing_sep:
                user_extra_path += os.sep

            recursive_glob = "**" in user_extra_path
            for globbed_path in glob.iglob(user_extra_path, recursive=recursive_glob):
                if self.should_terminate():
                    return

                files = []
                if os.path.isdir(globbed_path):
                    try:
                        files = kpu.scan_directory(
                            globbed_path, self.pathext, kpu.ScanFlags.FILES,
                            max_level=0)
                    except IOError as exc:
                        self.warn(exc)
                        continue
                    files = [ os.path.join(globbed_path, f) for f in files ]
                elif os.path.isfile(globbed_path):
                    files = [globbed_path]
                else:
                    continue # duh?!

                if self.should_terminate():
                    return

                for f in files:
                    catalog.append(self.create_item(
                        category=kp.ItemCategory.FILE,
                        label=os.path.basename(f),
                        short_desc=f,
                        target=f,
                        args_hint=kp.ItemArgsHint.ACCEPTED,
                        hit_hint=kp.ItemHitHint.KEEPALL))
                    if len(catalog) % 100 == 0 and self.should_terminate():
                        return

        self.set_catalog(catalog)

        if len(self.extra_paths):
            self._log_catalog_duration(start, len(catalog))

    def on_events(self, flags):
        must_catalog = False

        if flags & kp.Events.PACKCONFIG:
            if self._read_config():
                must_catalog = True

        if ((flags & kp.Events.ENV) and len(self.extra_paths) and
                os.getenv("PATHEXT", "") != self.pathext_str):
            # some extra_paths implicitely make use of the PATHEXT env var
            must_catalog = True

        if must_catalog:
            self.on_catalog()

    def _read_config(self):
        new_extra_paths = self.load_settings().get_multiline(
            "extra_paths", self.CONFIG_SECTION_MAIN)
        config_changed = new_extra_paths != self.extra_paths
        self.extra_paths = new_extra_paths
        return config_changed


class CustomCmds(_BasePlugin):
    """
    Launch any predefined command line, optionally with argument placeholders
    """

    DEFAULT_ITEM_LABEL_FORMAT = "{cmd_name}"
    DEFAULT_HISTORY_KEEP = kp.ItemHitHint.NOARGS

    REGEX_PLACEHOLDER = re.compile(r"\{\{(q?args|q?\*|q?\d+)\}\}", re.ASCII)

    custom_cmds = {}

    def __init__(self):
        super().__init__()

    def on_catalog(self):
        catalog = []
        for cmd_name, custcmd in self.custom_cmds.items():
            if len(custcmd['cmds']) == 1:
                cmd_desc = "Custom command: " + custcmd['cmds'][0]
            else:
                cmd_desc = "{} custom commands. First: {}".format(len(custcmd['cmds']), custcmd['cmds'][0])
            catalog.append(self.create_item(
                category=self.ITEMCAT_CUSTOMCMD,
                label=custcmd['item_label'],
                short_desc=cmd_desc,
                target=cmd_name,
                args_hint=custcmd['args_hint'],
                hit_hint=custcmd['hit_hint'],
                icon_handle=custcmd['icon_handle']))

        self.set_catalog(catalog)

    def on_execute(self, item, action):
        # item's category is assumed to be self.ITEMCAT_CUSTOMCMD

        cmd_name = item.target()
        if cmd_name not in self.custom_cmds:
            self.warn('Could not execute item "{}". Custom command "{}" not found.'.format(item.label(), cmd_name))
            return

        custcmd = self.custom_cmds[cmd_name]

        cmd_lines = self._customcmd_apply_args(custcmd['cmds'][:], item.raw_args())
        for cmdline in cmd_lines:
            try:
                args = kpu.cmdline_split(cmdline)
                kpu.shell_execute(
                    args[0], args=args[1:],
                    verb="runas" if custcmd['elevated'] else "",
                    detect_nongui=custcmd['auto_terminal'])
            except:
                traceback.print_exc()

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()
            self.on_catalog()

    def _read_config(self):
        # free loaded icons
        for cmd_name, custcmd in self.custom_cmds.items():
            if custcmd['icon_handle']:
                custcmd['icon_handle'].free()

        self.custom_cmds = {}

        settings = self.load_settings()

        # read "custom_commands" section
        supported_history_keep_values = {
            'all': kp.ItemHitHint.KEEPALL,
            'cmd': kp.ItemHitHint.NOARGS,
            'none': kp.ItemHitHint.IGNORE}
        default_item_label_format = settings.get_stripped(
            "item_label",
            section=self.CONFIG_SECTION_CUSTOMCMD_DEFAULTS,
            fallback=self.DEFAULT_ITEM_LABEL_FORMAT)
        default_history_keep = settings.get_mapped(
            "history_keep",
            section=self.CONFIG_SECTION_CUSTOMCMD_DEFAULTS,
            fallback=self.DEFAULT_HISTORY_KEEP,
            map=supported_history_keep_values)
        default_auto_terminal = settings.get_bool(
            "auto_terminal",
            section=self.CONFIG_SECTION_CUSTOMCMD_DEFAULTS,
            fallback=True)

        # read "cmd" sections (custom commands)
        for section in settings.sections():
            if section.lower().startswith(self.CONFIG_SECTION_CUSTOMCMD + "/"):
                cmd_label = section[len(self.CONFIG_SECTION_CUSTOMCMD) + 1:].strip()
            else:
                continue

            if not len(cmd_label):
                self.warn('Ignoring empty custom command name (section "{}").'.format(section))
                continue
            forbidden_chars = (':;,/|\\')
            if any(c in forbidden_chars for c in cmd_label):
                self.warn(
                    'Forbidden character(s) found in custom command name "{}". Forbidden characters list "{}"'
                    .format(cmd_label, forbidden_chars))
                continue
            if cmd_label.lower() in self.custom_cmds.keys():
                self.warn('Ignoring duplicated custom command "{}" defined in section "{}".'.format(cmd_label, section))
                continue

            if not settings.get_bool("enable", section=section, fallback=True):
                continue

            cmd_lines = settings.get_multiline("cmd", section=section)
            if not len(cmd_lines):
                self.warn('Custom command "{}" does not have "cmd" value (or is empty). Ignored.'.format(cmd_label))
                continue

            item_label_format = settings.get(
                "item_label", section=section, fallback=default_item_label_format)
            cmd_item_label = item_label_format.format(
                cmd_name=cmd_label, plugin_name=self.friendly_name())

            cmd_hit_hint = settings.get_mapped(
                "history_keep", section=section, fallback=default_history_keep,
                map=supported_history_keep_values)

            cmd_auto_terminal = settings.get_bool(
                "auto_terminal", section=section, fallback=default_auto_terminal)

            cmd_elevated = settings.get_bool(
                "elevated", section=section, fallback=False)

            cmd_has_placeholders = any(map(
                lambda s: self.REGEX_PLACEHOLDER.search(s) is not None,
                cmd_lines))
            if cmd_has_placeholders:
                cmd_args_hint = kp.ItemArgsHint.ACCEPTED
            else:
                cmd_args_hint = kp.ItemArgsHint.FORBIDDEN

            self.custom_cmds[cmd_label.lower()] = {
                'label': cmd_label,
                'cmds': cmd_lines,
                'item_label': cmd_item_label,
                'args_hint': cmd_args_hint,
                'hit_hint': cmd_hit_hint,
                'icon_handle': self._customcmd_icon(cmd_lines),
                'auto_terminal': cmd_auto_terminal,
                'elevated': cmd_elevated}

    def _customcmd_icon(self, cmd_lines):
        #for cmdline in cmd_lines:
        #    try:
        #        args = kpu.cmdline_split(cmdline)
        #    except:
        #        traceback.print_exc()
        #        continue
        #    args[0] = kpu.shell_resolve_exe_path(args[0])
        #    if args[0] is not None:
        #        try:
        #            icon_handle = self.load_icon("file:///" + args[0])
        #            if icon_handle:
        #                return icon_handle
        #        except ValueError:
        #            pass
        return None

    def _customcmd_apply_args(self, cmd_lines, args_str):
        try:
            args = kpu.cmdline_split(args_str)
        except:
            traceback.print_exc()
            return cmd_lines

        final_cmd_lines = []
        for cmdline in cmd_lines:
            try:
                arg0 = kpu.cmdline_split(cmdline)[0]
                resolved_arg0 = kpu.shell_resolve_exe_path(arg0)
                if resolved_arg0 is not None:
                    arg0 = resolved_arg0
            except:
                traceback.print_exc()
                return cmd_lines

            start_pos = 0
            while True:
                rem = self.REGEX_PLACEHOLDER.search(cmdline, start_pos)
                if not rem:
                    break

                placeholder = rem.group(1)
                if placeholder in ("*", "args"):
                    args_str = args_str.strip()
                    cmdline = cmdline[0:rem.start()] + args_str + cmdline[rem.end():]
                    start_pos = rem.start() + len(args_str)
                elif placeholder in ("q*", "qargs"):
                    if not len(args):
                        cmdline = cmdline[0:rem.start()] + cmdline[rem.end():]
                        start_pos = rem.start()
                    else:
                        quoted_args = kpu.cmdline_quote(args, force_quote=True)
                        cmdline = cmdline[0:rem.start()] + quoted_args + cmdline[rem.end():]
                        start_pos = rem.start() + len(quoted_args)
                else:
                    force_quote = False
                    if placeholder[0] == "q":
                        force_quote = True
                        placeholder = placeholder[1:]

                    arg_idx = int(placeholder)
                    if arg_idx == 0:
                        quoted_arg = kpu.cmdline_quote(arg0, force_quote=force_quote)
                    else:
                        arg_idx = arg_idx - 1
                        quoted_arg = kpu.cmdline_quote(
                            args[arg_idx] if arg_idx < len(args) else "",
                            force_quote=force_quote)

                    cmdline = cmdline[0:rem.start()] + quoted_arg + cmdline[rem.end():]
                    start_pos = rem.start() + len(quoted_arg)

            final_cmd_lines.append(cmdline)

        return final_cmd_lines
