import sys
import os
import json
import time
import ctypes
import threading
import collections
import winreg
import math

# Windows DPI Awareness (Fare offset'ini düzeltmek için kritik)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QCheckBox, QPushButton, QSystemTrayIcon, 
                               QMenu, QStyle, QComboBox, QDialog, QColorDialog,
                               QMessageBox)
from PySide6.QtGui import QIcon, QAction, QPainter, QPen, QColor, QFont, QCursor, QPalette
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPoint

from pynput import mouse, keyboard

keyboard_controller = keyboard.Controller()

user32 = ctypes.windll.user32
SCREEN_LEFT = user32.GetSystemMetrics(76)
SCREEN_TOP = user32.GetSystemMetrics(77)
SCREEN_WIDTH = user32.GetSystemMetrics(78)
SCREEN_HEIGHT = user32.GetSystemMetrics(79)
SCREEN_RIGHT = SCREEN_LEFT + SCREEN_WIDTH - 1

REQUIRED_KEY = keyboard.Key.ctrl_l
TIME_WINDOW = 0.4
EDGE_TOLERANCE = 5
MIN_DX = 250
MIN_DY = 80
MAX_Y_LIMIT = SCREEN_TOP + (SCREEN_HEIGHT * 0.6)
COOLDOWN = 1.0

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


class GestureSignals(QObject):
    add_point = Signal()
    finish_gesture = Signal(str)
    clear_path = Signal()


