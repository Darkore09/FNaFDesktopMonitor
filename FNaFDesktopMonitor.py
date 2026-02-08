import sys
import os
import random
import math
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMenu, QSystemTrayIcon
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QPixmap, QIcon, QCursor, QKeySequence
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDialog, QCheckBox, QVBoxLayout
from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
import ctypes.wintypes
import pygame
import ctypes
import time

user32 = ctypes.windll.user32

MOD_CONTROL = 0x0002
VK_H = 0x48
WM_HOTKEY = 0x0312
HOTKEY_ID = 1

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

AUDIO_AVAILABLE = True

try:
    pygame.mixer.init()
except Exception as e:
    print("Audio disabled:", e)
    AUDIO_AVAILABLE = False

class SafeSound:
    def __init__(self, path=None, volume=1.0):
        self.sound = None
        if path and AUDIO_AVAILABLE:
            try:
                self.sound = pygame.mixer.Sound(path)
                self.sound.set_volume(volume)
            except Exception:
                self.sound = None

    def play(self, loops=0):
        if self.sound:
            try:
                self.sound.play(loops=loops)
            except:
                pass

    def stop(self):
        if self.sound:
            try:
                self.sound.stop()
            except:
                pass

vd = ctypes.WinDLL(resource_path("VirtualDesktopAccessor.dll"))

vd.GetDesktopCount.restype = ctypes.c_int
vd.GetCurrentDesktopNumber.restype = ctypes.c_int
vd.GoToDesktopNumber.argtypes = [ctypes.c_int]
vd.CreateDesktop.restype = ctypes.c_int
vd.RemoveDesktop.argtypes = [ctypes.c_int, ctypes.c_int]
vd.RemoveDesktop.restype = None
vd.MoveWindowToDesktopNumber.argtypes = [ctypes.c_void_p, ctypes.c_int]
vd.MoveWindowToDesktopNumber.restype = ctypes.c_int

def switch_to_desktop(num):
    vd.GoToDesktopNumber(num)

def get_current_desktop():
    return vd.GetCurrentDesktopNumber()

def ease_out_quad(t):
    return 1 - (1 - t) * (1 - t)

def cleanup_virtual_desktop():
    try:
        if overlay.monitor_desktop is not None:
            switch_to_desktop(overlay.original_desktop)
            time.sleep(0.3)

            hwnd = int(overlay.winId())
            vd.MoveWindowToDesktopNumber(hwnd, overlay.original_desktop)

            time.sleep(0.1)

            if get_current_desktop() == overlay.monitor_desktop:
                switch_to_desktop(0)
                time.sleep(0.2)

            vd.RemoveDesktop(overlay.monitor_desktop, 0)
    except Exception as e:
        print(f"Cleanup failed: {e}")

