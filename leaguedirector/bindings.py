import threading
import functools
from ctypes import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *


class KeyboardHook(QThread):
    """
    This class is responsible for creating a global keyboard hook and
    forwarding key events to QT when the game process has focus.
    """

    def __init__(self, window):
        QThread.__init__(self)
        self.tid = None
        self.pid = None
        self.running = True
        self.window = window
        self.window.installEventFilter(self)
        QCoreApplication.instance().aboutToQuit.connect(self.stop)

    def stop(self):
        self.window.removeEventFilter(self)
        self.running = False
        windll.user32.PostThreadMessageA(self.tid, 18, 0, 0)

    def eventFilter(self, object, event):
        if event.type() == QEvent.ActivationChange:
            self.window.setFocus(Qt.OtherFocusReason)
            QApplication.setActiveWindow(self.window)
        return False

    def setPid(self, pid):
        self.pid = pid

    def run(self):
        self.tid = threading.get_ident()
        from ctypes.wintypes import DWORD, WPARAM, LPARAM, MSG

        class KBDLLHOOKSTRUCT(Structure):
            _fields_ = [
                ("vk_code", DWORD),
                ("scan_code", DWORD),
                ("flags", DWORD),
                ("time", c_int),
                ("dwExtraInfo", POINTER(DWORD))
            ]

        def callback(nCode, wParam, lParam):
            pid = c_ulong()
            windll.user32.GetWindowThreadProcessId(windll.user32.GetForegroundWindow(), byref(pid))
            if pid.value == self.pid:
                windll.user32.SendMessageA(self.window.winId(), wParam, lParam.contents.vk_code, 0)
            return windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
 
        function = CFUNCTYPE(c_int, WPARAM, LPARAM, POINTER(KBDLLHOOKSTRUCT))(callback)
        hook = windll.user32.SetWindowsHookExW(13, function, windll.kernel32.GetModuleHandleW(None), 0)

        msg = POINTER(MSG)()
        while self.running:
            try:
                windll.user32.GetMessageW(msg, 0, 0, 0)
                windll.user32.TranslateMessage(msg)
                windll.user32.DispatchMessageA(msg)
            except: pass

        windll.user32.UnhookWindowsHookEx(hook)


class Bindings(QObject):
    triggered = Signal(str)

    def __init__(self, window, bindings, options):
        QObject.__init__(self)
        self.labels = {name : label for name, label, _ in options}
        self.shortcuts = {}
        self.defaults = {}
        for name, _, default in options:
            if name in bindings:
                sequence = QKeySequence(bindings[name])
            else:
                sequence = QKeySequence(default)
            shortcut = QShortcut(sequence, window)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.setAutoRepeat(True)
            shortcut.activated.connect(functools.partial(self.activated, name))
            shortcut.activatedAmbiguously.connect(functools.partial(self.activated, name))
            self.shortcuts[name] = shortcut
            self.defaults[name] = default
        self.hook = KeyboardHook(window)
        self.hook.start()

    def activated(self, name):
        sequence = self.shortcuts[name].key()
        for name, shortcut in self.shortcuts.items():
            if shortcut.key() == sequence:
                self.triggered.emit(name)

    def getBindings(self):
        return {name : shortcut.key().toString() for name, shortcut in self.shortcuts.items()}

    def getOptions(self):
        return [(name, label, self.shortcuts[name].key().toString()) for name, label, default in self.options]

    def setBinding(self, name, sequence):
        self.shortcuts[name].setKey(QKeySequence(sequence))

    def getLabel(self, name):
        return self.labels[name]

    def setGamePid(self, pid):
        self.hook.setPid(pid)
