import json
import os
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel, QTextEdit, QComboBox, QHBoxLayout,QApplication
from PyQt5.QtCore import QThread, QRect
from PyQt5.QtGui import QFont
from ui.themes import dark_theme, light_theme,get_stylesheet
import threading
import subprocess
import time
from settings import SettingsManager,SettingsWindow,FeatureWindow1,FeatureWindow2,FeatureWindow3,FeatureWindow4,FeatureWindow5,FeatureWindow6,FeatureWindow7,FeatureWindow8

CONFIG_FILE = "config/config.json"

class MainApp(QWidget):
    def __init__(self,settings_manager: SettingsManager):
        super().__init__()
        self.settings_manager = settings_manager
        self.setWindowTitle("Main Control Panel")
        self.setGeometry(100, 100, 400, 500)
        self.current_theme = "light"

        self.load_window_geometry()
        self.settings_win = None 
        self.buttons = []

        # Threads/workers for mic & speaker separately
        self.mic_thread = None
        self.mic_worker = None
        self.speaker_thread = None
        self.speaker_worker = None
        self.uvicorn_process = None  # Will store the subprocess

        # Start FastAPI with delay
        self.start_fastapi_uvicorn_with_delay()

        

        layout = QVBoxLayout()  # main layout (vertical)

        self.open_windows = {}

        # --- Top section: two vertical columns side by side ---
        top_layout = QHBoxLayout()

        # Left column (1–3)
        col1 = QVBoxLayout()
        for i in range(1, 4):
            self.btn = QPushButton(f"Open Window {i}")
            self.btn.clicked.connect(lambda checked, n=i: self.open_feature(n))
            col1.addWidget(self.btn)
            self.buttons.append(self.btn)
        top_layout.addLayout(col1)

        # Right column (4–6)
        col2 = QVBoxLayout()
        for i in range(4, 7):
            self.btn = QPushButton(f"Open Window {i}")
            self.btn.clicked.connect(lambda checked, n=i: self.open_feature(n))
            col2.addWidget(self.btn)
            self.buttons.append(self.btn)
        top_layout.addLayout(col2)

        layout.addLayout(top_layout)

        # --- Bottom section: 7, 8, Settings (stacked vertically) ---
        bottom_layout = QVBoxLayout()
        for i in range(7, 9):
            self.btn = QPushButton(f"Open Window {i}")
            self.btn.clicked.connect(lambda checked, n=i: self.open_feature(n))
            bottom_layout.addWidget(self.btn)
            self.buttons.append(self.btn)
        #FeatureWindow1.polished_text_signal.connect(FeatureWindow2.receive_text)
        self.btn_setting = QPushButton("Open Settings")
        self.btn_setting.clicked.connect(self.open_settings)
        bottom_layout.addWidget(self.btn_setting)
        self.buttons.append(self.btn_setting)

        layout.addLayout(bottom_layout)
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)
        self.setLayout(layout)


    # Dummy ON/OFF toggle
    def toggle_onoff(self):
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("OFF")
        else:
            self.btn_onoff.setText("ON")
    
    def open_feature(self, n):
    # If already open, just bring to front
        if n in self.open_windows and self.open_windows[n] is not None:
            win = self.open_windows[n]
            win.show()
            win.raise_()
            win.activateWindow()
            return

        # Otherwise, create the window
        if n != 9:
            win = globals()[f"FeatureWindow{n}"](self.settings_manager)

        self.open_windows[n] = win

        # Clean up when closed
        win.destroyed.connect(lambda: self.open_windows.update({n: None}))
        win.show()

        # --- Connect signals ---
        if 1 in self.open_windows and 2 in self.open_windows:
            try:
                self.open_windows[1].polished_text_signal.disconnect(self.open_windows[2].receive_text)
            except TypeError:
                pass
            self.open_windows[1].polished_text_signal.connect(self.open_windows[2].receive_text)

        if 2 in self.open_windows and 3 in self.open_windows:
            try:
                self.open_windows[2].polished_text_ready.disconnect(self.open_windows[3].handle_new_text)
            except TypeError:
                pass
            self.open_windows[2].polished_text_ready.connect(self.open_windows[3].handle_new_text)

        if 1 in self.open_windows and 3 in self.open_windows:
            try:
                self.open_windows[1].raw_text_ready.disconnect(self.open_windows[3].handle_new_text)
            except TypeError:
                pass
            self.open_windows[1].raw_text_ready.connect(self.open_windows[3].handle_new_text)
        if 4 in self.open_windows and 5 in self.open_windows:
            try:
                self.open_windows[4].polished_text_signal.disconnect(self.open_windows[5].receive_text)
            except TypeError:
                pass
            self.open_windows[4].polished_text_signal.connect(self.open_windows[5].receive_text)
        if 5 in self.open_windows and 6 in self.open_windows:
            try:
                self.open_windows[5].polished_text_ready.disconnect(self.open_windows[6].handle_new_text)
            except TypeError:
                pass
            self.open_windows[5].polished_text_ready.connect(self.open_windows[6].handle_new_text)
        if 4 in self.open_windows and 6 in self.open_windows:
            try:
                self.open_windows[4].raw_text_ready.disconnect(self.open_windows[6].handle_new_text)
            except TypeError:
                pass
            self.open_windows[4].raw_text_ready.connect(self.open_windows[6].handle_new_text)
        if 4 in self.open_windows and "7C" in self.open_windows:
            try:
                self.open_windows[4].transcription_updated.disconnect(self.open_windows["7C"].receive_transcription)
            except TypeError:
                pass
            self.open_windows[4].transcription_updated.connect(self.open_windows["7C"].receive_transcription)

        # if 7 in self.open_windows and "7C" in self.open_windows:
        #     try:
        #         self.open_windows[7].file_selected.disconnect(self.open_windows["7C"].set_file_path)
        #     except TypeError:
        #         pass
        #     self.open_windows[7].file_selected.connect(self.open_windows["7C"].set_file_path)

    def open_settings(self):
        if self.settings_win is None:
            self.settings_win = SettingsWindow(self.settings_manager)
        self.settings_win.show()
        self.settings_win.raise_()
        self.settings_win.activateWindow()
    def apply_settings(self, config):
        # === Theme background ===
        self.setStyleSheet(get_stylesheet(config.get("theme", "light")))

        # === Font settings ===
        font = QFont()
        font.setFamily(config.get("font", "Arial"))
        font.setPointSize(config.get("font_size", 12))
        font.setItalic(config.get("italic", False))

        weight_map = {
            "Thin": QFont.Thin,
            "ExtraLight": QFont.ExtraLight,
            "Light": QFont.Light,
            "Normal": QFont.Normal,
            "Medium": QFont.Medium,
            "DemiBold": QFont.DemiBold,
            "Bold": QFont.Bold,
            "ExtraBold": QFont.ExtraBold,
            "Black": QFont.Black
        }
        font.setWeight(weight_map.get(config.get("weight", "Normal"), QFont.Normal))

        # Apply font to transcript and labels
        for btn in self.buttons:
            btn.setFont(font)
        # self.language_dropdown.setFont(font)
        # self.engine_dropdown.setFont(font)

    def start_fastapi_uvicorn_with_delay(self):
        """Start FastAPI with uvicorn in a separate thread after 1–2 sec delay"""
        def run_uvicorn():
            time.sleep(1.22)  # 1–2 second relay
            print("[MainApp] Starting FastAPI uvicorn server...")
            # Start uvicorn as a subprocess
            self.uvicorn_process = subprocess.Popen([
                "uvicorn",
                "Langchain_workers.Fastapi_end:app",
                "--host", "127.0.0.1",
                "--port", "8000",
                "--workers","1"
            ])
            self.uvicorn_process.wait()  # Wait for uvicorn to finish (blocks this thread)

        thread = threading.Thread(target=run_uvicorn, daemon=True)
        thread.start()


    # ================= SAVE / LOAD GEOMETRY =================
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)

                if "main_window" in config:
                    g = config["main_window"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))

                # ✅ Load saved default prompt
                # if "window3_prompt" in config:
                #     self.text_box.setPlainText(config["window3_prompt"])

            except Exception as e:
                print("Error loading window position:", e)

    def save_window_geometry(self):
        geometry = self.geometry()
        g_data = {
            "x": geometry.x(),
            "y": geometry.y(),
            "w": geometry.width(),
            "h": geometry.height()
        }

        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
            except:
                config = {}

        config["main_window"] = g_data
        # config["window3_prompt"] = self.text_box.toPlainText()

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def closeEvent(self, event):
        self.save_window_geometry()
        if self.uvicorn_process:
            print("[MainApp] Terminating FastAPI uvicorn server...")
            self.uvicorn_process.terminate()
            self.uvicorn_process.wait()
        try:
            if os.path.exists("transcripts.txt"):
                os.remove("transcripts.txt")
                #print("[Window3] transcripts.txt deleted")
        except Exception as e:
            print(f"[Window3] Error deleting transcripts.txt: {e}")
        super().closeEvent(event)

