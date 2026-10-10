"""Hidden-window smoke test of desktop construction and native hooks."""
import tkinter as tk
import viewer

original = tk.Tk.__init__
def hidden(self, *args, **kwargs):
    original(self, *args, **kwargs)
    self.withdraw()
def smoke(self):
    self.update()
    assert hasattr(self, 'application_icon')
    assert hasattr(self, '_drop_handler')
    self.destroy()
tk.Tk.__init__ = hidden
tk.Tk.mainloop = smoke
viewer.run_gui()
print('PASS desktop construction, app icon, native file-drop hook and teardown')
