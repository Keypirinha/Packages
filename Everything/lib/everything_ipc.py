# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha_wintypes as kpwt
import ctypes as ct
import os.path
import time

class EVERYTHING_IPC_QUERY_HEADER(ct.Structure):
    _pack_ = 1 # must be defined BEFORE _fields_
    _fields_ = [("reply_hwnd", kpwt.DWORD),
                ("reply_copydata_message", kpwt.DWORD),
                ("search_flags", kpwt.DWORD),
                ("offset", kpwt.DWORD),
                ("max_results", kpwt.DWORD)]
                # followed by the search string itself (a null terminated WSTR)

class EVERYTHING_IPC_ITEMW(ct.Structure):
    _pack_ = 1 # must be defined BEFORE _fields_
    _fields_ = [("flags", kpwt.DWORD),
                ("filename_offset", kpwt.DWORD),
                ("path_offset", kpwt.DWORD)]

class EVERYTHING_IPC_LIST_HEADER(ct.Structure):
    _pack_ = 1 # must be defined BEFORE _fields_
    _fields_ = [("totfolders", kpwt.DWORD), # the total number of folders found
                ("totfiles", kpwt.DWORD),   # the total number of files found
                ("totitems", kpwt.DWORD),   # totfolders + totfiles
                ("numfolders", kpwt.DWORD), # the number of folders available
                ("numfiles", kpwt.DWORD),   # the number of files available
                ("numitems", kpwt.DWORD),   # the number of items available
                ("offset", kpwt.DWORD)]     # index offset of the first result in the item list
                # followed by numitems * EVERYTHING_IPC_ITEMW

EVERYTHING_OK = 0
EVERYTHING_ERROR_MEMORY = 1
EVERYTHING_ERROR_IPC = 2
EVERYTHING_ERROR_REGISTERCLASSEX = 3
EVERYTHING_ERROR_CREATEWINDOW = 4
EVERYTHING_ERROR_CREATETHREAD = 5
EVERYTHING_ERROR_INVALIDINDEX = 6
EVERYTHING_ERROR_INVALIDCALL = 7

EVERYTHING_WM_IPC = kpwt.WM_USER

EVERYTHING_IPC_GET_MAJOR_VERSION = 0
EVERYTHING_IPC_GET_MINOR_VERSION = 1
EVERYTHING_IPC_GET_REVISION = 2
EVERYTHING_IPC_GET_BUILD_NUMBER = 3
EVERYTHING_IPC_REBUILD_DB = 405
EVERYTHING_IPC_COPYDATAQUERYW = 2

EVERYTHING_IPC_WNDCLASS = "EVERYTHING_TASKBAR_NOTIFICATION"

EVERYTHING_IPC_MATCHCASE = 0x00000001
EVERYTHING_IPC_MATCHWHOLEWORD = 0x00000002
EVERYTHING_IPC_MATCHPATH = 0x00000004
EVERYTHING_IPC_REGEX = 0x00000008
EVERYTHING_IPC_MATCHACCENTS = 0x00000010 # match diacritic marks

EVERYTHING_IPC_ALLRESULTS = 0xffffffff

EVERYTHING_IPC_FOLDER = 0x00000001  # The item is a folder. (its a file if not set)
EVERYTHING_IPC_DRIVE = 0x00000002   # The folder is a drive. Path will be an empty string



CLIENT_WNDCLASS_NAME = "PyEverythingIPCClient"

class Error(Exception): pass
class EverythingNotFound(Error): pass
class IPCError(Error): pass

class List():
    def __init__(self, result_buffer=None):
        self.data = result_buffer
        if self.data is None:
            self.list = None
        else:
            self.list = ct.cast(
                            ct.byref(self.data),
                            ct.POINTER(EVERYTHING_IPC_LIST_HEADER)).contents

    def __len__(self):
        return self.list.numitems if self.list else 0

    def __getattr__(self, attr):
        return getattr(self.list, attr)

    def __iter__(self):
        if not self.list:
            return
            yield # empty generator
        index = 0
        offset = ct.sizeof(EVERYTHING_IPC_LIST_HEADER)
        while index < self.list.numitems:
            if offset + ct.sizeof(EVERYTHING_IPC_ITEMW) > len(self.data):
                break
            item = ct.cast(
                        ct.byref(self.data, offset),
                        ct.POINTER(EVERYTHING_IPC_ITEMW)).contents
            if item.flags & EVERYTHING_IPC_DRIVE:
                item_full_path = self._safe_wstring_at(self.data, item.filename_offset)
                if item_full_path is None:
                    break
                if len(item_full_path) == 2:
                    item_full_path += os.sep
                is_file = False
            else:
                item_dir = self._safe_wstring_at(self.data, item.path_offset)
                if item_dir is None:
                    break
                if len(item_dir) == 2 and item_dir[1] == ":":
                    item_dir += os.sep
                item_fname = self._safe_wstring_at(self.data, item.filename_offset)
                if item_fname is None:
                    break
                item_full_path = os.path.join(item_dir, item_fname)
                is_file = (item.flags & EVERYTHING_IPC_FOLDER) == 0
            index += 1
            offset += ct.sizeof(EVERYTHING_IPC_ITEMW)
            yield item_full_path, is_file

    def _safe_wstring_at(self, buff, offset):
        idx = 0
        length = 0
        while offset + idx + 1 < len(buff):
            if buff[offset+idx] == b'\x00' and buff[offset+idx+1] == b'\x00':
                return ct.wstring_at(ct.addressof(buff) + offset, length)
            idx += 2
            length += 1
        return None # terminating null char not found

