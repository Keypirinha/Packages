# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
from keypirinha_wintypes import FOLDERID
import os.path
import winreg
import urllib.parse

class WinSCP(kp.Plugin):
    """
    Launch WinSCP sessions.

    This plugin automatically detects the installed version of the official
    WinSCP distribution and lists its configured sessions so they can be
    launched directly without having to pass through the sessions selection
    dialog. The portable version of WinSCP can also be registered in package's
    dedicated configuration file.
    """

    DIST_SECTION_PREFIX = "dist/" # lower case
    EXE_NAME_OFFICIAL = "WinSCP.exe"
    INI_NAME_OFFICIAL = "WinSCP.ini"

    default_icon_handle = None
    distros = {}

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_config()

    def on_catalog(self):
        self._read_config()

        catalog = []
        for distro_name, distro in self.distros.items():
            if not distro['enabled']:
                continue
            # catalog the executable
            catalog.append(self.create_item(
                category=kp.ItemCategory.FILE,
                label=distro['label'],
                short_desc="",
                target=distro['exe_file'],
                args_hint=kp.ItemArgsHint.ACCEPTED,
                hit_hint=kp.ItemHitHint.KEEPALL))
            # catalog the configured sessions, if any
            for session_name in distro['sessions']:
                catalog.append(self.create_item(
                    category=kp.ItemCategory.REFERENCE,
                    label="{}: {}".format(distro['label'], session_name),
                    short_desc='Launch {} "{}" session'.format(
                        distro['label'], session_name),
                    target=kpu.kwargs_encode(
                        dist=distro_name, session=session_name),
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.NOARGS))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if items_chain and items_chain[-1].category() == kp.ItemCategory.FILE:
            clone = items_chain[-1].clone()
            clone.set_args(user_input)
            self.set_suggestions([clone])

    def on_execute(self, item, action):
        if item.category() == kp.ItemCategory.FILE:
            kpu.execute_default_action(self, item, action)
            return

        if item.category() != kp.ItemCategory.REFERENCE:
            return

        # extract info from item's target property
        try:
            item_target = kpu.kwargs_decode(item.target())
            distro_name = item_target['dist']
            session_name = item_target['session']
        except Exception as exc:
            self.dbg(str(exc))
            return

        # check if the desired distro is available and enabled
        if distro_name not in self.distros:
            self.warn('Could not execute item "{}". Distro "{}" not found.'.format(item.label(), distro_name))
            return
        distro = self.distros[distro_name]
        if not distro['enabled']:
            self.warn('Could not execute item "{}". Distro "{}" is disabled.'.format(item.label(), distro_name))
            return

        # check if the desired session still exists
        if session_name not in distro['sessions']:
            self.warn('Could not execute item "{}". Session "{}" not found in distro "{}".'.format(item.label(), session_name, distro_name))
            return

        # find the placeholder of the session name in the args list and execute
        sidx = distro['cmd_args'].index('%1')
        kpu.shell_execute(
            distro['exe_file'],
            args=distro['cmd_args'][0:sidx] + [session_name] + distro['cmd_args'][sidx+1:])

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self.info("Configuration changed, rebuilding catalog...")
            self.on_catalog()



    def _read_config(self):
        if self.default_icon_handle:
            self.default_icon_handle.free()
            self.default_icon_handle = None
        self.distros = {}

        settings = self.load_settings()
        for section_name in settings.sections():
            if not section_name.lower().startswith(self.DIST_SECTION_PREFIX):
                continue

            dist_name = section_name[len(self.DIST_SECTION_PREFIX):]

            detect_method = getattr(self, "_detect_distro_{}".format(dist_name.lower()), None)
            if not detect_method:
                self.err("Unknown WinSCP distribution name: ", dist_name)
                continue

            dist_path = settings.get_stripped("path", section_name)
            dist_enable = settings.get_bool("enable", section_name)
            dist_ini_path = settings.get_stripped("ini_path", section_name)

            dist_props = detect_method(
                dist_enable,
                settings.get_stripped("label", section_name),
                dist_path,
                dist_ini_path)

            if not dist_props:
                if dist_path:
                    self.warn('WinSCP distribution "{}" not found in: {}'.format(dist_name, dist_path))
                elif dist_enable:
                    self.warn('WinSCP distribution "{}" not found'.format(dist_name))
                continue

            self.distros[dist_name.lower()] = {
                'orig_name': dist_name,
                'enabled': dist_props['enabled'],
                'label': dist_props['label'],
                'exe_file': dist_props['exe_file'],
                'cmd_args': dist_props['cmd_args'],
                'sessions': dist_props['sessions']}

            if dist_props['enabled'] and not self.default_icon_handle:
                self.default_icon_handle = self.load_icon(
                    "@{},0".format(dist_props['exe_file']))
                if self.default_icon_handle:
                    self.set_default_icon(self.default_icon_handle)



    def _detect_distro_official(self, given_enabled, given_label, given_path, given_ini_path):
        dist_props = {
            'enabled': given_enabled,
            'label': given_label,
            'exe_file': None,
            'cmd_args': ['%1'],
            'sessions': []}

        # label
        if not dist_props['label']:
            dist_props['label'] = "WinSCP"

        # enabled? don't go further if not
        if dist_props['enabled'] is None:
            dist_props['enabled'] = True
        if not dist_props['enabled']:
            return dist_props

        # find executable
        exe_file = None
        if given_path:
            exe_file = os.path.normpath(os.path.join(given_path, self.EXE_NAME_OFFICIAL))
            if not os.path.exists(exe_file):
                exe_file = None
        if not exe_file:
            exe_file = self._autodetect_official_installreg()
        if not exe_file:
            exe_file = self._autodetect_startmenu(self.EXE_NAME_OFFICIAL, "WinSCP.lnk")
        if not exe_file:
            exe_file = self._autodetect_official_progfiles()
        if not exe_file:
            exe_file = self._autodetect_path(self.EXE_NAME_OFFICIAL)
        #if not exe_file:
        #    exe_file = self._autodetect_startmenu(self.EXE_NAME_OFFICIAL, "*winscp*.lnk")
        if not exe_file:
            return None
        dist_props['exe_file'] = exe_file

        # List configured sessions
        # To do that, we first have to detect if WinSCP is in Installed or
        # Portable mode. The steps are described by the official documentation
        # at: https://winscp.net/eng/docs/config#auto

        ini_file = None
        # If a configuration (INI) file is provided, we use that instead of
        # searching for it.
        if given_ini_path is not None and os.path.isfile(given_ini_path):
            ini_file = given_ini_path
        else:
            if given_ini_path is not None:
                self.err("Failed to read INI file:", given_ini_path)

            expected_ini_locations = (
                # along with the exe file
                os.path.join(os.path.dirname(exe_file), self.INI_NAME_OFFICIAL),
                # in "%USERPROFILE%\AppData\Roaming" folder (DIRECTLY)
                os.path.join(
                    kpu.shell_known_folder_path(FOLDERID.RoamingAppData.value),
                    self.INI_NAME_OFFICIAL))

            for ini_location in expected_ini_locations:
                if os.path.isfile(ini_location):
                    ini_file = ini_location
                    break

        if ini_file is not None:
            # While the ini file format seems to be standard (i.e.: parseable
            # with the configparser Python module), we choose the lazy way for
            # performance reasons and because we only need the name of the
            # configured sessions.
            ini_section_prefix = "[sessions\\"
            try:
                ini_content = kpu.chardet_slurp(ini_file)
            except Exception:
                self.err("Failed to read file:", ini_file)
                return None
            for ini_line in iter(ini_content.splitlines()):
                if ini_line.lower().startswith(ini_section_prefix) and ini_line.endswith(']'):
                    dist_props['sessions'].append(
                        urllib.parse.unquote(
                            ini_line[len(ini_section_prefix):-1]))
            ini_content = None

            dist_props['cmd_args'].insert(0, '/ini=' + ini_file)
        else:
            try:
                hkey = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    'Software\\Martin Prikryl\\WinSCP 2\\Sessions')
                index = 0
                while True:
                    try:
                        session_name = winreg.EnumKey(hkey, index)
                        index += 1
                        dist_props['sessions'].append(
                            urllib.parse.unquote(
                                session_name, encoding='utf-8'))
                    except OSError:
                        break
                winreg.CloseKey(hkey)
            except OSError:
                pass

        return dist_props



    def _autodetect_official_installreg(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\winscp3_is1",
                access=winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
            value = winreg.QueryValueEx(key, "InstallLocation")[0]
            winreg.CloseKey(key)
            exe_file = os.path.join(value, self.EXE_NAME_OFFICIAL)
            if os.path.exists(exe_file):
                return exe_file
        except:
            pass
        return None

    def _autodetect_official_progfiles(self):
        for hive in ('%PROGRAMFILES%', '%PROGRAMFILES(X86)%'):
            exe_file = os.path.join(
                os.path.expandvars(hive), "WinSCP", self.EXE_NAME_OFFICIAL)
            if os.path.exists(exe_file):
                return exe_file

    def _autodetect_startmenu(self, exe_name, name_pattern):
        known_folders = (
            "{625b53c3-ab48-4ec1-ba1f-a1ef4146fc19}", # FOLDERID_StartMenu
            "{a4115719-d62e-491d-aa7c-e74b8be3b067}") # FOLDERID_CommonStartMenu

        found_link_files = []
        for kf_guid in known_folders:
            try:
                known_dir = kpu.shell_known_folder_path(kf_guid)
                found_link_files += [
                    os.path.join(known_dir, f)
                    for f in kpu.scan_directory(
                        known_dir, name_pattern, kpu.ScanFlags.FILES, -1)]
            except Exception as exc:
                self.dbg(str(exc))
                pass

        for link_file in found_link_files:
            try:
                link_props = kpu.read_link(link_file)
                if (link_props['target'].lower().endswith(exe_name) and
                        os.path.exists(link_props['target'])):
                    return link_props['target']
            except Exception as exc:
                self.dbg(str(exc))
                pass

        return None

    def _autodetect_path(self, exe_name):
        path_dirs = [
            os.path.expandvars(p.strip())
                for p in os.getenv("PATH", "").split(";") if p.strip() ]

        for path_dir in path_dirs:
            exe_file = os.path.join(path_dir, exe_name)
            if os.path.exists(exe_file):
                return exe_file

        return None