class CustomThemeModal(QDialog):
    def __init__(self, parent=None, current_main="#1DB954", current_glow="#1DB954"):
        super().__init__(parent)
        self.setWindowTitle("🎨 Özel Tema Profiliniz")
        self.resize(320, 200)
        self.main_color = QColor(current_main)
        self.glow_color = QColor(current_glow)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        info = QLabel("Kendi neon renklerinizi seçin:")
        info.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(info)
        
        self.main_btn = QPushButton("Ana Çizgi Rengini Seç")
        self.main_btn.setCursor(Qt.PointingHandCursor)
        self.main_btn.setStyleSheet(f"background-color: {self.main_color.name()}; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.main_btn.clicked.connect(self.pick_main)
        layout.addWidget(self.main_btn)
        
        self.glow_btn = QPushButton("Dış Parlama (Neon) Rengini Seç")
        self.glow_btn.setCursor(Qt.PointingHandCursor)
        self.glow_btn.setStyleSheet(f"background-color: {self.glow_color.name()}; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.glow_btn.clicked.connect(self.pick_glow)
        layout.addWidget(self.glow_btn)
        
        save_btn = QPushButton("Kaydet ve Kapat")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("background-color: #333333; color: white; padding: 10px; border-radius: 5px;")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
        
    def pick_main(self):
        color = QColorDialog.getColor(self.main_color, self, "Ana Çizgi Rengi")
        if color.isValid():
            self.main_color = color
            self.main_btn.setStyleSheet(f"background-color: {color.name()}; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
            
    def pick_glow(self):
        color = QColorDialog.getColor(self.glow_color, self, "Neon Rengi Seç")
        if color.isValid():
            self.glow_color = color
            self.glow_btn.setStyleSheet(f"background-color: {color.name()}; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")


class OverlayWindow(QWidget):
    def __init__(self, settings_ref):
        super().__init__()
        self.app_settings = settings_ref
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        v_left = user32.GetSystemMetrics(76)
        v_top = user32.GetSystemMetrics(77)
        v_width = user32.GetSystemMetrics(78)
        v_height = user32.GetSystemMetrics(79)
        self.setGeometry(v_left, v_top, v_width, v_height)
        
        self.path = []
        self.last_text = ""
        self.text_alpha = 0
        self.fade_alpha = 0
        
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.fade_step)
        
    def get_colors(self):
        theme = self.app_settings.get("theme", "spotify")
        if theme == "cyberpunk":
            return QColor(255, 105, 180), QColor(255, 0, 255)
        elif theme == "sith":
            return QColor(255, 100, 100), QColor(255, 0, 0)
        elif theme == "glacier":
            return QColor(150, 255, 255), QColor(0, 150, 255)
        elif theme == "custom":
            return QColor(self.app_settings.get("custom_main", "#ffffff")), QColor(self.app_settings.get("custom_glow", "#1DB954"))
        
        # Default Spotify
        return QColor(29, 185, 84), QColor(29, 185, 84)
        
    def add_point(self):
        # QCursor ile fare koordinatını %100 hassasiyetle (Offset olmadan) çekiyoruz
        cursor_pos = QCursor.pos()
        local_pt = self.mapFromGlobal(cursor_pos)
        
        self.fade_timer.stop()
        self.fade_alpha = 255
        self.text_alpha = 0
        
        self.path.append((local_pt.x(), local_pt.y()))
        self.update()
        
    def finish_gesture(self, text):
        self.last_text = text
        self.text_alpha = 255
        self.fade_timer.start(20)
        
    def clear_path(self):
        self.fade_timer.start(20)
        
    def fade_step(self):
        needs_update = False
        if self.fade_alpha > 0:
            self.fade_alpha = max(0, self.fade_alpha - 12)
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
        
        if len(self.path) >= 2 and self.fade_alpha > 0:
            main_c, glow_c = self.get_colors()
            
            glow_color = QColor(glow_c.red(), glow_c.green(), glow_c.blue(), int(self.fade_alpha * 0.45))
            pen_glow = QPen(glow_color)
            pen_glow.setWidth(14)
            pen_glow.setCapStyle(Qt.RoundCap)
            pen_glow.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen_glow)
            for i in range(len(self.path) - 1):
                p1 = self.path[i]
                p2 = self.path[i+1]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
            
            main_color = QColor(main_c.red(), main_c.green(), main_c.blue(), self.fade_alpha)
            pen_main = QPen(main_color)
            pen_main.setWidth(6)
            pen_main.setCapStyle(Qt.RoundCap)
            pen_main.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen_main)
            for i in range(len(self.path) - 1):
                p1 = self.path[i]
                p2 = self.path[i+1]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
                
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
            
            # Dinamik konumlama (Ortaya yakın)
            local_center_x = int(w_width / 2) - self.geometry().x()
            local_center_y = int(w_height / 3) - self.geometry().y()
            bg_rect.moveCenter(QPoint(local_center_x, local_center_y))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(bg_rect, 20, 20)
            
            main_c, glow_c = self.get_colors()
            border_pen = QPen(QColor(glow_c.red(), glow_c.green(), glow_c.blue(), self.text_alpha))
            border_pen.setWidth(3)
            painter.setPen(border_pen)
            painter.drawRoundedRect(bg_rect, 20, 20)
            
            painter.setPen(text_color)
            x_pos = local_center_x - int(rect.width() / 2)
            y_pos = local_center_y + int(rect.height() / 4)
            painter.drawText(x_pos, y_pos, self.last_text)