def _wndproc(hwnd, msg, wparam, lparam):
    if msg == kpwt.WM_COPYDATA:
        expected_query_id = kpwt.user32.GetWindowLongPtrW(hwnd, kpwt.GWLP_USERDATA)
        cds = ct.cast(lparam, ct.POINTER(kpwt.COPYDATASTRUCT)).contents
        if cds.dwData == expected_query_id:
            res_buffer = ct.create_string_buffer(cds.cbData)
            ct.memmove(res_buffer, cds.lpData, cds.cbData)
            globals()['_result_buffers'][expected_query_id] = res_buffer
            kpwt.user32.PostQuitMessage(0)
            return True
    return kpwt.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

_pwndproc = kpwt.WNDPROCTYPE(_wndproc)
_next_query_id = 1
_result_buffers = {} # {query_id: buffer}

class Client():
    def get_version(self):
        everything_hwnd = self._find_everything()
        major = self._send_msg(everything_hwnd, EVERYTHING_WM_IPC, EVERYTHING_IPC_GET_MAJOR_VERSION, 0)
        minor = self._send_msg(everything_hwnd, EVERYTHING_WM_IPC, EVERYTHING_IPC_GET_MINOR_VERSION, 0)
        revision = self._send_msg(everything_hwnd, EVERYTHING_WM_IPC, EVERYTHING_IPC_GET_REVISION, 0)
        build = self._send_msg(everything_hwnd, EVERYTHING_WM_IPC, EVERYTHING_IPC_GET_BUILD_NUMBER, 0)
        return (major, minor, revision, build)

    def get_version_str(self):
        return ".".join([str(n) for n in self.get_version()])

    def show(self):
        # This will fail with an ERROR_ACCESS_DENIED (5) if Everything runs with
        # elevated privileges and we don't because of Windows UIPI...
        self._send_msg(self._find_everything(), kpwt.WM_COMMAND, 40007, 0)

    def rebuild_db(self): # requires 1.4+
        self._send_msg(self._find_everything(), EVERYTHING_WM_IPC, EVERYTHING_IPC_REBUILD_DB, 0)

    def query(self, search_terms,
            result_offset=0, max_results=EVERYTHING_IPC_ALLRESULTS,
            is_regex=False, match_path=False, match_case=False,
            match_whole_word=False, match_accents=False,
            should_terminate_cb=None):
        everything_hwnd = self._find_everything()

        # query id
        current_query_id = globals()['_next_query_id']
        globals()['_next_query_id'] += 1

        # create our ipc client window
        # Everything requires ONE window per query
        hwnd = self._create_window(current_query_id)

        # prepare query
        query_payload = ct.create_string_buffer(
                            ct.sizeof(EVERYTHING_IPC_QUERY_HEADER) +
                            (len(search_terms) + 1) * ct.sizeof(ct.c_wchar))
        kpwt.ZeroMemory(query_payload)
        query_head = ct.cast(
                        ct.byref(query_payload),
                        ct.POINTER(EVERYTHING_IPC_QUERY_HEADER)).contents
        query_head.reply_hwnd = hwnd
        query_head.reply_copydata_message = current_query_id
        query_head.offset = result_offset
        query_head.max_results = max_results
        query_head.search_flags = 0
        if match_case:
            query_head.search_flags |= EVERYTHING_IPC_MATCHCASE
        if match_whole_word:
            query_head.search_flags |= EVERYTHING_IPC_MATCHWHOLEWORD
        if match_path:
            query_head.search_flags |= EVERYTHING_IPC_MATCHPATH
        if is_regex:
            query_head.search_flags |= EVERYTHING_IPC_REGEX
        if match_accents:
            query_head.search_flags |= EVERYTHING_IPC_MATCHACCENTS
        (ct.c_wchar * len(search_terms)).from_buffer(query_payload,
            ct.sizeof(EVERYTHING_IPC_QUERY_HEADER))[:] = search_terms

        # send query
        cds = kpwt.COPYDATASTRUCT()
        cds.dwData = EVERYTHING_IPC_COPYDATAQUERYW
        cds.cbData = len(query_payload)
        cds.lpData = ct.cast(ct.byref(query_payload), kpwt.PVOID)
        kpwt.kernel32.SetLastError(0)
        if not kpwt.user32.SendMessageW(everything_hwnd, kpwt.WM_COPYDATA, hwnd, ct.addressof(cds)):
            error = kpwt.kernel32.GetLastError()
            kpwt.user32.DestroyWindow(hwnd)
            if not error:
                raise IPCError("IPC query to Everything not supported")
            else:
                raise IPCError("IPC query to Everything failed (winerror #{})".format(error))

        # wait for an answer
        res = self._flush_winmsg()
        must_terminate = False
        if res:
            max_query_seconds = 30 # seconds
            wait_milli = 75 if should_terminate_cb else int(max_query_seconds * 1000)
            start_time = time.perf_counter()
            while True:
                wait_res = kpwt.user32.MsgWaitForMultipleObjects(
                                            0, None, False, wait_milli,
                                            0x04FF | 0x0100)
                if wait_res == kpwt.WAIT_TIMEOUT:
                    if not should_terminate_cb or should_terminate_cb():
                        must_terminate = True
                        break
                elif not self._flush_winmsg():
                    break
                if time.perf_counter() - start_time >= max_query_seconds:
                    break

        # destroy window
        kpwt.user32.DestroyWindow(hwnd)
        hwnd = None

        # encapsulate the resulting buffer, if we've got one, so the caller can
        # iterate over Everything's list in an easy and optimized way
        res_buffers_ref = globals()['_result_buffers']
        if current_query_id in res_buffers_ref:
            # do not feed the caller if this call has been aborted
            if must_terminate:
                del res_buffers_ref[current_query_id]
            else:
                res_list = List(res_buffers_ref[current_query_id])
                del res_buffers_ref[current_query_id]
                return res_list
        return List()

    def _find_everything(self):
        everything_hwnd = kpwt.user32.FindWindowW(EVERYTHING_IPC_WNDCLASS, None)
        if not everything_hwnd:
            raise EverythingNotFound
        return everything_hwnd

    def _send_msg(self, hwnd, msg, wparam=0, lparam=0):
        kpwt.kernel32.SetLastError(0)
        res = kpwt.user32.SendMessageW(hwnd, msg, wparam, lparam)
        err = kpwt.kernel32.GetLastError()
        if err:
            raise ct.WinError(err)
        return res

    def _create_window(self, current_query_id=None):
        hinst = kpwt.kernel32.GetModuleHandleW(None)
        wcex = kpwt.WNDCLASSEXW()

        # create class if needed
        wcex.cbSize = ct.sizeof(kpwt.WNDCLASSEXW)
        res = kpwt.user32.GetClassInfoExW(
                hinst, kpwt.LPCWSTR(CLIENT_WNDCLASS_NAME), ct.byref(wcex))
        if not res:
            kpwt.ZeroMemory(wcex)
            wcex.cbSize = ct.sizeof(kpwt.WNDCLASSEXW)
            wcex.lpfnWndProc = globals()['_pwndproc']
            wcex.hInstance = hinst
            wcex.lpszClassName = CLIENT_WNDCLASS_NAME
            res = kpwt.user32.RegisterClassExW(ct.byref(wcex))
            if not res:
                raise ct.WinError()

        # create window
        hwnd = kpwt.user32.CreateWindowExW(
                            0, CLIENT_WNDCLASS_NAME, "", 0, 0, 0, 0, 0, None,
                            None, hinst, None)
        if not hwnd:
            raise ct.WinError()

        # assign the current query id if needed
        if current_query_id is not None:
            kpwt.user32.SetWindowLongPtrW(hwnd, kpwt.GWLP_USERDATA, current_query_id)

        # allow the WM_COPYDATA message to be received
        try:
            kpwt.user32.ChangeWindowMessageFilterEx(hwnd, kpwt.WM_COPYDATA, 1, None)
        except AttributeError:
            pass

        return hwnd

    def _flush_winmsg(self):
        msg = kpwt.MSG()
        while kpwt.user32.PeekMessageW(ct.byref(msg), None, 0, 0, 1):
            if msg.message == kpwt.WM_QUIT:
                return False
            kpwt.user32.TranslateMessage(ct.byref(msg))
            kpwt.user32.DispatchMessageW(ct.byref(msg))
        return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise Exception("arg missing: search term")
    search_terms = sys.argv[1]

    start = time.perf_counter()

    client = Client()
    res_list = client.query(search_terms)
    end1 = time.perf_counter()

    for item_full_path, item_is_file in res_list:
        #print("[{}] {}".format(item_is_file, item_full_path))
        pass

    print("\nEverything version", client.get_version_str())
    end2 = time.perf_counter()
    if res_list:
        print("List Info:\n  search:", search_terms)
        for name, tp in res_list.list._fields_:
            print("  {}: {}".format(name, getattr(res_list, name)))
    print("Query done in {:.4f}s. Results in {:.4f}s.".format(end1 - start, end2 - end1))
