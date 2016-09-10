# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import os.path
import winreg
import xml.etree.ElementTree as ET

class FileZilla(kp.Plugin):
    """
    Launch FileZilla Client sessions.

    This plugin automatically detects the installed version of the official
    FileZilla Client distribution and lists its configured sessions so they can
    be launched directly without having to pass through the sessions selection
    dialog. The portable version of FileZilla Client can also be registered in
    package's dedicated configuration file.
    """

    DIST_SECTION_PREFIX = "dist/" # lower case
    EXE_NAME_OFFICIAL = "filezilla.exe"

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
        except Exception as e:
            self.dbg(e)
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
        session_arg = distro['sessions'][session_name]

        # find the placeholder of the session name in the args list and execute
        sidx = distro['cmd_args'].index('%1')
        kpu.shell_execute(
            distro['exe_file'],
            args=distro['cmd_args'][0:sidx] + [session_arg] + distro['cmd_args'][sidx+1:])

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
                self.err("Unknown FileZilla distribution name: ", dist_name)
                continue

            dist_path = settings.get_stripped("path", section_name)
            dist_enable = settings.get_bool("enable", section_name)

            dist_props = detect_method(
                dist_enable,
                settings.get_stripped("label", section_name),
                dist_path)

            if not dist_props:
                if dist_path:
                    self.warn('FileZilla distribution "{}" not found in: {}'.format(dist_name, dist_path))
                elif dist_enable:
                    self.warn('FileZilla distribution "{}" not found'.format(dist_name))
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



    def _detect_distro_official(self, given_enabled, given_label, given_path):
        dist_props = {
            'enabled': given_enabled,
            'label': given_label,
            'exe_file': None,
            'cmd_args': ['--site', '%1'],
            'sessions': {}}

        # label
        if not dist_props['label']:
            dist_props['label'] = "FileZilla"

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
            exe_file = self._autodetect_startmenu(self.EXE_NAME_OFFICIAL, "FileZilla.lnk")
        if not exe_file:
            exe_file = self._autodetect_official_progfiles()
        if not exe_file:
            exe_file = self._autodetect_path(self.EXE_NAME_OFFICIAL)
        #if not exe_file:
        #    exe_file = self._autodetect_startmenu(self.EXE_NAME_OFFICIAL, "*filezilla*.lnk")
        if not exe_file:
            return None
        dist_props['exe_file'] = exe_file

        # List configured sessions
        # To do that, we first have to detect if FileZilla is in Installed or
        # Portable mode. The steps are described by the official documentation
        # at: https://wiki.filezilla-project.org/Client_Installation#With_zip_version

        # select config file
        if os.path.isfile(os.path.join(os.path.dirname(exe_file), "fzdefaults.xml")):
            # Portable mode enabled, configuration files are stored in the
            # 'config' directory located in the same directory than the
            # executable
            sessions_file = os.path.join(
                os.path.dirname(exe_file), "config", "sitemanager.xml")
        else:
            # Installed mode. Configuration files are stored into the
            # "%USERPROFILE%\AppData\Roaming\FileZilla" directory
            sessions_file = os.path.join(
                kpu.shell_known_folder_path(
                    "{3eb685db-65f9-4cf6-a03a-e3ef65729f3d}"),
                "FileZilla", "sitemanager.xml")

        # read and parse config file
        xml_sessions = []
        if sessions_file is not None and os.path.isfile(sessions_file):
            def _recurse_folder(xml_folder):
                folder_sessions = []
                xml_servers = xml_folder.findall("./Server")
                for xml_svr in xml_servers:
                    for xml_child in xml_svr:
                        if xml_child.tag.lower() == "name":
                            folder_sessions.append(
                                [xml_folder.text, xml_child.text])
                xml_subfolders = xml_folder.findall("./Folder")
                for xml_subfolder in xml_subfolders:
                    folder_sessions += [
                        [xml_folder.text] + subsess
                            for subsess in _recurse_folder(xml_subfolder)]
                return folder_sessions

            try:
                xml_content = kpu.chardet_slurp(sessions_file)
            except Exception:
                self.err("Failed to read file:", sessions_file)
                return None

            try:
                xml_root = ET.fromstring(xml_content)

                xml_servers = xml_root.findall("./Servers/Server")
                for xml_svr in xml_servers:
                    for xml_child in xml_svr:
                        if xml_child.tag.lower() == "name":
                            xml_sessions.append([xml_child.text])

                xml_folders = xml_root.findall("./Servers/Folder")
                for xml_folder in xml_folders:
                    xml_sessions += _recurse_folder(xml_folder)
            except Exception as e:
                self.err('Failed to parse "{}". Error: {}'.format(sessions_file, e))

        # encode session names
        # FileZilla needs the session name to be escaped when passed as a
        # command line argument. Slashes and backslashes must be prefixed by a
        # backslash.
        for session_elems in xml_sessions:
            session_name = '/'.join(session_elems)
            session_arg = '0/' + '/'.join([
                e.replace('\\', '\\\\').replace('/', '\\/') # CAUTION: order matters!
                    for e in session_elems])
            dist_props['sessions'][session_name] = session_arg

        return dist_props



    def _autodetect_official_installreg(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FileZilla Client",
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
            for dir_name in ('FileZilla FTP Client', 'FileZilla Client', 'FileZilla'):
                exe_file = os.path.join(
                    os.path.expandvars(hive), dir_name, self.EXE_NAME_OFFICIAL)
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
            except Exception as e:
                self.dbg(e)
                pass

        for link_file in found_link_files:
            try:
                link_props = kpu.read_link(link_file)
                if (link_props['target'].lower().endswith(exe_name) and
                        os.path.exists(link_props['target'])):
                    return link_props['target']
            except Exception as e:
                self.dbg(e)
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