class SpotifySkipperApp(QWidget):
    def __init__(self):
        super().__init__()
        
        self.settings = {
            "ctrl_lock": True,
            "run_on_startup": False,
            "theme": "spotify",
            "custom_main": "#ffffff",
            "custom_glow": "#1DB954"
        }
        self.load_settings()
        
        self.signals = GestureSignals()
        self.overlay = OverlayWindow(self.settings)
        self.overlay.show()
        
        self.signals.add_point.connect(self.overlay.add_point)
        self.signals.finish_gesture.connect(self.overlay.finish_gesture)
        self.signals.clear_path.connect(self.overlay.clear_path)
        
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

    def save_settings(self, silent=True):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            if not silent:
                QMessageBox.information(self, "Başarılı", "✅ Ayarlarınız tümüyle kaydedildi!")
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Hata", f"Kaydedilirken bir sorun oluştu: {e}")

    def init_ui(self):
        self.setWindowTitle("Spotify Skipper V2 - Profiller")
        self.resize(480, 420)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)
        
        self.title_label = QLabel("🎵 Spotify Skipper V2")
        self.title_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #1DB954;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
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
        self.guide_label.setStyleSheet("background-color: #222222; color: #eeeeee; padding: 15px; border-radius: 8px; font-size: 13px;")
        layout.addWidget(self.guide_label)
        
        layout.addSpacing(5)
        
        # TEMA ve PROFİL SEÇİCİ
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Çizim Profili:")
        theme_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([
            "Neon Yeşil (Spotify)",
            "Siber Pembe (Cyberpunk)",
            "Ateş Kırmızısı (Sith)",
            "Buz Mavisi (Glacier)",
            "Özel Profil (Custom)"
        ])
        
        theme_map = {"spotify": 0, "cyberpunk": 1, "sith": 2, "glacier": 3, "custom": 4}
        idx = theme_map.get(self.settings.get("theme", "spotify"), 0)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        
        self.custom_btn = QPushButton("⚙️ Özel Rengi Ayarla")
        self.custom_btn.setCursor(Qt.PointingHandCursor)
        self.custom_btn.clicked.connect(self.open_custom_modal)
        self.custom_btn.setVisible(idx == 4)
        theme_layout.addWidget(self.custom_btn)
        
        layout.addLayout(theme_layout)
        
        # Ayarlar
        self.ctrl_checkbox = QCheckBox("Akıllı Çizim Modunu Aktifleştir")
        self.ctrl_checkbox.setChecked(self.settings.get("ctrl_lock", True))
        self.ctrl_checkbox.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.ctrl_checkbox.toggled.connect(self.on_ctrl_toggled)
        layout.addWidget(self.ctrl_checkbox)
        
        self.startup_checkbox = QCheckBox("Windows ile birlikte başlat")
        self.startup_checkbox.setChecked(self.settings.get("run_on_startup", False))
        self.startup_checkbox.setStyleSheet("font-size: 13px;")
        self.startup_checkbox.toggled.connect(self.on_startup_toggled)
        layout.addWidget(self.startup_checkbox)
        
        layout.addStretch()
        
        # KAYDET BUTONU YENİ EKLENDİ
        self.save_btn = QPushButton("💾 Tüm Ayarları Kaydet")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: black;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        self.save_btn.clicked.connect(lambda: self.save_settings(silent=False))
        layout.addWidget(self.save_btn)
        
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
            QPushButton:hover { background-color: #444444; }
        """)
        self.hide_button.clicked.connect(self.hide)
        layout.addWidget(self.hide_button)
        
        self.setLayout(layout)

    def on_theme_changed(self, index):
        keys = ["spotify", "cyberpunk", "sith", "glacier", "custom"]
        self.settings["theme"] = keys[index]
        self.custom_btn.setVisible(index == 4)
        self.save_settings(silent=True)

    def open_custom_modal(self):
        modal = CustomThemeModal(self, self.settings["custom_main"], self.settings["custom_glow"])
        if modal.exec():
            self.settings["custom_main"] = modal.main_color.name()
            self.settings["custom_glow"] = modal.glow_color.name()
            self.save_settings(silent=True)
            QMessageBox.information(self, "Profil", "Özel profil renkleriniz ayarlandı!")

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
        self.save_settings(silent=True)
        
    def on_startup_toggled(self, checked):
        self.settings["run_on_startup"] = checked
        self.save_settings(silent=True)
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
        if dist < 80:
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
        if self.settings.get("ctrl_lock", True):
            if self.is_key_pressed:
                if not self.drawing_started:
                    if self.draw_start_x is None:
                        self.draw_start_x = x
                        self.draw_start_y = y
                    dist = math.hypot(x - self.draw_start_x, y - self.draw_start_y)
                    if dist > 20: 
                        self.drawing_started = True
                        self.draw_history.append((self.draw_start_x, self.draw_start_y))
                        self.signals.add_point.emit()
                
                if self.drawing_started:
                    self.draw_history.append((x, y))
                    self.signals.add_point.emit()
            return

        # ESKİ MOD: Köşelere kaydırma (Fallback)
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