# ---------------------------
# FAKE WALLPAPER
# ---------------------------
class FakeWallpaper(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowStaysOnBottomHint
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        geo = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(geo)

        self.pix = QPixmap(resource_path("monitor_wallpaper.png"))

    def paintEvent(self, event):
        p = QPainter(self)
        geo = QApplication.primaryScreen().availableGeometry()
        p.fillRect(0, 0, geo.width(), geo.height(), QColor(0,0,0))
        p.drawPixmap(geo.width()//2 - ((geo.height()-20) * (800/600))//2,10,(geo.height()-20) * (800/600) ,geo.height()-20, self.pix)

# ---------------------------
# STATIC OVERLAY
# ---------------------------
class StaticOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

        self.overlay_img = QPixmap(resource_path("monitor_overlay.png"))

        self.noise = QPixmap()
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)

        self.noise_timer = QTimer(self)
        self.noise_timer.timeout.connect(self.generate_noise)
        
        self.anim_state = 'off' 
        self.anim_progress = 0

    def start_crt_sequence(self):
        self.anim_state = 'line'
        self.anim_progress = 0
        self.anim_timer.start(16)
        self.show()

    def stop(self):
        self.anim_state = 'off'
        self.anim_timer.stop()
        self.noise_timer.stop()
        self.hide()

    def update_animation(self):
        if self.anim_state == 'line':
            self.anim_progress += 10
            if self.anim_progress >= 200:
                self.anim_state = 'expand'
                self.anim_progress = 0
        
        elif self.anim_state == 'expand':
            self.anim_progress += 10
            if self.anim_progress >= 150:
                self.anim_state = 'startup'
                self.anim_progress = 0

        elif self.anim_state == 'startup':
            if not self.noise_timer.isActive():
                self.noise_timer.start(50)
            self.anim_progress += 5
            if self.anim_progress >= 150:
                self.anim_state = 'noise'
            
        self.update()

    def generate_noise(self):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0: return

        image = QPixmap(w, h)
        image.fill(Qt.transparent)
        painter = QPainter(image)

        for y in range(0, h, 2):
            shade = random.randint(10, 40)
            painter.fillRect(0, y, w, 1, QColor(shade, shade, shade, 120))

        for _ in range(5000):
            x = random.randint(0, w - 1)
            y = random.randint(0, h - 1)
            val = random.randint(200, 255)
            painter.fillRect(x, y, 1, 1, QColor(val, val, val, random.randint(20, 60)))
            
        painter.end()
        self.noise = image

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        center_y = h // 2
        
        if self.anim_state == 'line':
            painter.fillRect(0,0,self.width(), self.height(),QColor(0,0,0))
            t = min(self.anim_progress / 150.0, 1.0)
            eased = ease_out_quad(t)
            line_w = int(w * eased)
            line_h = 4
            x = (w - line_w) // 2
            
            painter.fillRect(x, center_y - 2, line_w, line_h, QColor(255, 255, 255))

        elif self.anim_state == 'expand':
            painter.fillRect(0,0,self.width(), self.height(),QColor(0,0,0))
            t = min(self.anim_progress / 150.0, 1.0)
            eased = ease_out_quad(t)
            box_h = int(h * eased)
            y = (h - box_h) // 2
            
            painter.fillRect(0, y, w, box_h, QColor(255, 255, 255))
        
        elif self.anim_state == 'startup':
            if not self.noise.isNull():
                painter.drawPixmap(0, 0, self.noise)
            t = min(self.anim_progress / 150.0, 1.0)
            eased = ease_out_quad(t)
            alpha_state = int(255 * (1 - eased))

            painter.fillRect(0, 0, w, h, QColor(255, 255, 255, alpha_state))

        elif self.anim_state == 'noise':
            if not self.noise.isNull():
                painter.drawPixmap(0, 0, self.noise)
        
        if not self.overlay_img.isNull():
            painter.drawPixmap(self.rect(), self.overlay_img)

    def mousePressEvent(self, event): event.ignore()
    def mouseMoveEvent(self, event): event.ignore()
    def enterEvent(self, event): event.ignore()

# ---------------------------
# MONITOR OVERLAY
# ---------------------------
class MonitorOverlay(QWidget):
    def __init__(self):
        super().__init__()

        pygame.mixer.init()

        self.original_desktop = 0
        self.monitor_desktop = None

        self.snd_up = SafeSound(resource_path("monitor_up.wav"))
        self.snd_down = SafeSound(resource_path("monitor_down.wav"))
        self.snd_ambience = SafeSound(resource_path("monitor_ambience.wav"), volume=0.4)

        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Window | 
            Qt.WindowTransparentForInput |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        geo = QApplication.primaryScreen().geometry()
        self.setGeometry(geo)

        self.label = QLabel(self)
        self.label.setGeometry(self.rect())
        self.label.setScaledContents(True)
        self.label.hide()

        self.static = StaticOverlay(self)
        self.static.setGeometry(self.rect())
        self.static.stop()

        self.up_frames = self.load_frames("monitor_up")
        self.down_frames = self.load_frames("monitor_down")

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.next_frame)

        self.current_frames = []
        self.frame_index = 0
        self.state = "down"

        self.hide()

    def load_frames(self, folder):
        frames = []
        folder_path = resource_path(folder)
        if os.path.exists(folder_path):
            for file in sorted(os.listdir(folder_path)):
                if file.endswith(".png"):
                    frames.append(QPixmap(os.path.join(folder_path, file)))
        return frames

    def play_animation(self, frames, end_state):
        self.current_frames = frames
        self.frame_index = 0
        self.state = "animating"
        self.end_state = end_state

        self.label.show()
        self.show()
        self.raise_()
        self.anim_timer.start(30)

    def next_frame(self):
        if self.frame_index == len(self.current_frames) - 2:
            if self.state == "animating" and self.end_state == "up":
                self.static.start_crt_sequence()

        if self.frame_index >= len(self.current_frames):
            self.anim_timer.stop()
            self.label.hide()
            self.state = self.end_state

            if self.state == "up":
                self.original_desktop = get_current_desktop()

                if self.monitor_desktop == None:
                    new_index = vd.GetDesktopCount()
                    vd.CreateDesktop()
                    self.monitor_desktop = new_index

                hwnd = int(self.winId())
                vd.MoveWindowToDesktopNumber(hwnd, self.monitor_desktop)
                switch_to_desktop(self.monitor_desktop)
                self.button_ref.raise_()
                self.snd_ambience.play(loops=-1)
                self.fake_wallpaper = FakeWallpaper()
                self.fake_wallpaper.show()

                hwnd_wall = int(self.fake_wallpaper.winId())
                vd.MoveWindowToDesktopNumber(hwnd_wall, self.monitor_desktop)
            else:                
                self.static.stop()
                self.snd_ambience.stop()
                self.snd_up.stop()
                self.hide()
            return

        self.label.setPixmap(self.current_frames[self.frame_index])
        self.frame_index += 1

    def open_monitor(self):
        if self.state == "down":
            self.original_desktop = get_current_desktop()
            self.play_animation(self.up_frames, "up")
            self.button_ref.raise_()
            self.snd_up.play()

    def close_monitor(self):
        if self.state == "up":
            self.snd_down.play()
            self.static.hide()
            self.snd_ambience.stop()
            self.play_animation(self.down_frames, "down")
            if hasattr(self, "fake_wallpaper"):
                self.fake_wallpaper.close()
                self.fake_wallpaper = None
            hwnd = int(self.winId())
            vd.MoveWindowToDesktopNumber(hwnd, self.original_desktop)
            switch_to_desktop(self.original_desktop)

