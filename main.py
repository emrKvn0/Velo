import sys
import os
import json
import time
import ctypes
import threading
import collections
import winreg
import math

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QCheckBox, QPushButton, QSystemTrayIcon, 
                               QMenu, QStyle, QComboBox, QDialog, QColorDialog,
                               QMessageBox, QInputDialog, QListWidget)
from PySide6.QtGui import QIcon, QAction, QPainter, QPen, QColor, QFont, QCursor, QPalette
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPoint

from pynput import mouse, keyboard
import recognizer

keyboard_controller = keyboard.Controller()

user32 = ctypes.windll.user32

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
GESTURES_FILE = os.path.join(os.path.dirname(__file__), "gestures.json")

class GlobalGestures:
    def __init__(self):
        self.db = {"profiles": {"Varsayılan Profil": {}}, "active_profile": "Varsayılan Profil"}
        self.load()
        
    def load(self):
        if os.path.exists(GESTURES_FILE):
            try:
                with open(GESTURES_FILE, "r", encoding="utf-8") as f:
                    self.db = json.load(f)
            except Exception: pass
            
    def save(self):
        try:
            with open(GESTURES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.db, f, indent=4)
        except Exception: pass
        
    def get_active_templates(self):
        act = self.db.get("active_profile", "Varsayılan Profil")
        return self.db.get("profiles", {}).get(act, {})


class GestureSignals(QObject):
    add_point = Signal()
    finish_gesture = Signal(str)
    clear_path = Signal()


