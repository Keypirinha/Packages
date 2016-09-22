# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import ctypes
import threading

class WinampRemote:
    """
    A utility class to ease IPC with a running instance of Winamp.
    Makes intensive use of the standard *ctypes* module.
    """

    # variables (private)
    wa_hwnd = None   # handle of winamp's main window
    wa_version = (0) # winamp version tuple: (major, minor)
    wa_procid = 0    # id of winamp's process
    wa_hproc = None  # handle of winamp's process

    # constants: current winamp state in response to the ISPLAYING message
    # see the get_state() method for more info
    STATE_PLAYING = 1
    STATE_PAUSED = 3
    STATE_NOTPLAYING = 0
    STATE_ERROR = None

    # private constants from windows headers
    _WM_USER = 1024
    _WM_COMMAND = 0x0111
    _PROCESS_VM_READ = 0x0010
    _PROCESS_VM_WRITE = 0x0020

    # private constants: windows system error codes
    _WINERR_ACCESS_DENIED = 5
    _WINERR_INVALID_WINDOW_HANDLE = 1400

    # private constants: winamp ipc messages from wa_ipc.h (winamp sdk)
    _WM_WA_IPC = _WM_USER
    _IPC_GETVERSION = 0
    _IPC_ISPLAYING = 104
    _IPC_SETPLAYLISTPOS = 121
    _IPC_SETVOLUME = 122
    _IPC_GETLISTLENGTH = 124
    _IPC_GETLISTPOS = 125
    _IPC_GETPLAYLISTTITLEW = 213

    # private constants: defined in winampcmd.h (winamp sdk)
    _WA_BUTTON_COMMAND_PREVIOUS = 40044
    _WA_BUTTON_COMMAND_PLAY = 40045
    _WA_BUTTON_COMMAND_PAUSE = 40046
    _WA_BUTTON_COMMAND_STOP = 40047
    _WA_BUTTON_COMMAND_NEXT = 40048

    # exception class for internal use
    class Exception(OSError):
        def __init__(self, winerr=None):
            if not winerr:
                winerr = ctypes.GetLastError()
            super().__init__(0, ctypes.FormatError(winerr), None, winerr)

    def __init__(self):
        super().__init__()

    def __del__(self):
        # we call uninit() here just in case, but remember we cannot assume
        # __del__ will ever be called
        self.uninit()

    def uninit(self):
        """
        Frees attached resources and resets internal state. This should
        **always** be called after you are done using this object.
        """
        if self.wa_hproc:
            try:
                ctypes.windll.kernel32.CloseHandle(self.wa_hproc)
            except:
                pass
        self.wa_hwnd = None
        self.wa_version = (0)
        self.wa_procid = 0
        self.wa_hproc = None

    def ping(self):
        """
        Returns a boolean that indicates if a Winamp instance has been found
        and we have been able to communicate with it.
        """
        if self._send_msg(WinampRemote._WM_WA_IPC, 0, WinampRemote._IPC_GETVERSION):
            return True
        else:
            return False

    def version(self):
        """
        Returns Winamp's version tuple if Winamp instance has been found and we
        have been able to communicate with it. Tuple is: (major, minor).
        Returns None otherwise.
        """
        return self.wa_version if self.ping() else None

    def get_state(self):
        """Returns one of the STATE_* values."""
        return self._send_msg(WinampRemote._WM_WA_IPC, 0, WinampRemote._IPC_ISPLAYING)

    def get_list_length(self):
        """
        Returns the number of tracks in the current playlist, or None in case of
        error.
        Requires Winamp 2.0+.
        """
        return self._send_msg(WinampRemote._WM_WA_IPC, 0, WinampRemote._IPC_GETLISTLENGTH)

    def get_list_position(self):
        """
        Returns the current playlist position (zero-based), or None in case of
        error.
        Requires Winamp 2.05+.
        """
        return self._send_msg(WinampRemote._WM_WA_IPC, 0, WinampRemote._IPC_GETLISTPOS)

    def set_list_position(self, position, do_play=False):
        """
        Sets the playlist to a specified position (zero-based).
        Returns a boolean that indicate if the operation has been successful.
        Requires Winamp 2.0+.
        """
        result = self._send_msg(WinampRemote._WM_WA_IPC, position, WinampRemote._IPC_SETPLAYLISTPOS)
        if result is None:
            return False
        if do_play:
            # the PLAY command will just resume the current track if it was in
            # PAUSE state, so send a STOP request first
            self.do_stop()
            return self.do_play()
        return True

    def get_track_title(self, position=None):
        """
        Returns the title as shown in the playlist window of the track at a
        given position (zero-based), or None in case of error.
        If no position is given, gets the title of the current track.
        Requires Winamp 2.04+.
        """
        if position is None:
            position = self.get_list_position()
            if position is None:
                return None
        address = self._send_msg(WinampRemote._WM_WA_IPC, position, WinampRemote._IPC_GETPLAYLISTTITLEW)
        if not address:
            return None
        return self._read_remote_string(address)

    def get_tracks_titles(self):
        """
        Returns a list of all the tracks titles of the current playlist, as show
        in the playlist window. Some elements in the returned list might be None
        if they were not available at request time.
        Returns None if an error occurred.
        Requires Winamp 2.04+.
        """
        count = self.get_list_length()
        if count is None:
            return None
        playlist = []
        for idx in range(count):
            playlist.append(self.get_track_title(idx))
        return playlist

    def get_volume(self):
        """
        Returns the current volume of Winamp (between the range of 0 to 255), or
        None if an error occurred.
        Requires Winamp 2.0+.
        """
        return self._send_msg(WinampRemote._WM_WA_IPC, -666, WinampRemote._IPC_SETVOLUME)

    def set_volume(self, volume):
        """
        Sets the volume of Winamp (between the range of 0 to 255).
        Returns a boolean to indicate if the operation was successful.
        Requires Winamp 2.0+.
        """
        if self._send_msg(WinampRemote._WM_WA_IPC,
                volume, WinampRemote._IPC_SETVOLUME) is not None:
            return True
        else:
            return False

    def do_previous(self):
        """Simulates a press to the PREVIOUS button"""
        if self._send_msg(WinampRemote._WM_COMMAND,
                WinampRemote._WA_BUTTON_COMMAND_PREVIOUS, 0) is not None:
            return True
        else:
            return False

    def do_play(self):
        """Simulates a press to the PLAY button"""
        if self._send_msg(WinampRemote._WM_COMMAND,
                WinampRemote._WA_BUTTON_COMMAND_PLAY, 0) is not None:
            return True
        else:
            return False

    def do_playpause(self):
        """Simulates a press to the PAUSE button"""
        if self._send_msg(WinampRemote._WM_COMMAND,
                WinampRemote._WA_BUTTON_COMMAND_PAUSE, 0) is not None:
            return True
        else:
            return False

    def do_stop(self):
        """Simulates a press to the STOP button"""
        if self._send_msg(WinampRemote._WM_COMMAND,
                WinampRemote._WA_BUTTON_COMMAND_STOP, 0) is not None:
            return True
        else:
            return False

    def do_next(self):
        """Simulates a press to the NEXT button"""
        if self._send_msg(WinampRemote._WM_COMMAND,
                WinampRemote._WA_BUTTON_COMMAND_NEXT, 0) is not None:
            return True
        else:
            return False

    def _find_winamp(self):
        """
        Finds the Winamp instance and (re)initializes the internal state.
        Returns a boolean to indicate if the whole init/finding process is
        successful. May raise a WinampRemote.Exception exception.
        """
        # find the main window
        self.wa_hwnd = ctypes.windll.user32.FindWindowW("Winamp v1.x", None)
        if not self.wa_hwnd:
            winerr = ctypes.GetLastError()
            if winerr:
                raise WinampRemote.Exception(winerr)
            self.uninit()
            return False # winamp instance not found

        # fetch the version number, this also allows us to ping the application
        # and to ensure we can do IPC with it
        ctypes.windll.kernel32.SetLastError(0)
        result = ctypes.windll.user32.SendMessageW(
            self.wa_hwnd, WinampRemote._WM_WA_IPC, 0,
            WinampRemote._IPC_GETVERSION)
        winerr = ctypes.GetLastError()
        if winerr:
            self.uninit()
            if winerr != WinampRemote._WINERR_ACCESS_DENIED:
                raise WinampRemote.Exception(winerr)
            return False # winamp instance found but not accessible
        self.wa_version = (
            (result & 0xFF00) >> 12,
            int("{:#X}".format((result & 0x00FF)), 16))

        # get a handle to the process so we can exchange data by simulating
        # "in-process" communication. trick detailed here:
        # http://winampboard.radionomy.net/showthread.php?p=1494866
        result = ctypes.c_uint32()
        ctypes.windll.kernel32.SetLastError(0)
        ctypes.windll.user32.GetWindowThreadProcessId(
            self.wa_hwnd, ctypes.byref(result))
        if ctypes.GetLastError():
            self.uninit()
            return False
        self.wa_procid = int(result.value)

        self.wa_hproc = ctypes.windll.kernel32.OpenProcess(
            WinampRemote._PROCESS_VM_READ, False, self.wa_procid)
        if not self.wa_hproc:
            winerr = ctypes.GetLastError()
            self.uninit()
            raise WinampRemote.Exception(winerr)

        return True

    def _send_msg(self, msgId, wparam=0, lparam=0):
        """
        A util method to send a simple message to a window. Lazy init is
        supported.
        """
        for i in range(2):
            try:
                ctypes.windll.kernel32.SetLastError(0)
                result = ctypes.windll.user32.SendMessageW(
                    self.wa_hwnd, msgId, wparam, lparam)
                winerr = ctypes.GetLastError()
            except Exception:
                return None

            if winerr == 0:
                return result
            elif winerr == WinampRemote._WINERR_INVALID_WINDOW_HANDLE:
                try: # we've lost winamp, try to find it a last time
                    if self._find_winamp():
                        continue
                except:
                    pass
                return None
            return None

    def _read_remote_string(self, address, as_unicode=True):
        """Reads a string from Winamp's memory address space."""
        if not self.wa_hproc:
            #print("Trying to read Winamp's memory without having found any instance!")
            return None

        buflen = 1024
        if as_unicode:
            buffer = ctypes.create_unicode_buffer(buflen)
        else:
            buffer = ctypes.create_string_buffer(buflen)
        bytes_read = ctypes.c_size_t(0)

        if not ctypes.windll.kernel32.ReadProcessMemory(
                self.wa_hproc, address, buffer, buflen, ctypes.byref(bytes_read)):
            winerr = ctypes.GetLastError()
            #print(
            #    "Failed to read memory from Winamp's memory space:",
            #    ctypes.FormatError(winerr))
            return None

        return buffer.value


