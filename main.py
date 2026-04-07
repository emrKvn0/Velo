import sys
import os
import json
import time
import ctypes
import threading
import collections
import winreg

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                               QLabel, QCheckBox, QPushButton, QSystemTrayIcon, 
                               QMenu, QStyle)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt

from pynput import mouse, keyboard

# Medya tuşlarını kontrol edeceğimiz obje
keyboard_controller = keyboard.Controller()

# Dinamik Ekran Boyutlarını Al
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

class SpotifySkipperApp(QWidget):
    def __init__(self):
        super().__init__()
        
        # Varsayılan ayarlar
        self.settings = {
            "ctrl_lock": True,
            "run_on_startup": False
        }
        self.load_settings()
        
        # Hareket takip değişkenleri
        self.history = collections.deque()
        self.last_trigger_time = 0
        self.is_key_pressed = False
        
        # Pynput için arka plan dinleyici thread
        self.pynput_thread = threading.Thread(target=self.run_listeners, daemon=True)
        self.pynput_thread.start()
        
        # Arayüzü ve System Tray'i Hazırla
        self.init_ui()
        self.setup_tray_icon()
        
        # Başlangıca eklenme durumunu doğrula (Kullanıcı dışarıdan elle silmiş olabilir)
        self.set_startup_registry(self.settings["run_on_startup"])

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except Exception as e:
                print("Ayarlar yüklenemedi:", e)

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print("Ayarlar kaydedilemedi:", e)

    def init_ui(self):
        self.setWindowTitle("Spotify Skipper")
        self.resize(360, 200)
        
        # Modern ve Sade Arayüz Tasarımı (PySide6)
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.title_label = QLabel("🎵 Spotify Skipper")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #1DB954;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("Gizli kavis hareketi ile arka planda çalışır.")
        self.subtitle_label.setStyleSheet("color: gray; font-size: 11px;")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle_label)
        
        layout.addSpacing(10)
        
        # Gelişmiş Koruma Modu Seçeneği
        self.ctrl_checkbox = QCheckBox("Güvenlik Kilidi Aktif (Sol CTRL tuşu gerektirir)")
        self.ctrl_checkbox.setChecked(self.settings["ctrl_lock"])
        self.ctrl_checkbox.setStyleSheet("font-size: 13px;")
        self.ctrl_checkbox.setToolTip("Kapalıyken sadece ekran köşelerine çarpma ile çalışır.")
        self.ctrl_checkbox.toggled.connect(self.on_ctrl_toggled)
        layout.addWidget(self.ctrl_checkbox)
        
        # Windows Başlangıç Seçeneği
        self.startup_checkbox = QCheckBox("Windows ile birlikte başlat")
        self.startup_checkbox.setChecked(self.settings["run_on_startup"])
        self.startup_checkbox.setStyleSheet("font-size: 13px;")
        self.startup_checkbox.setToolTip("Bilgisayar açıldığında bu uygulama arka planda başlar.")
        self.startup_checkbox.toggled.connect(self.on_startup_toggled)
        layout.addWidget(self.startup_checkbox)
        
        layout.addStretch()
        
        # Alta Gizle Butonu
        self.hide_button = QPushButton("Arka Plana Gizle")
        self.hide_button.setCursor(Qt.PointingHandCursor)
        self.hide_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.hide_button.clicked.connect(self.hide)
        layout.addWidget(self.hide_button)
        
        self.setLayout(layout)

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # Varsayılan Qt simgelerinden birini Play butonu şeklinde çek
        icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        
        show_action = QAction("Ayarları Göster", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Çıkış", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # İkona çift tıklanınca ana pencereyi aç
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        # Uygulama ekranını "X" basarak kapatınca tamamen kapanmasın, sağ alta gizlensin
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Spotify Skipper",
            "Uygulama arka planda dinlemeye devam ediyor.",
            QSystemTrayIcon.Information,
            2000
        )

    # --- AYAR OLAYLARI ---
    
    def on_ctrl_toggled(self, checked):
        self.settings["ctrl_lock"] = checked
        self.save_settings()
        
    def on_startup_toggled(self, checked):
        self.settings["run_on_startup"] = checked
        self.save_settings()
        self.set_startup_registry(checked)

    def set_startup_registry(self, enabled):
        # Kayıt defteri (Registry) üzerinden uygulamanın arka planda pythonw.exe ile başlatılmasını sağlar
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "SpotifySkipper"
        
        try:
            registry_key = winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS)
            
            # pythonw.exe konsol penceresi göstermeden çalıştırır
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
        except Exception as e:
            print(f"Startup Kayıt Hatası: {e}")

    # --- PYNPUT OLAYLARI (ARKA PLAN THREAD) ---

    def run_listeners(self):
        kbd_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        kbd_listener.start()
        
        with mouse.Listener(on_move=self.on_move) as listener:
            listener.join()

    def on_press(self, key):
        if key == REQUIRED_KEY:
            self.is_key_pressed = True

    def on_release(self, key):
        if key == REQUIRED_KEY:
            self.is_key_pressed = False
            self.history.clear()

    def on_move(self, x, y):
        # Arayüzden GÜVENLİK KİLİDİ açıksa ve tuşa basılmıyorsa işlemi yok say
        if self.settings["ctrl_lock"] and not self.is_key_pressed:
            return

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
                start_time, start_x, start_y = self.history[0]
                
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
    
    # Modern arayüz stili
    app.setStyle("Fusion")
    
    window = SpotifySkipperApp()
    window.show()
    
    sys.exit(app.exec())