class DrawingCanvas(QWidget):
    def __init__(self):
        super().__init__()
        # EKRAN ORA(ASPECT RATIO) HESAPLAMA
        # Gerçek bilgisayar ekranı ile aynı oranlara sahip bir tuval tasarlıyoruz
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        if sw == 0: sw = 1920
        if sh == 0: sh = 1080
        
        target_w = 480
        target_h = int(target_w * (sh / sw))
        
        self.setFixedSize(target_w, target_h)
        self.setStyleSheet("background-color: #1a1a1a; border: 4px solid #444; border-radius: 8px;")
        
        self.points = []
        self.is_drawing = False
        self.setCursor(Qt.CrossCursor)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(26, 26, 26))
        
        # Ekranı Taklit Eden Mini Border / İpucu
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.drawRect(2, 2, self.width()-4, self.height()-4)
        
        if not self.points:
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "Monitörünüzün küçültülmüş hali.\nBuraya Basılı Tutarak Şekli Çizin")
            
        if len(self.points) >= 2:
            pen = QPen(QColor(29, 185, 84))
            pen.setWidth(5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            for i in range(len(self.points) - 1):
                p1 = self.points[i]
                p2 = self.points[i+1]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.points.clear()
            self.is_drawing = True
            self.points.append((event.position().x(), event.position().y()))
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.points.append((event.position().x(), event.position().y()))
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_drawing = False

    def clear(self):
        self.points.clear()
        self.update()


class GestureRecorderWindow(QDialog):
    def __init__(self, db_mgr, parent=None):
        super().__init__(parent)
        self.gestures_mgr = db_mgr
        self.setWindowTitle("🎨 Özel Çizim Kaydedici / Eğitim Modu")
        self.resize(800, 500)
        
        layout = QHBoxLayout()
        
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        
        title = QLabel("Yeni Çizim (Gesture) Öğret")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1DB954;")
        left_panel.addWidget(title)
        
        left_panel.addWidget(QLabel("<b>Profil ve Eylem Seç:</b>"))
        prof_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self.load_gesture_list)
        prof_layout.addWidget(self.profile_combo)
        
        new_prof_btn = QPushButton("+")
        new_prof_btn.setFixedWidth(30)
        new_prof_btn.clicked.connect(self.new_profile)
        prof_layout.addWidget(new_prof_btn)
        left_panel.addLayout(prof_layout)
        
        self.action_combo = QComboBox()
        self.action_combo.addItems(["Sonraki Şarkı", "Önceki Şarkı", "Oynat / Duraklat", "Sesi Kapat / Aç"])
        left_panel.addWidget(self.action_combo)
        
        save_btn = QPushButton("💾 Şekli Öğret (Kaydet)")
        save_btn.setStyleSheet("background-color: #1DB954; color: black; font-weight: bold; padding: 10px;")
        save_btn.clicked.connect(self.save_gesture)
        save_btn.setCursor(Qt.PointingHandCursor)
        left_panel.addWidget(save_btn)
        
        left_panel.addWidget(QLabel("<b>Daha Önce Çizilen Şekiller:</b>"))
        self.gesture_list = QListWidget()
        self.gesture_list.itemClicked.connect(self.on_gesture_selected)
        left_panel.addWidget(self.gesture_list)
        
        del_btn = QPushButton("Seçili Şekli Sil")
        del_btn.setStyleSheet("background-color: #aa3333; color: white;")
        del_btn.clicked.connect(self.delete_gesture)
        left_panel.addWidget(del_btn)
        
        self.update_profiles()
        
        right_panel = QVBoxLayout()
        right_panel.setAlignment(Qt.AlignCenter)
        self.canvas = DrawingCanvas()
        
        clear_btn = QPushButton("Tuvali Temizle")
        clear_btn.clicked.connect(self.clear_canvas)
        clear_btn.setFixedWidth(self.canvas.width())
        
        right_panel.addWidget(self.canvas)
        right_panel.addWidget(clear_btn)
        
        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)
        
        self.setLayout(layout)
        
    def update_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        profs = list(self.gestures_mgr.db.get("profiles", {}).keys())
        if not profs:
            profs = ["Varsayılan Profil"]
            self.gestures_mgr.db["profiles"] = {"Varsayılan Profil": {}}
        self.profile_combo.addItems(profs)
        act = self.gestures_mgr.db.get("active_profile")
        if act in profs:
            self.profile_combo.setCurrentText(act)
        self.profile_combo.blockSignals(False)
        self.load_gesture_list()
            
    def new_profile(self):
        text, ok = QInputDialog.getText(self, "Yeni Profil", "Profil adı giriniz:")
        if ok and text.strip():
            prof_name = text.strip()
            if prof_name not in self.gestures_mgr.db["profiles"]:
                self.gestures_mgr.db["profiles"][prof_name] = {}
            self.update_profiles()
            self.profile_combo.setCurrentText(prof_name)
            
    def load_gesture_list(self):
        self.gesture_list.clear()
        profile = self.profile_combo.currentText()
        gestures = self.gestures_mgr.db.get("profiles", {}).get(profile, {})
        for gid, g_data in gestures.items():
            name = g_data.get("name", "Bilinmeyen eylem")
            self.gesture_list.addItem(name)
            self.gesture_list.item(self.gesture_list.count()-1).setData(Qt.UserRole, gid)
            
    def on_gesture_selected(self, item):
        gid = item.data(Qt.UserRole)
        profile = self.profile_combo.currentText()
        gestures = self.gestures_mgr.db.get("profiles", {}).get(profile, {})
        if gid in gestures:
            raw = gestures[gid].get("raw_points", [])
            self.canvas.points = [(p[0], p[1]) for p in raw] if raw else []
            self.canvas.update()
            
    def delete_gesture(self):
        item = self.gesture_list.currentItem()
        if not item: return
        gid = item.data(Qt.UserRole)
        profile = self.profile_combo.currentText()
        if gid in self.gestures_mgr.db["profiles"][profile]:
            del self.gestures_mgr.db["profiles"][profile][gid]
            self.gestures_mgr.save()
            self.load_gesture_list()
            self.canvas.clear()
            if self.parent(): self.parent().update_gesture_profiles_ui()
            
    def clear_canvas(self):
        self.canvas.clear()
        
    def save_gesture(self):
        if len(self.canvas.points) < 5:
            QMessageBox.warning(self, "Hata", "Lütfen tuvale belirgin bir şekil çizin!")
            return
            
        action_idx = self.action_combo.currentIndex()
        action_map = ["media_next", "media_previous", "media_play_pause", "media_volume_mute"]
        action_name = self.action_combo.currentText()
        action_key = action_map[action_idx]
        profile = self.profile_combo.currentText()
        
        norm_pts = recognizer.normalize(self.canvas.points)
        gid = f"gesture_{int(time.time())}"
        
        self.gestures_mgr.db["profiles"][profile][gid] = {
            "name": action_name,
            "action": action_key,
            "points": norm_pts,
            "raw_points": self.canvas.points
        }
        self.gestures_mgr.save()
        
        if self.parent():
            self.parent().update_gesture_profiles_ui()
            
        self.load_gesture_list()
        QMessageBox.information(self, "Başarılı", f"Özel çiziminiz (Gesture) '{profile}' profiline eklendi!")


