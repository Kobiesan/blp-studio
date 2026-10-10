"""Native Windows file drops, without an additional runtime dependency."""
import sys

def install(root, callback):
    if sys.platform != 'win32':
        return False
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    result_type = ctypes.c_ssize_t
    proc_type = ctypes.WINFUNCTYPE(result_type, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    setter = user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.SetWindowLongW
    setter.argtypes = [wintypes.HWND, ctypes.c_int, result_type]
    setter.restype = result_type
    user.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.CallWindowProcW.restype = result_type
    shell.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell.DragQueryFileW.restype = wintypes.UINT
    shell.DragFinish.argtypes = [wintypes.HANDLE]
    root.update_idletasks()
    hwnd = user.GetAncestor(root.winfo_id(), 2)
    old = None
    @proc_type
    def handler(window, message, wparam, lparam):
        if message == 0x233:  # WM_DROPFILES
            paths = []
            try:
                count = shell.DragQueryFileW(wparam, 0xffffffff, None, 0)
                for index in range(count):
                    length = shell.DragQueryFileW(wparam, index, None, 0)
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    shell.DragQueryFileW(wparam, index, buffer, length + 1)
                    paths.append(buffer.value)
            finally:
                shell.DragFinish(wparam)
            root.after(0, lambda: callback(paths))
            return 0
        return user.CallWindowProcW(old, window, message, wparam, lparam)
    ctypes.set_last_error(0)
    old = setter(hwnd, -4, ctypes.cast(handler, ctypes.c_void_p).value)
    if not old and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    shell.DragAcceptFiles(hwnd, True)
    root._drop_handler = handler
    def remove(event):
        if event.widget is root:
            shell.DragAcceptFiles(hwnd, False)
            setter(hwnd, -4, old)
    root.bind('<Destroy>', remove, add='+')
    return True
