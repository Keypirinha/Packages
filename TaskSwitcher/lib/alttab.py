# Keypirinha: a fast launcher for Windows (keypirinha.com)

import ctypes

class AltTab:
    """
    A class to ease the finding of Alt+Tab eligible windows and the interaction
    between Python and the Win32 API via ctypes.
    """

    @classmethod
    def list_alttab_windows(cls):
        """
        Return the list of the windows handles that are currently guessed to be
        eligible to the Alt+Tab panel.
        Raises a OSError exception on error.
        """
        # LPARAM is defined as LONG_PTR (signed type)
        if ctypes.sizeof(ctypes.c_long) == ctypes.sizeof(ctypes.c_void_p):
            LPARAM = ctypes.c_long
        elif ctypes.sizeof(ctypes.c_longlong) == ctypes.sizeof(ctypes.c_void_p):
            LPARAM = ctypes.c_longlong
        EnumWindowsProc = ctypes.WINFUNCTYPE(
                                ctypes.c_bool, ctypes.c_void_p, LPARAM)

        def _enum_proc(hwnd, lparam):
            try:
                if cls.is_alttab_window(hwnd):
                    handles.append(hwnd)
            except OSError:
                pass
            return True

        handles = []
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(_enum_proc), 0)
        return handles

    @classmethod
    def is_alttab_window(cls, hwnd):
        """
        Guess if the given window handle is eligible to the Alt+Tab panel.
        Raises a OSError exception on error.
        """
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible

        # * Initial windows filtering based on Raymond Chen's blog post:
        #   "Which windows appear in the Alt+Tab list?"
        #     https://blogs.msdn.microsoft.com/oldnewthing/20071008-00/?p=24863/
        # * Also see MSDN documentation ""The Taskbar" (especially the "Managing
        #   Taskbar Buttons"):
        #     https://msdn.microsoft.com/en-us/library/bb776822(VS.85).aspx
        # * "Getting a list of windows like those displayed in the alt-tab list,
        #   taskbar buttons and task manager" post on MSDN Forum:
        #     https://social.msdn.microsoft.com/Forums/windowsdesktop/en-US/5b337500-32dc-442d-8f77-62cad15ef46a
        if not IsWindowVisible(hwnd):
            return False
        if ctypes.windll.user32.GetWindowTextLengthW(hwnd) <= 0:
            return False
        exstyle = cls.get_window_long(hwnd, -16) # GWL_EXSTYLE
        if (exstyle & WS_EX_APPWINDOW) == WS_EX_APPWINDOW:
            return True
        if (exstyle & WS_EX_TOOLWINDOW) == WS_EX_TOOLWINDOW:
            return False
        if (exstyle & WS_EX_NOACTIVATE) == WS_EX_NOACTIVATE:
            return False
        owner_hwnd = ctypes.windll.user32.GetWindow(hwnd, 4) # GW_OWNER
        if owner_hwnd and IsWindowVisible(owner_hwnd):
            return False

        # skip root Excel window
        # https://mail.python.org/pipermail/python-win32/2010-January/010012.html
        if ctypes.windll.user32.GetPropW(hwnd, "ITaskList_Deleted"):
            return False

        # avoids double entries for store apps on windows 10
        # trick from Switcheroo (http://www.switcheroo.io/)
        class_name = cls.get_window_class_name(hwnd)
        if class_name == "Windows.UI.Core.CoreWindow":
            return False

        # skip the "Program Manager" window ("explorer" process, tested on 8.1)
        if class_name == "Progman":
            return False

        return True

    @staticmethod
    def switch_to_window(hwnd):
        """Wrapper over the SwitchToThisWindow() Win32 function"""
        ctypes.windll.user32.SwitchToThisWindow(hwnd, True)

    @staticmethod
    def get_window_text(hwnd):
        """
        Wrapper over the GetWindowTextW() Win32 function
        Raises a OSError exception on error.
        """
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.kernel32.SetLastError(0)
        res = ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        if not res and ctypes.GetLastError() != 0:
            raise ctypes.WinError()
        return buff.value

    @staticmethod
    def get_window_long(hwnd, index):
        """
        Wrapper over the GetWindowLongW() Win32 function
        Raises a OSError exception on error.
        """
        ctypes.windll.kernel32.SetLastError(0)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, index)
        if ctypes.GetLastError() != 0:
            raise ctypes.WinError()
        return style

    @staticmethod
    def get_window_class_name(hwnd):
        """
        Wrapper over the GetClassNameW() Win32 function
        Raises a OSError exception on error.
        """
        max_length = 256 # see WNDCLASS documentation
        buff = ctypes.create_unicode_buffer(max_length + 1)
        if not ctypes.windll.user32.GetClassNameW(hwnd, buff, max_length + 1):
            raise ctypes.WinError()
        return buff.value

    @staticmethod
    def get_window_thread_process_id(hwnd):
        """
        Wrapper over the GetWindowThreadProcessId() win32 function.
        Get the IDs of the parent thread and process of the given window handle.
        Returns a tuple: (thread_id, proc_id)
        Raises a OSError exception on error.
        """
        proc_id = ctypes.c_ulong()
        thread_id = ctypes.windll.user32.GetWindowThreadProcessId(
                        hwnd, ctypes.byref(proc_id))
        if not thread_id or not proc_id.value:
            raise ctypes.WinError()
        return (thread_id, proc_id.value)

    @staticmethod
    def get_process_image_path(proc_id):
        """
        Return the full path of the PE image of the given process ID.
        Raises a OSError exception on error.
        """
        # get process handle
        # PROCESS_QUERY_INFORMATION = 0x400
        hproc = ctypes.windll.kernel32.OpenProcess(0x400, False, proc_id)
        if not hproc:
            raise ctypes.WinError()

        # get image path
        # MAX_PATH is 260 but we're using the Unicode variant of the API
        max_length = 1024
        length = ctypes.c_ulong(max_length)
        buff = ctypes.create_unicode_buffer(max_length)
        ctypes.windll.kernel32.SetLastError(0)
        res = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                                        hproc, 0, buff, ctypes.byref(length))
        error = ctypes.GetLastError()
        ctypes.windll.kernel32.CloseHandle(hproc)
        ctypes.windll.kernel32.SetLastError(error)
        if not res:
            raise ctypes.WinError()
        return buff.value