class CustomThemeModal(QDialog):
    def __init__(self, parent=None, current_main="#1DB954", current_glow="#1DB954"):
        super().__init__(parent)
        self.setWindowTitle("🎨 Özel Renk Seçici")
        self.resize(320, 200)
        self.main_color = QColor(current_main)
        self.glow_color = QColor(current_glow)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        info = QLabel("Kendi neon renklerinizi seçin:")
        layout.addWidget(info)
        
        self.main_btn = QPushButton("Ana Çizgi Rengini Seç")
        self.main_btn.setStyleSheet(f"background-color: {self.main_color.name()}; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.main_btn.clicked.connect(self.pick_main)
        layout.addWidget(self.main_btn)
        
        self.glow_btn = QPushButton("Dış Parlama (Neon) Rengini Seç")
        self.glow_btn.setStyleSheet(f"background-color: {self.glow_color.name()}; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.glow_btn.clicked.connect(self.pick_glow)
        layout.addWidget(self.glow_btn)
        
        save_btn = QPushButton("Kaydet ve Kapat")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)
        self.setLayout(layout)
        
    def pick_main(self):
        c = QColorDialog.getColor(self.main_color, self, "Ana Çizgi Rengi")
        if c.isValid():
            self.main_color = c
            self.main_btn.setStyleSheet(f"background-color: {c.name()};")
            
    def pick_glow(self):
        c = QColorDialog.getColor(self.glow_color, self, "Neon Rengi Seç")
        if c.isValid():
            self.glow_color = c
            self.glow_btn.setStyleSheet(f"background-color: {c.name()};")


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
        if theme == "cyberpunk": return QColor(255, 105, 180), QColor(255, 0, 255)
        elif theme == "sith": return QColor(255, 100, 100), QColor(255, 0, 0)
        elif theme == "glacier": return QColor(150, 255, 255), QColor(0, 150, 255)
        elif theme == "custom": return QColor(self.app_settings.get("custom_main", "#ffffff")), QColor(self.app_settings.get("custom_glow", "#1DB954"))
        return QColor(29, 185, 84), QColor(29, 185, 84)
        
    def add_point(self):
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
        self.fade_timer.start(25)
        
    def clear_path(self):
        self.fade_timer.start(25)
        
    def fade_step(self):
        needs_update = False
        if self.fade_alpha > 0:
            self.fade_alpha = max(0, self.fade_alpha - 15)
            needs_update = True
        else:
            if self.path: self.path.clear()
                
        if self.text_alpha > 0:
            self.text_alpha = max(0, self.text_alpha - 5)
            needs_update = True
            
        if needs_update: self.update()
        else: self.fade_timer.stop()
            
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
                painter.drawLine(self.path[i][0], self.path[i][1], self.path[i+1][0], self.path[i+1][1])
            
            main_color = QColor(main_c.red(), main_c.green(), main_c.blue(), self.fade_alpha)
            pen_main = QPen(main_color)
            pen_main.setWidth(6)
            pen_main.setCapStyle(Qt.RoundCap)
            pen_main.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen_main)
            for i in range(len(self.path) - 1):
                painter.drawLine(self.path[i][0], self.path[i][1], self.path[i+1][0], self.path[i+1][1])
                
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
        
        self.gestures_mgr = GlobalGestures()
        
        self.settings = {
            "ctrl_lock": True,
            "run_on_startup": False,
            "theme": "spotify",
            "custom_main": "#ffffff",
            "custom_glow": "#1DB954",
            "trigger_key": "ctrl_l"
        }
        self.load_settings()
        
        self.signals = GestureSignals()
        self.overlay = OverlayWindow(self.settings)
        self.overlay.show()
        
        self.signals.add_point.connect(self.overlay.add_point)
        self.signals.finish_gesture.connect(self.overlay.finish_gesture)
        self.signals.clear_path.connect(self.overlay.clear_path)
        
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
            except Exception: pass

    def save_settings(self, silent=True):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            self.gestures_mgr.save()
            if not silent:
                QMessageBox.information(self, "Başarılı", "✅ Tüm ayarlarınız kaydedildi!")
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Hata", f"Kaydedilirken hata oluştu: {e}")

    def get_trigger_key(self):
        k = self.settings.get("trigger_key", "ctrl_l")
        if k == "alt_l": return keyboard.Key.alt_l
        if k == "shift_l": return keyboard.Key.shift_l
        if k == "ctrl_r": return keyboard.Key.ctrl_r
        return keyboard.Key.ctrl_l

    def init_ui(self):
        self.setWindowTitle("Spotify Skipper V3 - Tam Kontrol")
        self.resize(520, 500)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)
        
        self.title_label = QLabel("🎵 Spotify Skipper V3")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1DB954;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        gesture_btn = QPushButton("🎨 Özel Şekiller (Gestures) Oluştur")
        gesture_btn.setCursor(Qt.PointingHandCursor)
        gesture_btn.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #C2185B; }
        """)
        gesture_btn.clicked.connect(self.open_gesture_recorder)
        layout.addWidget(gesture_btn)
        
        prof_layout = QHBoxLayout()
        prof_layout.addWidget(QLabel("<b>Aktif Çizim Profili:</b>"))
        self.gesture_profile_combo = QComboBox()
        self.update_gesture_profiles_ui()
        self.gesture_profile_combo.currentIndexChanged.connect(self.on_gesture_profile_changed)
        prof_layout.addWidget(self.gesture_profile_combo)
        layout.addLayout(prof_layout)
        
        trigger_layout = QHBoxLayout()
        trigger_layout.addWidget(QLabel("<b>Tetikleyici Tuş (Kısayol):</b>"))
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["Sol CTRL", "Sağ CTRL", "Sol ALT", "Sol SHIFT"])
        tm = {"ctrl_l": 0, "ctrl_r": 1, "alt_l": 2, "shift_l": 3}
        self.trigger_combo.setCurrentIndex(tm.get(self.settings.get("trigger_key", "ctrl_l"), 0))
        self.trigger_combo.currentIndexChanged.connect(self.on_trigger_changed)
        trigger_layout.addWidget(self.trigger_combo)
        layout.addLayout(trigger_layout)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("<b>Neon Renk Teması:</b>"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Neon Yeşil (Spotify)", "Siber Pembe (Cyberpunk)", "Ateş Kırmızısı (Sith)", "Buz Mavisi (Glacier)", "Özel Profil (Custom)"])
        theme_map = {"spotify": 0, "cyberpunk": 1, "sith": 2, "glacier": 3, "custom": 4}
        idx = theme_map.get(self.settings.get("theme", "spotify"), 0)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        self.custom_btn = QPushButton("⚙️ Özel Renk")
        self.custom_btn.clicked.connect(self.open_custom_modal)
        self.custom_btn.setVisible(idx == 4)
        theme_layout.addWidget(self.custom_btn)
        layout.addLayout(theme_layout)
        
        layout.addWidget(QLabel("<b>Diğer Ayarlar:</b>"))
        self.startup_checkbox = QCheckBox("Windows ile birlikte başlat")
        self.startup_checkbox.setChecked(self.settings.get("run_on_startup", False))
        self.startup_checkbox.toggled.connect(self.on_startup_toggled)
        layout.addWidget(self.startup_checkbox)
        
        layout.addStretch()
        
        self.save_btn = QPushButton("💾 Tüm Ayarları Kaydet")
        self.save_btn.setStyleSheet("background-color: #1DB954; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.save_btn.clicked.connect(lambda: self.save_settings(silent=False))
        layout.addWidget(self.save_btn)
        
        self.hide_button = QPushButton("Arka Plana Gizle")
        self.hide_button.setStyleSheet("background-color: #333333; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
        self.hide_button.clicked.connect(self.hide)
        layout.addWidget(self.hide_button)
        
        self.setLayout(layout)

    def update_gesture_profiles_ui(self):
        self.gesture_profile_combo.blockSignals(True)
        self.gesture_profile_combo.clear()
        profs = list(self.gestures_mgr.db.get("profiles", {}).keys())
        if not profs: profs = ["Varsayılan Profil"]
        self.gesture_profile_combo.addItems(profs)
        act = self.gestures_mgr.db.get("active_profile")
        if act in profs: self.gesture_profile_combo.setCurrentText(act)
        self.gesture_profile_combo.blockSignals(False)

    def on_gesture_profile_changed(self, text):
        self.gestures_mgr.db["active_profile"] = text
        self.gestures_mgr.save()

    def on_trigger_changed(self, index):
        keys = ["ctrl_l", "ctrl_r", "alt_l", "shift_l"]
        self.settings["trigger_key"] = keys[index]
        self.save_settings(silent=True)

    def open_gesture_recorder(self):
        modal = GestureRecorderWindow(self.gestures_mgr, self)
        modal.exec()

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
        self.tray_icon.showMessage("Spotify Skipper V3", "Uygulama arka planda dinliyor.", QSystemTrayIcon.Information, 2000)
        
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
            if not os.path.exists(python_exe): python_exe = sys.executable
            script_path = os.path.abspath(__file__)
            command = f'"{python_exe}" "{script_path}"'
            if enabled: winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, command)
            else:
                try: winreg.DeleteValue(registry_key, app_name)
                except FileNotFoundError: pass
            winreg.CloseKey(registry_key)
        except Exception: pass

    def run_listeners(self):
        kbd_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        kbd_listener.start()
        with mouse.Listener(on_move=self.on_move) as listener:
            listener.join()

    def on_press(self, key):
        if key == self.get_trigger_key():
            self.is_key_pressed = True
            self.drawing_started = False
            self.draw_start_x = None
            self.draw_start_y = None
            self.draw_history.clear()

    def on_release(self, key):
        if key == self.get_trigger_key():
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
            
        total_dist = 0
        for i in range(1, len(self.draw_history)):
            total_dist += math.hypot(self.draw_history[i][0] - self.draw_history[i-1][0], 
                                     self.draw_history[i][1] - self.draw_history[i-1][1])
                                     
        if total_dist < 40:
            self.signals.clear_path.emit()
            return

        templates = self.gestures_mgr.get_active_templates()
        if not templates:
            # ARTIK FALLBACK ESKİ KOD YOK, YALNIZCA ÖĞRETİLENLER...
            self.signals.finish_gesture.emit("Lütfen bir şekil öğretin ❌")
            return
            
        # AKILLI ŞABLON KARŞILAŞTIRMA MANTIĞI
        best_template, score = recognizer.recognize(self.draw_history, templates, threshold=150.0)
        
        if best_template:
            action = best_template["action"]
            name = best_template["name"]
            
            key_mapped = getattr(keyboard.Key, action, None)
            if key_mapped:
                keyboard_controller.press(key_mapped)
                keyboard_controller.release(key_mapped)
                
            icon = "👉" if "Sonraki" in name else "👈" if "Önceki" in name else "⏯" if "Oynat" in name else "🔇" if "Ses" in name else "✨"
            self.signals.finish_gesture.emit(f"{name} {icon}")
        else:
            self.signals.finish_gesture.emit("Bilinmeyen Şekil ❓")

    def on_move(self, x, y):
        # Yalnızca Yeni Şekil Çizim Motoru var. Eski Edge Swap kodu tamamen silindi.
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
