# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import ctypes

class Test(kp.Plugin):
    """
    This line should describe your plugin.

    This text should describe your plugin more in details. While both the line
    and this text are not required by the application to load this plugin, they
    may be used in the future to be automatically displayed to the end-user as a
    comprehensive description of your plugin and its purpose.
    """

    def __init__(self):
        super().__init__() # good pratice
        #self._debug = True # enables self.dbg() output
        self.dbg("CONSTRUCTOR")

    def __del__(self):
        self.dbg("DESTRUCTOR")

    def on_start(self):
        self.dbg("On Start")

    def on_catalog(self):
        self.dbg("On Catalog")

    def on_suggest(self, user_input, items_chain):
        self.dbg('On Suggest "{}" (items_chain[{}])'.format(
            user_input, len(items_chain)))

    def on_execute(self, item, action):
        msg = 'On Execute "{}" (action: {})'.format(item, action)
        self.dbg(msg)
        ctypes.windll.user32.MessageBoxW(None, msg, "TEST PLUGIN", 0)

    def on_activated(self):
        self.dbg("On App Activated")

    def on_deactivated(self):
        self.dbg("On App Deactivated")

    def on_events(self, flags):
        self.dbg("On event(s) (flags {:#x})".format(flags))