# ---------------------------
# SETTINGS WINDOW
# ---------------------------
class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Monitor Settings")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setFixedSize(250, 120)

        geo = QApplication.primaryScreen().availableGeometry()
        x = geo.left() + (geo.width() // 2) - (self.width() // 2)
        y = geo.top() + (geo.height() // 2) - (self.height() // 2)

        self.move(x,y)

        layout = QVBoxLayout(self)

        self.open_checkbox = QCheckBox("Click to open monitor")
        self.close_checkbox = QCheckBox("Click to close monitor")

        self.open_checkbox.setChecked(False)
        self.close_checkbox.setChecked(False)

        layout.addWidget(self.open_checkbox)
        layout.addWidget(self.close_checkbox)

# ---------------------------
# HOTKEY FILTER
# ---------------------------

class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            self.callback()
            return True, 0
        return False, 0

# ---------------------------
# MONITOR BUTTON
# ---------------------------
class MonitorButton(QWidget):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(600, 60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn = QPushButton()
        self.btn.setIcon(QIcon(resource_path("monitor_button.png")))
        self.btn.setIconSize(QSize(600, 60))
        self.btn.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.btn)

        geo = QApplication.primaryScreen().availableGeometry()
        x = geo.left() + (geo.width() // 2) - (self.width() // 2)
        y = geo.top()

        self.move(x, y)

        self.btn.clicked.connect(self.button_clicked)
        self.btn.installEventFilter(self)

        self._setup_tray()

        self.hotkey_filter = HotkeyFilter(self.toggle_button_visibility)
        QCoreApplication.instance().installNativeEventFilter(self.hotkey_filter)

        user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL, VK_H)

    def check_hotkey(self):
        msg = ctypes.wintypes.MSG()
        if user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                self.toggle_button_visibility()

    def button_clicked(self):
        open_enabled = self.settings_window.open_checkbox.isChecked()
        close_enabled = self.settings_window.close_checkbox.isChecked()
        
        if self.overlay.state == "up" and close_enabled:
            self.overlay.close_monitor()
        elif self.overlay.state == "down" and open_enabled:
            self.overlay.open_monitor()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon(resource_path("icon.ico")), self)
        self.tray.setToolTip("FNAF Desktop Monitor")

        self.settings_window = SettingsWindow(self)

        menu = QMenu()
        menu.setStyleSheet("""
        QMenu::item { margin: 10px; }
        """)

        menu.addAction(QIcon(resource_path("icon.ico")), "FNAF Desktop Monitor").setEnabled(False)
        menu.addSeparator()

        self.toggle_button_action = menu.addAction("Hide Button", self.toggle_button_visibility, QKeySequence("Ctrl+H"))
        menu.addAction("Settings", self.open_settings)
        menu.addSeparator()
        menu.addAction("Exit", self.tray_close)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def open_settings(self):
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def toggle_button_visibility(self):
        if self.isHidden():
            self.show()
            self.toggle_button_action.setText("Hide Button")
        else:
            self.hide()
            self.toggle_button_action.setText("Show Button")

    def full_shutdown(self):
        import os
        import signal

        try:
            self.overlay.anim_timer.stop()
            self.overlay.static.anim_timer.stop()
            self.overlay.static.noise_timer.stop()
        except:
            pass

        try:
            if hasattr(self.overlay, "fake_wallpaper") and self.overlay.fake_wallpaper:
                self.overlay.fake_wallpaper.close()
                self.overlay.fake_wallpaper.deleteLater()
        except:
            pass

        try:
            if AUDIO_AVAILABLE:
                try:
                    pygame.mixer.quit()
                    pygame.quit()
                except:
                    pass
        except:
            pass

        try:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        except:
            pass

        try:
            QCoreApplication.instance().removeNativeEventFilter(self.hotkey_filter)
        except:
            pass

        try:
            self.tray.hide()
        except:
            pass

        QApplication.quit()
        QCoreApplication.processEvents()

        os.kill(os.getpid(), signal.SIGTERM)

    def tray_close(self):
        cleanup_virtual_desktop()
        self.full_shutdown()

    def eventFilter(self, obj, event):
        if obj == self.btn and event.type() == QEvent.Enter:
            open_enabled = self.settings_window.open_checkbox.isChecked()
            close_enabled = self.settings_window.close_checkbox.isChecked()

            if self.overlay.state == "up" and not close_enabled:
                self.overlay.close_monitor()
            elif self.overlay.state == "down" and not open_enabled:
                self.overlay.open_monitor()

        return super().eventFilter(obj, event)


# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from PySide6.QtCore import QCoreApplication

    overlay = MonitorOverlay()
    button = MonitorButton(overlay)
    overlay.button_ref = button
    button.show()
    
    sys.exit(app.exec())