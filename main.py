import sys
import os
import json
import time
import ctypes
import threading
import collections
import winreg
import math

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                               QLabel, QCheckBox, QPushButton, QSystemTrayIcon, 
                               QMenu, QStyle)
from PySide6.QtGui import QIcon, QAction, QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPoint

from pynput import mouse, keyboard

# Medya tuşlarını kontrol edeceğimiz obje
keyboard_controller = keyboard.Controller()

# Dinamik Ekran Boyutlarını Al (Varlığı korunsun ama Overlay kendi de hesaplıyor)
user32 = ctypes.windll.user32
SCREEN_LEFT = user32.GetSystemMetrics(76)
SCREEN_TOP = user32.GetSystemMetrics(77)
SCREEN_WIDTH = user32.GetSystemMetrics(78)
SCREEN_HEIGHT = user32.GetSystemMetrics(79)
SCREEN_RIGHT = SCREEN_LEFT + SCREEN_WIDTH - 1

# Pynput Hareket Ayarları
REQUIRED_KEY = keyboard.Key.ctrl_l
TIME_WINDOW = 0.4
EDGE_TOLERANCE = 5
MIN_DX = 250
MIN_DY = 80
MAX_Y_LIMIT = SCREEN_TOP + (SCREEN_HEIGHT * 0.6)
COOLDOWN = 1.0

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


class GestureSignals(QObject):
    add_point = Signal(int, int)
    finish_gesture = Signal(str)
    clear_path = Signal()


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # Çoklu monitör kapsama
        v_left = user32.GetSystemMetrics(76)
        v_top = user32.GetSystemMetrics(77)
        v_width = user32.GetSystemMetrics(78)
        v_height = user32.GetSystemMetrics(79)
        self.setGeometry(v_left, v_top, v_width, v_height)
        self.offset_x = v_left
        self.offset_y = v_top
        
        self.path = []
        self.last_text = ""
        self.text_alpha = 0
        self.fade_alpha = 0
        
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.fade_step)
        
    def add_point(self, x, y):
        self.fade_timer.stop()
        self.fade_alpha = 255
        self.text_alpha = 0  # Yeni çizimde eski yazıyı gizle
        
        self.path.append((x - self.offset_x, y - self.offset_y))
        self.update()
        
    def finish_gesture(self, text):
        self.last_text = text
        self.text_alpha = 255
        self.fade_timer.start(25) # Kaybolma animasyonu başlat
        
    def clear_path(self):
        self.fade_timer.start(25)
        
    def fade_step(self):
        needs_update = False
        if self.fade_alpha > 0:
            self.fade_alpha = max(0, self.fade_alpha - 10)
            needs_update = True
        else:
            if self.path:
                self.path.clear()
                
        if self.text_alpha > 0:
            self.text_alpha = max(0, self.text_alpha - 5)
            needs_update = True
            
        if needs_update:
            self.update()
        else:
            self.fade_timer.stop()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Çizgiyi Parıltılı Çiz (Neon Efekti)
        if len(self.path) >= 2 and self.fade_alpha > 0:
            # Dış Parlama (Glow)
            glow_color = QColor(29, 185, 84, int(self.fade_alpha * 0.4))
            pen_glow = QPen(glow_color)
            pen_glow.setWidth(14)
            pen_glow.setCapStyle(Qt.RoundCap)
            pen_glow.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen_glow)
            for i in range(len(self.path) - 1):
                p1 = self.path[i]
                p2 = self.path[i+1]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
            
            # Ana Çizgi
            main_color = QColor(29, 185, 84, self.fade_alpha)
            pen_main = QPen(main_color)
            pen_main.setWidth(6)
            pen_main.setCapStyle(Qt.RoundCap)
            pen_main.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen_main)
            for i in range(len(self.path) - 1):
                p1 = self.path[i]
                p2 = self.path[i+1]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
                
        # Animasyonlu Toast Yazısı Çiz
        if self.text_alpha > 0 and self.last_text:
            text_color = QColor(255, 255, 255, self.text_alpha)
            bg_color = QColor(20, 20, 20, int(self.text_alpha * 0.8))
            
            painter.setFont(QFont("Segoe UI", 36, QFont.Bold))
            
            w_width = user32.GetSystemMetrics(0)
            w_height = user32.GetSystemMetrics(1)
            
            rect = painter.fontMetrics().boundingRect(self.last_text)
            pad_x = 40
            pad_y = 20
            bg_rect = rect.adjusted(-pad_x, -pad_y, pad_x, pad_y)
            bg_rect.moveCenter(QPoint(int(w_width / 2) - self.offset_x, int(w_height / 3) - self.offset_y))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(bg_rect, 20, 20)
            
            border_pen = QPen(QColor(29, 185, 84, self.text_alpha))
            border_pen.setWidth(3)
            painter.setPen(border_pen)
            painter.drawRoundedRect(bg_rect, 20, 20)
            
            painter.setPen(text_color)
            x_pos = int(w_width / 2) - int(rect.width() / 2) - self.offset_x
            y_pos = int(w_height / 3) + int(rect.height() / 4) - self.offset_y
            painter.drawText(x_pos, y_pos, self.last_text)


