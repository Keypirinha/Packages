# Keypirinha launcher (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_net as kpnet
import os
import xml.etree.ElementTree as ET

class SapGUI(kp.Plugin):
    _debug = False
    """
    Show SAPGui Entries to log ong
    """

    # Constants
    DEFAULT_SAPGUI_PATH = "%ProgramFiles(x86)%\\SAP\\FrontEnd\\SAPgui\\sapgui.exe"
    DEFAULT_XML_PATH = "%APPDATA%\\SAP\\Common\\SAPUILandscape.xml"

    # Variables
    sapgui_path = DEFAULT_SAPGUI_PATH
    xml_path = DEFAULT_XML_PATH

    def __init__(self):
        super().__init__()

    def on_start(self):
        gui = ET.parse(os.path.expandvars(self.xml_path))
        todos = gui.findall('Services/Service')
        self.itens = {}
        for el in todos:
            self.itens[str(el.get('uuid'))] = ItemSapGUI(str(el.get('name')), str(el.get('systemid')), str(el.get('server')))

    def on_catalog(self):
        catalog = []
        for uuid, item in self.itens.items():
            self.dbg(item.nome)
            catalog.append(self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label=item.nome,
                short_desc=item.systemid,
                target=uuid,
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.NOARGS,
            ))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        pass

    def on_execute(self, item, action):
        self.dbg(item)
        self.dbg(self.itens[item.target()])
        command = "\""+ self.sapgui_path +"\" " + self.itens[item.target()].ip + " " + self.itens[item.target()].instance
        self.dbg(command)
        os.system(os.path.expandvars(command))

    def on_activated(self):
        pass

    def on_deactivated(self):
        pass

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()
            self.on_catalog()

    def _read_config(self):
        settings = self.load_settings()

        self.xml_path = settings.get_stripped("xml_path", "main", self.DEFAULT_XML_PATH)
        self.sapgui_path = settings.get_stripped("sapgui_path", "main", self.DEFAULT_SAPGUI_PATH)

class ItemSapGUI():
    nome = ""
    systemid = ""
    ip = ""
    instance = ""

    def __init__(self, nome, systemid, server):
        self.nome = nome
        self.systemid = systemid
        try:
            (self.ip, self.instance) = server.split(":")
            self.instance = self.instance.replace('32', '')
        except ValueError:
            self.ip = server
        