class Winamp(kp.Plugin):
    """
    Control and track selection of Winamp.

    This plugin offers simple playback control of the currently running instance
    of Winamp, if any (i.e.: Play, Pause, Stop, Previous, Next). A "Jump To
    Track" feature is also available to search through the current playing list
    and directly play the selected track.
    """

    PREFIX = "Winamp"
    SIMPLE_COMMANDS = (
        { "target": "previous",  "label": "Previous Track", "desc": "Requests Winamp to go to the previous track" },
        { "target": "play",      "label": "Play",           "desc": "Requests Winamp to (re)start playing the current track" },
        { "target": "playpause", "label": "Pause",          "desc": "Requests Winamp to play/plause the current track" },
        { "target": "stop",      "label": "Stop",           "desc": "Requests Winamp to stop playing the current track" },
        { "target": "next",      "label": "Next Track",     "desc": "Requests Winamp to go to the next track" })

    wa = None
    wa_mutex = None

    def __init__(self):
        super().__init__()
        self.wa = WinampRemote()
        self.wa_mutex = threading.Lock()

    def __del__(self):
        if self.wa is not None:
            with self.wa_mutex:
                self.wa.uninit()

    def on_catalog(self):
        #with self.wa_mutex:
        #    if not self.wa.ping():
        #        self.set_catalog([])
        #        return

        catalog = []
        for cmd in Winamp.SIMPLE_COMMANDS:
            catalog.append(self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label="{}: {}".format(self.PREFIX, cmd['label']),
                short_desc=cmd['desc'],
                target=cmd['target'],
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.NOARGS))
        catalog.append(self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label="{}: {}".format(self.PREFIX, "Jump To Track"),
            short_desc="Requests Winamp to jump to the specified track",
            target="jumpfile",
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if (not items_chain
                or items_chain[0].category() != kp.ItemCategory.KEYWORD
                or items_chain[0].target() != "jumpfile"):
            return

        with self.wa_mutex:
            playlist = self.wa.get_tracks_titles()
        if not playlist:
            return

        suggestions = []
        desc_fmt = "Requests Winamp to jump to track #{:0" + str(len(str(len(playlist)))) + "}"
        for idx in range(len(playlist)):
            title = playlist[idx]
            if title is None:
                continue

            # if user_input is empty, just match everything we get
            include_track = 1
            if len(user_input) > 0:
                #include_track = True if user_input.lower() in title.lower() else False
                include_track = kpu.fuzzy_score(user_input, title) > 0
            if include_track:
                clone = items_chain[0].clone()
                clone.set_args(str(idx), title)
                clone.set_short_desc(desc_fmt.format(idx + 1))
                suggestions.append(clone)

        if len(suggestions) > 0:
            self.set_suggestions(suggestions)

    def on_execute(self, item, action):
        if item.target() == "jumpfile":
            with self.wa_mutex:
                self.wa.set_list_position(int(item.raw_args()), do_play=True)
        else:
            self._do_simplecmd(item.target())

    def _do_simplecmd(self, target):
        method_name = "do_" + target
        method = getattr(self.wa, method_name, None)
        if method is not None:
            with self.wa_mutex:
                method()