class SpotifySkipperApp(QWidget):
    def __init__(self):
        super().__init__()
        
        self.settings = {
            "ctrl_lock": True,
            "run_on_startup": False
        }
        self.load_settings()
        
        # Sinyaller ve Overlay ekranı
        self.signals = GestureSignals()
        self.overlay = OverlayWindow()
        self.overlay.show()
        
        self.signals.add_point.connect(self.overlay.add_point)
        self.signals.finish_gesture.connect(self.overlay.finish_gesture)
        self.signals.clear_path.connect(self.overlay.clear_path)
        
        # Hareket takip değişkenleri
        self.history = collections.deque()
        self.last_trigger_time = 0
        self.is_key_pressed = False
        
        self.drawing_started = False
        self.draw_start_x = None
        self.draw_start_y = None
        self.draw_history = []
        
        self.pynput_thread = threading.Thread(target=self.run_listeners, daemon=True)
        self.pynput_thread.start()
        
        self.init_ui()
        self.setup_tray_icon()
        self.set_startup_registry(self.settings["run_on_startup"])

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except Exception:
                pass

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass

    def init_ui(self):
        self.setWindowTitle("Spotify Skipper V2")
        self.resize(440, 340)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)
        
        self.title_label = QLabel("🎵 Spotify Skipper V2")
        self.title_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #1DB954;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("YENİ: İstediğiniz yere çizerek medya kontrolü sağlayın!")
        self.subtitle_label.setStyleSheet("""
            background-color: #E91E63; 
            color: white; 
            font-size: 11px; 
            font-weight: bold; 
            border-radius: 4px; 
            padding: 5px;
        """)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle_label)
        
        guide_text = (
            "<div style='line-height: 1.5;'>"
            "<b>🎨 Akıllı Medya Çizimleri Nasıl Kullanılır?</b><br><br>"
            "Bilgisayarda <b>Sol CTRL</b> tuşuna basılı tutun ve farenizi kaydırın:<br>"
            "&nbsp;&nbsp;👉 <b>Sağa Çiz:</b> Sonraki Şarkı<br>"
            "&nbsp;&nbsp;👈 <b>Sola Çiz:</b> Önceki Şarkı<br>"
            "&nbsp;&nbsp;👇 <b>Aşağı Çiz:</b> Oynat / Duraklat<br>"
            "&nbsp;&nbsp;👆 <b>Yukarı Çiz:</b> Sesi Kapat / Aç"
            "</div>"
        )
        self.guide_label = QLabel(guide_text)
        self.guide_label.setStyleSheet("""
            background-color: #222222; 
            color: #eeeeee; 
            padding: 15px; 
            border-radius: 8px; 
            font-size: 13px;
        """)
        layout.addWidget(self.guide_label)
        
        layout.addSpacing(5)
        
        self.ctrl_checkbox = QCheckBox("Akıllı Çizim Modunu Aktifleştir (Önerilen)")
        self.ctrl_checkbox.setChecked(self.settings["ctrl_lock"])
        self.ctrl_checkbox.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.ctrl_checkbox.toggled.connect(self.on_ctrl_toggled)
        layout.addWidget(self.ctrl_checkbox)
        
        self.startup_checkbox = QCheckBox("Windows ile birlikte başlat")
        self.startup_checkbox.setChecked(self.settings["run_on_startup"])
        self.startup_checkbox.setStyleSheet("font-size: 13px;")
        self.startup_checkbox.toggled.connect(self.on_startup_toggled)
        layout.addWidget(self.startup_checkbox)
        
        layout.addStretch()
        
        self.hide_button = QPushButton("Arka Plana Gizle")
        self.hide_button.setCursor(Qt.PointingHandCursor)
        self.hide_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1DB954;
                color: black;
            }
        """)
        self.hide_button.clicked.connect(self.hide)
        layout.addWidget(self.hide_button)
        
        self.setLayout(layout)

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        show_action = QAction("Ayarları Göster", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Tamamen Çık", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Spotify Skipper V2",
            "Uygulama arka planda çizim hareketlerinizi dinliyor.",
            QSystemTrayIcon.Information,
            2000
        )

    def on_ctrl_toggled(self, checked):
        self.settings["ctrl_lock"] = checked
        self.save_settings()
        
    def on_startup_toggled(self, checked):
        self.settings["run_on_startup"] = checked
        self.save_settings()
        self.set_startup_registry(checked)

    def set_startup_registry(self, enabled):
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "SpotifySkipper"
        
        try:
            registry_key = winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS)
            python_exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
                
            script_path = os.path.abspath(__file__)
            command = f'"{python_exe}" "{script_path}"'
            
            if enabled:
                winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(registry_key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(registry_key)
        except Exception:
            pass

    def run_listeners(self):
        kbd_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        kbd_listener.start()
        
        with mouse.Listener(on_move=self.on_move) as listener:
            listener.join()

    def on_press(self, key):
        if key == REQUIRED_KEY:
            self.is_key_pressed = True
            self.drawing_started = False
            self.draw_start_x = None
            self.draw_start_y = None
            self.draw_history.clear()

    def on_release(self, key):
        if key == REQUIRED_KEY:
            self.is_key_pressed = False
            if self.drawing_started:
                self.analyze_new_gesture()
            else:
                self.signals.clear_path.emit()
                
            self.drawing_started = False
            self.draw_history.clear()

    def analyze_new_gesture(self):
        if len(self.draw_history) < 2:
            self.signals.clear_path.emit()
            return
            
        start_x, start_y = self.draw_history[0]
        end_x, end_y = self.draw_history[-1]
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        dist = math.hypot(dx, dy)
        if dist < 80: # Minimal anlamlı çizim mesafesi
            self.signals.clear_path.emit()
            return
            
        angle = math.degrees(math.atan2(dy, dx))
        
        if -45 < angle <= 45:
            keyboard_controller.press(keyboard.Key.media_next)
            keyboard_controller.release(keyboard.Key.media_next)
            self.signals.finish_gesture.emit("Sonraki Şarkı 👉")
        elif angle > 135 or angle <= -135:
            keyboard_controller.press(keyboard.Key.media_previous)
            keyboard_controller.release(keyboard.Key.media_previous)
            self.signals.finish_gesture.emit("👈 Önceki Şarkı")
        elif 45 < angle <= 135:
            keyboard_controller.press(keyboard.Key.media_play_pause)
            keyboard_controller.release(keyboard.Key.media_play_pause)
            self.signals.finish_gesture.emit("⏯ Oynat / Duraklat")
        elif -135 < angle <= -45:
            keyboard_controller.press(keyboard.Key.media_volume_mute)
            keyboard_controller.release(keyboard.Key.media_volume_mute)
            self.signals.finish_gesture.emit("🔇 Sesi Sustur/Aç")

    def on_move(self, x, y):
        # YENİ MOD: Ekranda Çizim Yapma
        if self.settings["ctrl_lock"]:
            if self.is_key_pressed:
                if not self.drawing_started:
                    if self.draw_start_x is None:
                        self.draw_start_x = x
                        self.draw_start_y = y
                    dist = math.hypot(x - self.draw_start_x, y - self.draw_start_y)
                    if dist > 20: # Spam engelleme için asgari çekme payı
                        self.drawing_started = True
                        self.draw_history.append((self.draw_start_x, self.draw_start_y))
                        self.signals.add_point.emit(self.draw_start_x, self.draw_start_y)
                
                if self.drawing_started:
                    self.draw_history.append((x, y))
                    self.signals.add_point.emit(x, y)
            return

        # ESKİ MOD: Köşelere kaydırma takibi (Ctrl kapalıysa)
        current_time = time.time()
        self.history.append((current_time, x, y))
        
        while self.history and current_time - self.history[0][0] > TIME_WINDOW:
            self.history.popleft()
            
        if current_time - self.last_trigger_time > COOLDOWN:
            at_left_edge = (x <= SCREEN_LEFT + EDGE_TOLERANCE)
            if not at_left_edge and (x <= EDGE_TOLERANCE): 
                at_left_edge = True
            at_right_edge = (x >= SCREEN_RIGHT - EDGE_TOLERANCE)
            
            if (at_left_edge or at_right_edge) and y < MAX_Y_LIMIT and len(self.history) >= 2:
                start_t, start_x, start_y = self.history[0]
                dx = x - start_x
                dy = y - start_y
                
                if dy > MIN_DY:  
                    if at_left_edge and dx < -MIN_DX:
                        keyboard_controller.press(keyboard.Key.media_previous)
                        keyboard_controller.release(keyboard.Key.media_previous)
                        self.last_trigger_time = current_time
                        self.history.clear()
                    elif at_right_edge and dx > MIN_DX:
                        keyboard_controller.press(keyboard.Key.media_next)
                        keyboard_controller.release(keyboard.Key.media_next)
                        self.last_trigger_time = current_time
                        self.history.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Modern koyu tema
    from PySide6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(40, 40, 40))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(40, 40, 40))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(29, 185, 84))
    palette.setColor(QPalette.Highlight, QColor(29, 185, 84))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    window = SpotifySkipperApp()
    window.show()
    
    sys.exit(app.exec())
