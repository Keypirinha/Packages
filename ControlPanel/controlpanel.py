# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import os.path
import winreg

class ControlPanel(kp.Plugin):
    """
    Launch Windows' Control Panel items.

    This plugin allows to search for and open system's Control Panels. A Control
    Panel is a graphical interface component of Windows that allows the
    configuration of the operating system and its core components.
    Search for the "Control Panel:" prefix in the Catalog to list the available
    control panels.
    """

    panel_items = {} # 'clsid': {item_info}

    def __init__(self):
        super().__init__()

    def on_catalog(self):
        # free previously loaded icons if needed
        for cpi_clsid, cpi in self.panel_items.items():
            if cpi['icon_handle']:
                cpi['icon_handle'].free()

        # get the list of available control panel items from the system
        self.panel_items = self._list_items()

        # build plugin's catalog and commit it
        catalog = []
        for cpi_clsid, cpi in self.panel_items.items():
            catalog.append(self.create_item(
                category=kp.ItemCategory.REFERENCE,
                label="Control Panel: " + cpi['label'],
                short_desc=cpi['short_desc'],
                target=cpi['clsid'],
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.NOARGS,
                icon_handle=cpi['icon_handle']))
        self.set_catalog(catalog)

    def on_execute(self, item, action):
        try:
            cpitem = self.panel_items[item.target()]
        except KeyError:
            self.warn("Control Panel item not found with ID:", item.target())
            return

        if cpitem['canonical_name'] is not None:
            control_exe = os.path.expandvars("%SYSTEMROOT%\\System32\\control.exe")
            kpu.shell_execute(control_exe, args=["/name", cpitem['canonical_name']])
        elif cpitem['open_command'] is not None:
            cmd_exe = os.path.expandvars("%SYSTEMROOT%\\System32\\cmd.exe")
            kpu.shell_execute(cmd_exe, args="/C " + cpitem['open_command'])

    def _list_items(self):
        cpitems = {}
        try:
            reg_ns = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\ControlPanel\\NameSpace")
            reg_classes = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "CLSID")
            panel_idx = 0
            while 1:
                clsid = winreg.EnumKey(reg_ns, panel_idx)
                panel_idx += 1
                try:
                    reg_clsid = winreg.OpenKey(reg_classes, clsid)
                    cpitem_info = self._list_item_info(clsid, reg_clsid)
                    if cpitem_info:
                        cpitems[cpitem_info['clsid']] = cpitem_info
                except OSError:
                    pass
        except OSError:
            pass
        return cpitems

    def _list_item_info(self, clsid, reg_clsid):
        def _getregstr(hkey, sub_path, value_name):
            try:
                if sub_path is not None:
                    hkey_sub = winreg.OpenKey(hkey, sub_path)
                else:
                    hkey_sub = hkey
                (val, typ) = winreg.QueryValueEx(hkey_sub, value_name)
                if sub_path is not None:
                    winreg.CloseKey(hkey_sub)
                if isinstance(val, str) and len(val) > 0:
                    return val
            except OSError:
                pass
            return None

        cpitem = {
            'clsid': clsid,
            'canonical_name': _getregstr(reg_clsid, None, "System.ApplicationName"),
            'open_command': _getregstr(reg_clsid, "Shell\\Open\\Command", None),
            'label': None,
            'short_desc': None,
            'icon_location': _getregstr(reg_clsid, "DefaultIcon", None),
            'icon_handle': None}

        # skip item if it doesn't have a canonical name or a command to execute
        if not cpitem['canonical_name'] and not cpitem['open_command']:
            return None

        # label
        location = _getregstr(reg_clsid, None, "LocalizedString")
        if location is not None:
            cpitem['label'] = kpu.shell_string_resource(location)
        if cpitem['label'] is None:
            cpitem['label'] = _getregstr(reg_clsid, None, None)

        # skip item if it doesn't have a label
        if not cpitem['label']:
            return None

        # short_desc
        location = _getregstr(reg_clsid, None, "InfoTip")
        if location is not None:
            cpitem['short_desc'] = kpu.shell_string_resource(location)
        if cpitem['short_desc'] is None:
            cpitem['short_desc'] = ""

        # icon
        if cpitem['icon_location'] is not None:
            if cpitem['icon_location'][0] != '@':
                cpitem['icon_location'] = '@' + cpitem['icon_location']
            cpitem['icon_handle'] = self.load_icon(cpitem['icon_location'])

        return cpitem
