import os
import json
import sounddevice as sd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
    QComboBox, QCheckBox, QColorDialog, QSpinBox, QFontComboBox,QHBoxLayout,QTextEdit,QLineEdit,QFileDialog,QSplitter
)
from PyQt5.QtCore import  QObject, pyqtSignal,Qt,QThread,QRect,QTimer,pyqtSlot
from PyQt5.QtGui import QFont,QTextOption,QDragEnterEvent,QDropEvent,QMouseEvent
from ui.themes import dark_theme,light_theme,get_stylesheet,LANGUAGE_CODES,DIALECT_OPTIONS
from cloud_transcription.cloud_google import GCPTranscriptionWorker
from cloud_transcription.cloud_azure import AzureTranscriptionWorker
from cloud_transcription.cloud_xfyun import XFYunTranscriptionWorker
from polished_text.polished_text import Polished_text_worker
from cloud_translation.Google_cloud_translation import Google_translation_worker
from cloud_translation.azure_translation import Azure_translation_worker
from cloud_translation.gpt_translation import Translation_worker
#from Langchain_workers.manuel_langchain import LangChainWorker
import requests
from Langchain_workers.shared_transcription_rag import shared_state
from Langchain_workers.Question_Extraction import Question_extraction_worker
from cloud_transcription.recorder import start_recording,stop_recording
from datetime import datetime
import sys
import shutil
WINDOW2_ACTIVE = False
WINDOW5_ACTIVE = False
FILE_EXISTS= False

CONFIG_FILE="config/config.json"
def log_transcript(source: str, text: str, file_path="transcripts.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {source}: {text}\n")

class SettingsManager(QObject):
    setting_changed = pyqtSignal(dict)  # emits full config dict

    def __init__(self):
        super().__init__()
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def set_setting(self, key, value):
        self.config[key] = value
        self.save_config()
        self.setting_changed.emit(self.config)

    def get(self, key, default=None):
        return self.config.get(key, default)

# ----------------- Settings Window -----------------
class SettingsWindow(QWidget):
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setGeometry(200, 200, 400, 500)

        layout = QVBoxLayout()

        # Theme Toggle
        self.theme_toggle = QCheckBox("Dark Theme")
        self.theme_toggle.setChecked(self.settings_manager.get("theme", "light") == "dark")
        layout.addWidget(self.theme_toggle)
        self.theme_toggle.stateChanged.connect(self.update_theme)

        # Font Family
        self.font_dropdown = QFontComboBox()
        self.font_dropdown.setCurrentFont(QFont(self.settings_manager.get("font", "Arial")))
        layout.addWidget(QLabel("Font Family"))
        layout.addWidget(self.font_dropdown)
        self.font_dropdown.currentFontChanged.connect(lambda f: self.settings_manager.set_setting("font", f.family()))

        # Font Size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(self.settings_manager.get("font_size", 12))
        layout.addWidget(QLabel("Font Size"))
        layout.addWidget(self.font_size_spin)
        self.font_size_spin.valueChanged.connect(lambda v: self.settings_manager.set_setting("font_size", v))

        # Font Weight
        self.weight_dropdown = QComboBox()
        self.weight_dropdown.addItems([
            "Thin", "ExtraLight", "Light", "Normal", "Medium",
            "DemiBold", "Bold", "ExtraBold", "Black"
        ])
        self.weight_dropdown.setCurrentText(self.settings_manager.get("weight", "Normal"))
        layout.addWidget(QLabel("Font Weight"))
        layout.addWidget(self.weight_dropdown)
        self.weight_dropdown.currentTextChanged.connect(lambda t: self.settings_manager.set_setting("weight", t))

        # Italic Toggle
        self.italic_toggle = QCheckBox("Italic Text")
        self.italic_toggle.setChecked(self.settings_manager.get("italic", False))
        layout.addWidget(self.italic_toggle)
        self.italic_toggle.stateChanged.connect(lambda s: self.settings_manager.set_setting("italic", bool(s)))

        # Text Color Picker
        self.color_btn = QPushButton("Choose Text Color")
        self.color_btn.clicked.connect(self.choose_text_color)
        layout.addWidget(self.color_btn)

        # Input Sources
        devices = sd.query_devices()
        device_items = [f"{i}: {d['name']}" for i, d in enumerate(devices)]
        self.input_win1 = QComboBox()
        self.input_win1.addItems(device_items)

        saved_input_win1 = self.settings_manager.get("input_win1", {})
        if isinstance(saved_input_win1, dict) and "index" in saved_input_win1:
            match_text = f"{saved_input_win1['index']}: {saved_input_win1['name']}"
            idx = self.input_win1.findText(match_text)
            if idx >= 0:
                self.input_win1.setCurrentIndex(idx)

        layout.addWidget(QLabel("Window 1 Input Source"))
        layout.addWidget(self.input_win1)

        def save_input_win1(text):
            index = int(text.split(":")[0])
            name = text.split(": ", 1)[1]
            dev_info = sd.query_devices(index)
            channels = dev_info["max_input_channels"]
            self.settings_manager.set_setting("input_win1", {"index": index, "name": name,"channels": channels})

        self.input_win1.currentTextChanged.connect(save_input_win1)

        self.input_win4 = QComboBox()
        self.input_win4.addItems(device_items)  # same formatted list as input_win1

        saved_input_win4 = self.settings_manager.get("input_win4", {})
        if isinstance(saved_input_win4, dict) and "index" in saved_input_win4:
            match_text = f"{saved_input_win4['index']}: {saved_input_win4['name']}"
            idx = self.input_win4.findText(match_text)
            if idx >= 0:
                self.input_win4.setCurrentIndex(idx)

        layout.addWidget(QLabel("Window 4 Input Source"))
        layout.addWidget(self.input_win4)

        def save_input_win4(text):
            index = int(text.split(":")[0])
            name = text.split(": ", 1)[1]
            dev_info = sd.query_devices(index)
            channels = dev_info["max_input_channels"]
            self.settings_manager.set_setting("input_win4", {"index": index, "name": name,"channels": channels})

        self.input_win4.currentTextChanged.connect(save_input_win4)
        self.load_window_geometry()
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

        self.setLayout(layout)

    def update_theme(self):
        theme = "dark" if self.theme_toggle.isChecked() else "light"
        self.settings_manager.set_setting("theme", theme)

    def choose_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.settings_manager.set_setting("color", color.name())
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "settings" in config:
                    g = config["settings"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
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

        config["settings"] = g_data

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def closeEvent(self, event):
        self.save_window_geometry()
        super().closeEvent(event)
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
        self.theme_toggle.setFont(font)
        self.font_dropdown.setFont(font)
        self.font_size_spin.setFont(font)
        self.weight_dropdown.setFont(font)
        self.italic_toggle.setFont(font)
        self.color_btn.setFont(font)
        self.input_win1.setFont(font)
        self.input_win4.setFont(font)

# ----------------- Dummy Feature Windows -----------------
class ClickableTextEdit(QTextEdit):
    def __init__(self, placeholder_text, click_callback=None):
        super().__init__()
        self.setReadOnly(True)  # make it read-only
        self.setText(placeholder_text)
        self.click_callback = click_callback  # store callback
        self.setStyleSheet("""
            QTextEdit {
                padding: 15px;
                border: 1px solid gray;
            }
            QTextEdit:hover {
                border: 2px solid red;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.click_callback:
                self.click_callback(self)  # pass reference to clicked box
        super().mousePressEvent(event)


class FeatureWindow8(QWidget):
    def __init__(self, settings_manager):
        super().__init__()
        self.setWindowTitle("Meeting Transcript & Summary")
        self.setGeometry(200, 200, 700, 500)

        self.settings_manager = settings_manager
        self.diarization_running = False
        self.summary_running = False
        self.summary_task_id = None
        self.current_text = ""

        # Polling timer for summary
        self.summary_poll_timer = QTimer()
        self.summary_poll_timer.timeout.connect(self.check_summary_result)

        # Animation timer for "Processing..."
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_processing_animation)
        self.processing_dots = 0

        # --- Layouts ---
        layout = QVBoxLayout()
        
        # Language dropdown (for summary only)
        self.lang_label = QLabel("Select Summary Language")
        layout.addWidget(self.lang_label)

        self.language_dropdown = QComboBox()
        self.language_dropdown.addItems([
            "Chinese", "English", "French", "German", 
            "Spanish", "Portuguese", "Japanese", "Russian", "Arabic"
        ])
        self.language_map = {
            "Chinese": "zh-CN",
            "English": "en-US",
            "French": "fr-FR",
            "German": "de-DE",
            "Spanish": "es-ES",
            "Portuguese": "pt-PT",
            "Japanese": "ja-JP",
            "Russian": "ru-RU",
            "Arabic": "ar-EG"
        }
        layout.addWidget(self.language_dropdown)
        self.model_label = QLabel("Select Summary Model")
        layout.addWidget(self.model_label)

        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems([
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo"
        ])
        layout.addWidget(self.model_dropdown)
        splitter = QSplitter(Qt.Vertical)
        # Transcript box (just loads from transcripts.txt)
        self.transcript_box = ClickableTextEdit(
            "Meeting Diarized Transcript (Editable speaker names)", 
            click_callback=self.on_click
        )
        splitter.addWidget(self.transcript_box)
        self.text_box = QTextEdit()
        self.text_box.setPlaceholderText("Type Your Prompt for summerization")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)  # enables wrapping
        splitter.addWidget(self.text_box)
        
        # Summary box (API-based)
        self.summary_box = ClickableTextEdit(
            "Meeting Summary (Minutes)", 
            click_callback=self.on_click
        )
        splitter.addWidget(self.summary_box)
        splitter.setSizes([800, 100,100])
        layout.addWidget(splitter)

        # Download buttons
        button_layout = QHBoxLayout()
        self.download_transcript_btn = QPushButton("Download Transcript")
        self.download_summary_btn = QPushButton("Download Summary")
        button_layout.addWidget(self.download_transcript_btn)
        button_layout.addWidget(self.download_summary_btn)
        self.download_transcript_btn.clicked.connect(self.save_transcript)
        self.download_summary_btn.clicked.connect(self.save_summary)
        layout.addLayout(button_layout)

        # Load geometry & apply settings
        self.load_window_geometry()
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

        self.setLayout(layout)

    # --- Click handlers ---
    def on_click(self, text_edit_widget):
        if text_edit_widget == self.transcript_box:
            if self.diarization_running:
                return
            self.diarization_running = True
            self.processing_dots = 0
            self.transcript_box.setText("⏳ Processing")
            self.animation_timer.start(600)

            # Simulate "heavy processing" and then load the transcript
            QTimer.singleShot(1500, self.load_transcript_file)

        elif text_edit_widget == self.summary_box:
            if self.summary_running:
                self.summary_box.append("⚠️ Summary already running...")
                return

            if not self.current_text.strip():
                self.summary_box.append("⚠️ No transcript available for summary...")
                return
            if not self.text_box.toPlainText().strip():
                self.summary_box.setPlainText("⚠️ Please enter a prompt for summary")
                return
            else:
            # Clear any previous warning text before starting summary
                self.summary_box.clear()

            # Start summary request
            self.summary_running = True
            self.processing_dots = 0
            self.animation_timer.start(500)

            try:
                selected_lang_name = self.language_dropdown.currentText()
                selected_lang_code = self.language_map.get(selected_lang_name, "en-US")
                prompts=self.text_box.toPlainText()

                resp = requests.post(
                    "http://127.0.0.1:8000/start_summary",
                    json={"diarized": self.current_text,
                           "language": selected_lang_name,
                           "prompt":prompts,
                           "model":self.model_dropdown.currentText()}
                )
                data = resp.json()
                self.summary_task_id = data.get("task_id")

                # Poll every 2 seconds for summary
                self.summary_poll_timer.start(2000)

            except Exception as e:
                self.summary_box.setText("❌ FAST API server not started")
                self.summary_box.append(f"❌ Error starting summary: {e}")
                self.animation_timer.stop()
                self.summary_running = False

    # --- Load transcript.txt ---
    def load_transcript_file(self):
        self.animation_timer.stop()
        if os.path.exists("transcripts.txt"):
            with open("transcripts.txt", "r", encoding="utf-8") as f:
                self.current_text = f.read()
            self.transcript_box.setText(self.current_text)
        else:
            self.transcript_box.setText("⚠️ transcripts.txt not found.")

        self.diarization_running = False

    # --- Processing animation ---
    def update_processing_animation(self):
        self.processing_dots = (self.processing_dots + 1) % 4
        dots = "." * self.processing_dots
        if self.diarization_running:
            self.summary_box.setPlaceholderText(f"⏳ Processing{dots}")
        elif self.summary_running:
            self.summary_box.setPlaceholderText(f"⏳ Processing{dots}")

    # --- Summary polling ---
    def check_summary_result(self):
        if not self.summary_task_id:
            return

        try:
            resp = requests.get(f"http://127.0.0.1:8000/get_summary/{self.summary_task_id}")
            data = resp.json()

            if data.get("status") == "Completed":
                self.animation_timer.stop()
                self.summary_box.setText(data.get("summary"))
                self.summary_poll_timer.stop()
                self.summary_task_id = None
                self.summary_running = False

        except Exception as e:
            self.animation_timer.stop()
            self.summary_box.setText(f"❌ Error while polling: {e}")
            self.summary_poll_timer.stop()
            self.summary_task_id = None
            self.summary_running = False

    # --- Save functions ---
    def save_transcript(self):
        if not self.current_text.strip():
            self.transcript_box.append("⚠️ No transcript to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Transcript", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.transcript_box.toPlainText())
                self.transcript_box.append(f"✅ Transcript saved to {file_path}")
            except Exception as e:
                self.transcript_box.append(f"❌ Error saving transcript: {e}")

    def save_summary(self):
        if not self.summary_box.toPlainText().strip():
            self.summary_box.append("⚠️ No summary to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Summary", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.summary_box.toPlainText())
                self.summary_box.append(f"✅ Summary saved to {file_path}")
            except Exception as e:
                self.summary_box.append(f"❌ Error saving summary: {e}")

    # --- Window geometry ---
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "window8" in config:
                    g = config["window8"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
                if "window8_prompt" in config:
                    self.text_box.setText(config["window8_prompt"])
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

        config["window8"] = g_data
        config["window8_prompt"] = self.text_box.toPlainText()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
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

        self.lang_label.setFont(font)
        self.language_dropdown.setFont(font)
        self.summary_box.setFont(font)
        self.transcript_box.setFont(font)
        self.download_summary_btn.setFont(font)
        self.download_transcript_btn.setFont(font)
        self.text_box.setFont(font)
class ChatInput(QTextEdit):
    send_signal = pyqtSignal()  # custom signal for "send"

    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if event.modifiers() == Qt.ShiftModifier:
                # Shift+Enter → normal newline
                self.insertPlainText("\n")
            else:
                # Enter → trigger send
                self.send_signal.emit()
            return  # stop default behavior
        super().keyPressEvent(event)


class FeatureWindow7C(QWidget):
    def __init__(self,settings_manager:SettingsManager):
        super().__init__()
        self.task_id = None
        self.settings_manager=settings_manager
        self.transcription_text = ""  # from Window 4
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.check_result)

        self.setWindowTitle("Window 7C - Q&A")
        self.setGeometry(240, 240, 500, 400)

        top_layout = QVBoxLayout()
        lang_layout = QHBoxLayout()

        # ---------------- Controls ---------------- #
        # ON/OFF
        onoff_layout = QVBoxLayout()
        self.onoff_label = QLabel("ON/OFF Toggle")
        self.onoff_label.hide()
        onoff_layout.addWidget(self.onoff_label)
        self.btn_onoff = QPushButton("ON/OFF")
        self.btn_onoff.clicked.connect(self.start_query_api)

        onoff_layout.addWidget(self.btn_onoff)
        lang_layout.addLayout(onoff_layout)
        self.btn_onoff.hide()

        # Tone
        tone_layout = QVBoxLayout()
        self.tone_label = QLabel("Answer Tone")
        tone_layout.addWidget(self.tone_label)
        self.Tone_dropdown = QComboBox()
        self.Tone_dropdown.addItems([
            "No tone",
            "A formal, professional tone with clear and well-structured organisation",
            "A pragmatic tone supported by data and evidence",
            "A confident, decisive tone with strong persuasive power",
            "A conservative tone with an awareness of risk management",
            "A humble, reflective tone",
            "A positive, cooperation-oriented tone",
            "An innovative, problem-solving-oriented tone",
            "A relaxed, storytelling tone",
            "A reasonable, empathetic tone"
        ])
        self.Tone_dropdown.setCurrentText("No tone")
        tone_layout.addWidget(self.Tone_dropdown)
        lang_layout.addLayout(tone_layout)

        # Word count
        word_limit_layout = QVBoxLayout()
        self.count_label = QLabel("Word Count")
        word_limit_layout.addWidget(self.count_label)
        self.limit_dropdown = QComboBox()
        self.limit_dropdown.addItems([
            "No Word count", "50 words", "100 words", "200 words",
            "300 words","400 words","500 words","600 words",
            "700 words","800 words","900 words","1000 words",
            "1100 words","1200 words"
        ])
        self.limit_dropdown.setCurrentText("No Word count")
        word_limit_layout.addWidget(self.limit_dropdown)
        lang_layout.addLayout(word_limit_layout)

        # Alternatives
        alter_ans_layout = QVBoxLayout()
        self.alter_ans_label = QLabel("No. Of Alternate Answers")
        alter_ans_layout.addWidget(self.alter_ans_label)
        self.alter_ans = QComboBox()
        self.alter_ans.addItems(["1","2","3","4"])
        self.alter_ans.setCurrentText("1")
        alter_ans_layout.addWidget(self.alter_ans)
        lang_layout.addLayout(alter_ans_layout)

        GPT_layout=QVBoxLayout()
        self.GPT_select = QLabel(f"GPT Model")
        GPT_layout.addWidget(self.GPT_select)
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems(["gpt-4o","gpt-3.5-turbo"])
        GPT_layout.addWidget(self.model_dropdown)
        lang_layout.addLayout(GPT_layout)

        top_layout.addLayout(lang_layout)

        # ---------------- Text Inputs ---------------- #

        splitter = QSplitter(Qt.Vertical)

# History (top)
        self.history_box = QTextEdit()
        self.history_box.setReadOnly(True)
        self.history_box.setPlaceholderText("Previous questions...")
        splitter.addWidget(self.history_box)

        # Input (middle)
        self.text_box = ChatInput()
        self.text_box.setPlaceholderText("Questions (Editable)")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)
        self.text_box.send_signal.connect(self.start_query_api)
        splitter.addWidget(self.text_box)

        # Generated answer (bottom)
        self.generated = QTextEdit()
        self.generated.setReadOnly(True)
        self.generated.setPlaceholderText("Generated Answers.....")
        splitter.addWidget(self.generated)

        # Set sizes for 3 panels (history, input, answers)
        splitter.setSizes([150, 100, 500])   # adjust as you like

        top_layout.addWidget(splitter)

        self.setLayout(top_layout)
        self.load_window_geometry()
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

    # ---------------- API Handling ---------------- #
    def start_query_api(self):
        query = self.text_box.toPlainText().strip()
        if not query:
            self.generated.setPlainText("⚠️ Please enter a question first.")
            return
        if not os.path.exists("chroma_store") and FILE_EXISTS==True:   # replace with your actual folder name/path
            self.text_box.append("⚠️ Reading Document Wait....")
            return
        self.history_box.append(f"❓ {query}")
        self.text_box.clear()

        tone = self.Tone_dropdown.currentText()
        word_limit = None
        if "No Word count" not in self.limit_dropdown.currentText():
            word_limit = int(self.limit_dropdown.currentText().split()[0])
        num_alternatives = int(self.alter_ans.currentText())

        transcription = self.transcription_text


        payload = {
            "query": query,
            "transcription": transcription,
            "tone": tone,
            "word_limit": word_limit,
            "num_alternatives": num_alternatives,
            "model": self.model_dropdown.currentText() 
        }

        try:
            resp = requests.post("http://127.0.0.1:8000/query", json=payload)
            data = resp.json()
            self.task_id = data.get("task_id")
            self.generated.setPlainText("⏳ Processing... please wait.")
            self.poll_timer.start(2000)  # poll every 2 seconds
        except Exception as e:
            self.generated.setPlainText(f"❌ Error: {e}")

    def check_result(self):
        if not self.task_id:
            return

        try:
            resp = requests.get(f"http://127.0.0.1:8000/query_result/{self.task_id}")
            data = resp.json()
            if data.get("status") == "Completed":
                self.generated.setPlainText(data.get("answer"))
                ans=data.get("answer")
                self.history_box.append(f"💡 {ans}")
                self.poll_timer.stop()
                self.task_id = None
        except Exception as e:
            self.generated.setPlainText(f"❌ Error while polling: {e}")
            self.poll_timer.stop()
            self.task_id = None

    # ---------------- Signals from other windows ---------------- #
    def receive_transcription(self, transcript: str):
        self.transcription_text = transcript
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)

                if "window7C" in config:
                    g = config["window7C"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))

                # ✅ Load saved default prompt

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

        config["window7C"] = g_data

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
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
            #self.translation_area.setFont(font)
        self.onoff_label.setFont(font)
        self.tone_label.setFont(font)
        self.count_label.setFont(font)
        self.limit_dropdown.setFont(font)
        self.btn_onoff.setFont(font)
        self.GPT_select.setFont(font)
        self.generated.setFont(font)
        self.text_box.setFont(font)
        self.Tone_dropdown.setFont(font)
        self.alter_ans_label.setFont(font)
        self.alter_ans.setFont(font)
        self.model_dropdown.setFont(font)
        self.history_box.setFont(font)




class Drop_event(QWidget):
    def __init__(self):
        super().__init__()
        self.file_paths = []  # multiple files
        self.layout = QVBoxLayout(self)

        # Drop zone label
        self.label = QLabel("📂 Drag & Drop files here\nor Click to Browse")
        self.label.setFont(QFont("Arial", 12))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                color: #555;
                padding: 40px;
            }
            QLabel:hover {
                border: 2px dashed #0078D7;
                color: #0078D7;
            }
        """)
        self.layout.addWidget(self.label)

        # File list area
        self.files_layout = QVBoxLayout()
        self.layout.addLayout(self.files_layout)

        # Enable drag & drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        for file in files:
            self.add_file(file)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, "Select Documents", "",
                "Documents (*.pdf *.docx *.txt);;All Files (*)"
            )
            for file in file_paths:
                self.add_file(file)

    def add_file(self, file_path):
        if file_path not in self.file_paths:
            self.file_paths.append(file_path)

            row = QHBoxLayout()
            label = QLabel(file_path)
            remove_btn = QPushButton("❌")
            remove_btn.setFixedSize(25, 25)
            remove_btn.clicked.connect(lambda _, f=file_path, r=row: self.remove_file(f, r))

            row.addWidget(label)
            row.addWidget(remove_btn)
            self.files_layout.addLayout(row)

            print("Added file:", file_path)

    def remove_file(self, file_path, row_layout):
        if file_path in self.file_paths:
            self.file_paths.remove(file_path)
            while row_layout.count():
                item = row_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            print("Removed file:", file_path)

    

class FeatureWindow7B(QWidget):
    def __init__(self, settings_manager: SettingsManager, file_paths: list = None):
        super().__init__()
        self.settings_manager = settings_manager
        self.file_paths = file_paths or []
        self.window7C = None
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.check_result)

        self.setWindowTitle("Window 7B")
        self.setGeometry(220, 220, 500, 350)
        self.Qna_Done = True  # True == idle, False == busy

        top_layout = QVBoxLayout()

        # Controls row
        lang_layout = QHBoxLayout()

        onoff_layout = QVBoxLayout()
        self.onoff_label = QLabel("ON/OFF Toggle")
        onoff_layout.addWidget(self.onoff_label)

        # --- BUTTON: start/stop toggle behavior handled in on_toggle_clicked ---
        self.btn_onoff = QPushButton("ON/OFF")
        # connect only to the single handler that starts the work + updates UI
        self.btn_onoff.clicked.connect(self.on_toggle_clicked)
        onoff_layout.addWidget(self.btn_onoff)
        lang_layout.addLayout(onoff_layout)

        # Tone
        tone_layout = QVBoxLayout()
        self.tone_label = QLabel("Answer Tone")
        tone_layout.addWidget(self.tone_label)
        self.Tone_dropdown = QComboBox()
        self.Tone_dropdown.addItems([
            "No tone", "A formal, professional tone with clear and well-structured organisation",
            "A pragmatic tone supported by data and evidence", "A confident, decisive tone with strong persuasive power",
            "A conservative tone with an awareness of risk management","A humble, reflective tone",
            "A positive, cooperation-oriented tone","An innovative, problem-solving-oriented tone",
            "A relaxed, storytelling tone","A reasonable, empathetic tone"
        ])
        self.Tone_dropdown.setCurrentText("No tone")
        tone_layout.addWidget(self.Tone_dropdown)
        lang_layout.addLayout(tone_layout)

        # Word limit
        word_limit_layout = QVBoxLayout()
        self.count_label = QLabel("Word Limit")
        word_limit_layout.addWidget(self.count_label)
        self.limit_dropdown = QComboBox()
        self.limit_dropdown.addItems([
            "No Word count", "50 words", "100 words", "200 words", "300 words",
            "400 words","500 words","600 words","700 words","800 words","900 words",
            "1000 words","1100 words","1200 words"
        ])
        self.limit_dropdown.setCurrentText("No Word count")
        word_limit_layout.addWidget(self.limit_dropdown)
        lang_layout.addLayout(word_limit_layout)

        # Number of Questions
        alter_ques_layout = QVBoxLayout()
        self.alter_ques_label = QLabel("No. Of Alternate Answers")
        alter_ques_layout.addWidget(self.alter_ques_label)
        self.alter_ques = QComboBox()
        self.alter_ques.addItems([str(i) for i in range(1, 9)])
        self.alter_ques.setCurrentText("1")
        alter_ques_layout.addWidget(self.alter_ques)
        lang_layout.addLayout(alter_ques_layout)

        GPT_layout = QVBoxLayout()
        self.GPT_select = QLabel(f"GPT Model")
        GPT_layout.addWidget(self.GPT_select)
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems(["gpt-4o","gpt-3.5-turbo"])
        GPT_layout.addWidget(self.model_dropdown)
        lang_layout.addLayout(GPT_layout)

        # Open Window7C
        btn_layout = QVBoxLayout()
        self.manual_label = QLabel("Manual Questions")
        btn_layout.addWidget(self.manual_label)
        self.btn_open7C = QPushButton("Click Me")
        self.btn_open7C.clicked.connect(self.open_window7C)
        btn_layout.addWidget(self.btn_open7C)
        lang_layout.addLayout(btn_layout)

        top_layout.addLayout(lang_layout)

        # Text areas
        splitter = QSplitter(Qt.Vertical)

        self.text_box = QTextEdit()
        self.text_box.setPlaceholderText("AI Question Prompt (Editable)")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)

        self.generated = QTextEdit()
        self.generated.setReadOnly(True)
        self.generated.setPlaceholderText("Generated Q/A.....")

        splitter.addWidget(self.text_box)
        splitter.addWidget(self.generated)

        splitter.setSizes([100, 900])

        top_layout.addWidget(splitter)
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

        self.setLayout(top_layout)
        self.load_window_geometry()

        # internal state holders
        self.task_id = None
        self.question_queue = []

    # helper to show running/idle UI
    def set_button_running(self, running: bool):
        if running:
            self.btn_onoff.setText("ON")
            # inline style - will be cleared when done
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")
            # disable to prevent further clicks while running
            self.btn_onoff.setEnabled(False)
        else:
            # restore default
            self.btn_onoff.setEnabled(True)
            self.btn_onoff.setText("ON/OFF")
            self.btn_onoff.setStyleSheet("")

    # unified click handler
    def on_toggle_clicked(self, _checked=False):
        # If already busy, ignore additional clicks
        if not self.Qna_Done:
            self.generated.append("Already Busy⚠️")
            return

        # If there is nothing to generate, do nothing
        prompt = self.text_box.toPlainText().strip()
        if not prompt:
            self.generated.append("⚠️ Please enter a prompt first.")
            return

        # mark busy, update UI, and start generation
        self.Qna_Done = False
        self.set_button_running(True)
        # call generator (accepts optional arg from clicked signal)
        self.generte_Questions()

    # accept optional clicked param
    def generte_Questions(self, _=None):
        # create worker to extract questions
        prompt = self.text_box.toPlainText()
        self.worker_thread = QThread()
        self.worker = Question_extraction_worker(prompt, self.model_dropdown.currentText())
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.text_ready.connect(self.update_generated_question)
        # cleanup
        self.worker.text_ready.connect(self.worker_thread.quit)
        self.worker.text_ready.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def start_query_api(self, query=None):
        # start a server-side query (do not block here)
        query1 = self.generated.toPlainText().strip()
        if not query1:
            self.generated.setPlainText("⚠️ Please enter a question first.")
            # if nothing to query, revert UI
            self.Qna_Done = True
            self.set_button_running(False)
            return

        tone = self.Tone_dropdown.currentText()
        word_limit = None
        if "No Word count" not in self.limit_dropdown.currentText():
            word_limit = int(self.limit_dropdown.currentText().split()[0])
        num_alternatives = int(self.alter_ques.currentText())

        payload = {
            "query": query,
            "tone": tone,
            "word_limit": word_limit,
            "num_alternatives": num_alternatives,
            "model": self.model_dropdown.currentText() 

        }

        try:
            resp = requests.post("http://127.0.0.1:8000/query", json=payload)
            data = resp.json()
            self.task_id = data.get("task_id")
            self.generated.append("\n⏳ Processing... please wait.")

        # 🕒 Automatically remove it after 5 seconds
            QTimer.singleShot(5000, lambda: self.remove_processing_message())
            self.poll_timer.start(2000)  # poll every 2 seconds
        except Exception as e:
            self.generated.setPlainText(f"❌ Error: {e}")
            # revert UI on failure
            self.Qna_Done = True
            self.set_button_running(False)

    def check_result(self):
        if not getattr(self, "task_id", None):
            return

        try:
            resp = requests.get(f"http://127.0.0.1:8000/query_result/{self.task_id}")
            data = resp.json()
            if data.get("status") == "Completed":
                self.generated.append("Answer:")
                self.generated.append(data.get("answer"))
                self.generated.append(" ")
                # finished with this single query
                self.poll_timer.stop()
                self.task_id = None
                # if there are more questions, continue; else finish and revert UI
                if self.question_queue:
                    # continue processing next question
                    self.process_next_question()
                else:
                    #self.generated.append("✅ All questions processed.")
                    self.Qna_Done = True
                    self.set_button_running(False)
        except Exception as e:
            self.generated.setPlainText(f"❌ Error while polling: {e}")
            self.poll_timer.stop()
            self.task_id = None
            self.Qna_Done = True
            self.set_button_running(False)
    def remove_processing_message(self):
        """Remove 'Processing...' line from the text box if still present."""
        text = self.generated.toPlainText()
        updated = text.replace("⏳ Processing... please wait.", "").strip()
        self.generated.setPlainText(updated)

    def update_generated_question(self, polished_text: list):
        # If worker emitted an error marker, handle it and return early
        if polished_text and isinstance(polished_text, list):
            first = polished_text[0]
            if isinstance(first, str) and first.startswith("__ERROR__:"):
                err_msg = first.replace("__ERROR__:", "").strip()
                self.generated.setPlainText(f"❌ {err_msg}")
                # make sure UI/button returns to idle
                self.Qna_Done = True
                self.set_button_running(False)
                return

        # normal flow: receive list of questions and begin processing
        self.question_queue = polished_text[:]  # copy
        #self.generated.append("Starting question processing...")
        self.process_next_question()

    def process_next_question(self):
        if not self.question_queue:
            # nothing to do
            self.generated.append("✅ All questions processed.")
            self.Qna_Done = True
            self.set_button_running(False)
            return

        question = self.question_queue.pop(0)
        self.generated.append(f"Question:\n{question}")
        # start query for this question (start_query_api will start poll_timer)
        self.start_query_api(question)

    def delete_chroma_store(self):
        folder_path = "chroma_store"
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            try:
                shutil.rmtree(folder_path)
                print("[INFO] Chroma store deleted successfully.")
            except Exception as e:
                print(f"[ERROR] Could not delete chroma_store: {e}")

    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "window7B" in config:
                    g = config["window7B"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
                if "window7B_prompt" in config:
                    self.text_box.setText(config["window7B_prompt"])
            except Exception as e:
                print("Error loading window 7 position:", e)

    def save_window_geometry(self):
        geometry = self.geometry()
        g_data = {"x": geometry.x(), "y": geometry.y(),
                  "w": geometry.width(), "h": geometry.height()}

        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
            except:
                config = {}

        config["window7B"] = g_data
        config["window7B_prompt"] = self.text_box.toPlainText()

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def apply_settings(self, config):
        self.setStyleSheet(get_stylesheet(config.get("theme", "light")))

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

        self.alter_ques_label.setFont(font)
        self.onoff_label.setFont(font)
        self.tone_label.setFont(font)
        self.count_label.setFont(font)
        self.limit_dropdown.setFont(font)
        self.alter_ques.setFont(font)
        self.btn_onoff.setFont(font)
        self.GPT_select.setFont(font)
        self.manual_label.setFont(font)
        self.btn_open7C.setFont(font)
        self.generated.setFont(font)
        self.text_box.setFont(font)
        self.model_dropdown.setFont(font)
        self.Tone_dropdown.setFont(font)

    def open_window7C(self):
        if self.window7C is None:
            self.window7C = FeatureWindow7C(self.settings_manager)
        self.window7C.show()

    def closeEvent(self, event):
        self.save_window_geometry()
        super().closeEvent(event)


class FeatureWindow7(QWidget):
    #file_selected = pyqtSignal(list)

    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 7 RAG System")
        self.setGeometry(200, 200, 500, 300)
        self.settings_manager=settings_manager

        layout = QVBoxLayout()
        self.dropzone = Drop_event()
        self.btn=QPushButton("Submit or Skip")
        self.btn.clicked.connect(self.on_click)
        self.btn.clicked.connect(self.file_exist)
        layout.addWidget(self.dropzone)
        layout.addWidget(self.btn)
        self.setLayout(layout)
        # print(shared_state.get_transcription())
        # print(f"[Window4] shared_state id = {id(shared_state)}")
        self.load_window_geometry()
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

        self.window7b = None

    def file_exist(self):
        if self.dropzone.file_paths:
            print("Files uploaded:", self.dropzone.file_paths)
            global FILE_EXISTS
            FILE_EXISTS=True
            #self.file_selected.emit(self.dropzone.file_paths)
            for file_path in self.dropzone.file_paths:
                #file_path = self.dropzone.file_paths[0]
                resp = requests.post("http://127.0.0.1:8000/rag_initiate", json={"file_path": file_path})
                if resp.status_code==200:
                    print("Vector DB Created",resp.json())
                    self.window7b=FeatureWindow7B(self.settings_manager, self.dropzone.file_paths)
                    self.window7b.show() 
                else:
                    print("Unable to create file")
        else:
            print("No File found")
            self.window7b=FeatureWindow7B(self.settings_manager)
            self.window7b.show()
        self.close()
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)

                if "window7" in config:
                    g = config["window7"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))


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

        config["window7"] = g_data


        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
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
        self.dropzone.setFont(font)
        self.btn.setFont(font)
    def on_click(self):
        if self.btn.isChecked():
            self.btn.setText("ON")
            self.btn.setStyleSheet("background-color: green; font-weight: bold;")
        elif self.btn.isChecked() and FILE_EXISTS==False:
            self.btn.setText("Next window opening")
            self.btn.setStyleSheet("background-color: green; font-weight: bold;")
        else:
            self.btn.setText("Submitted")
            self.btn.setStyleSheet("background-color: green; font-weight: bold;")

    def closeEvent(self, event):
        self.save_window_geometry()
        self.btn.setStyleSheet("")
        self.btn.setText("Submit or Skip")
        super().closeEvent(event)


class FeatureWindow6(QWidget):
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 6 for Translation")
        self.setGeometry(200, 200, 600, 500)
        self.settings_manager = settings_manager
        self.accumulated_text=" "

        # Main vertical layout
        main_layout = QVBoxLayout()

        # --- Top bar layout ---
        top_layout = QHBoxLayout()


        # Language selection layout
        lang_layout = QVBoxLayout()
        self.language_label = QLabel("Language Selection")
        lang_layout.addWidget(self.language_label)
        self.language_dropdown = QComboBox()
        for name, code in LANGUAGE_CODES.items():
            self.language_dropdown.addItem(name, code)
        self.language_dropdown.setCurrentText("English")
        lang_layout.addWidget(self.language_dropdown)
        top_layout.addLayout(lang_layout)

        # Engine selection layout
        engine_layout = QVBoxLayout()
        self.engine_label = QLabel("Translation Engine")
        engine_layout.addWidget(self.engine_label)
        self.engine_dropdown = QComboBox()
        self.engine_dropdown.addItems(["Engine 1", "Engine 2", "Engine 3"])
        engine_layout.addWidget(self.engine_dropdown)
        top_layout.addLayout(engine_layout)

        

        main_layout.addLayout(top_layout)

        # --- Transcript view ---
        self.text_box = QTextEdit()
        
        #self.text_box.setFixedWidth(100)
        self.text_box.setFixedHeight(80)
        self.text_box.setPlaceholderText("Type Your Prompt")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)
        self.text_box.hide()  # start hidden
        main_layout.addWidget(self.text_box)

        self.mic_box = QTextEdit()
        self.mic_box.setReadOnly(True)
        self.mic_box.setPlaceholderText(f"Translated Text in {self.language_dropdown.currentText()}")
        main_layout.addWidget(self.mic_box)
        self.language_dropdown.currentTextChanged.connect(
            lambda lang: self.mic_box.setPlaceholderText(f"Translated Text in ({lang})"))
        self.engine_dropdown.currentTextChanged.connect(self.toggle_textbox)
        self.download_transcript_btn = QPushButton("Download Transalated Text")
        self.download_transcript_btn.clicked.connect(self.save_polished)
        main_layout.addWidget(self.download_transcript_btn)
        self.load_window_geometry()
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

        
        # Set final layout
        self.setLayout(main_layout)
        self.worker_thread = None
        self.worker = None
    @pyqtSlot(str)
    def handle_new_text(self, text: str):
        """Triggered when W1 or W2 sends fresh text"""
        global WINDOW5_ACTIVE  # import the global flag
        text = text.strip()
        if not text:
            return

        # ✅ If W2 is active, ignore direct W1 input
        if WINDOW5_ACTIVE and self.sender().__class__.__name__ == "FeatureWindow4":
            return

        self.start_translation(text)
    def translate_text(self):
        text = self.mic_box.toPlainText().strip()
        if text:
            self.start_translation(text)  
    def toggle_textbox(self, engine_name):
        if engine_name == "Engine 3":
            self.text_box.show()
        else:
            self.text_box.hide()
    def on_click(self):
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("ON")
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")
        else:
            self.btn_onoff.setText("OFF")
            self.btn_onoff.setStyleSheet("")
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)

                if "window6" in config:
                    g = config["window6"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))

                # ✅ Load saved default prompt

                if "window6_prompt" in config:
                    self.text_box.setPlainText(config["window6_prompt"])

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

        config["window6"] = g_data
        selected_engine = self.engine_dropdown.currentText()
        if selected_engine == "Engine 3":
            config["window6_prompt"] = self.text_box.toPlainText()

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
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
        self.mic_box.setFont(font)
        self.text_box.setFont(font)
        self.language_dropdown.setFont(font)
        self.engine_dropdown.setFont(font)
        self.download_transcript_btn.setFont(font)

        self.language_label.setFont(font)
        self.engine_label.setFont(font)
        #self.engine_label.setFont(font)
    def start_translation(self, text: str):
        if not text or not text.strip():
            print("[W3] start_translation: empty text -> skipping")
            return
        if getattr(self, "busy", False):
            print("[W6] Translation already running, skipping new request.")
            return
        self.busy = True

        target_language = self.language_dropdown.currentData() or self.language_dropdown.currentText()
        selected_engine = self.engine_dropdown.currentText()

        # Safely stop previous worker/thread if running
        if getattr(self, "worker_thread", None) is not None:
            try:
                # ask thread to quit and wait shortly
                self.worker_thread.quit()
                self.worker_thread.wait(1000)
            except Exception:
                pass
            finally:
                self.worker_thread = None
                self.worker = None

        # Create new worker + thread
        self.worker_thread = QThread()
        if selected_engine == "Engine 1":

            self.worker = Google_translation_worker(text, target_language)
            self.worker.translation_ready.connect(self.update_translation_area)

        elif selected_engine == "Engine 2":
            self.worker = Azure_translation_worker(text, target_language)
            self.worker.translation_ready.connect(self.update_translation_area)

        elif selected_engine == "Engine 3":
            #prompt = self.text_box.toPlainText()
            prompt=self.text_box.toPlainText().strip()
            self.worker=Translation_worker(text,target_language,prompt)
            self.worker.translation_ready.connect(self.update_translation_area)

        self.worker.moveToThread(self.worker_thread)

        # Normal flow: when thread starts, call run()
        self.worker.translation_ready.connect(lambda _: setattr(self, "busy", False))
        self.worker_thread.started.connect(self.worker.run)


        # Always ensure thread quits and worker gets deleted when worker signals finished
        if hasattr(self.worker, "finished"):
            self.worker.finished.connect(self.worker_thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        # Start thread
        self.worker_thread.start()


    def update_translation_area(self, translated_text: str):
        scrollbar = self.mic_box.verticalScrollBar()
    # Save distance from bottom
        distance_from_bottom = scrollbar.maximum() - scrollbar.value()
        self.accumulated_text+=" "+translated_text

        self.mic_box.setPlainText(self.accumulated_text)

        # Restore scroll relative to bottom
        scrollbar.setValue(scrollbar.maximum() - distance_from_bottom)

    def closeEvent(self, event):
        if getattr(self, "worker", None) is not None:
            try:
                self.worker.translation_ready.disconnect()
            except Exception:
                pass

        if getattr(self, "worker_thread", None) is not None:
            try:
                self.worker_thread.quit()
                self.worker_thread.wait(1000)
            except Exception as e:
                print(f"[W3] Error stopping worker thread: {e}")
            finally:
                self.worker_thread = None
                self.worker = None
        self.mic_box.setPlainText("")
        self.save_window_geometry()
        super().closeEvent(event)
    def save_polished(self):
        if not self.accumulated_text.strip():
            self.mic_box.append("⚠️ No Transaltion to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Translated Text", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.mic_box.toPlainText())
                self.mic_box.append(f"✅ Translated Text saved to {file_path}")
            except Exception as e:
                self.mic_box.append(f"❌ Error saving Translated Text: {e}")
class FeatureWindow5(QWidget):
    polished_text_ready = pyqtSignal(str) 
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 5 (Polished Text for window 4)")
        self.setGeometry(200, 200, 600, 500)
        self.settings_manager = settings_manager
        self.latest_text = ""
        self.last_sent_text = ""
        self.last_polished_text = ""
        self.accumulated_text=" "
        # Main vertical layout (everything stacks vertically)
        main_layout = QVBoxLayout()

        # --- Top bar (horizontal: left=button, right=text input) ---
        top_layout = QHBoxLayout()

        button_layout=QVBoxLayout()
        self.onoff_label = QLabel("ON/OFF Toggle")
        button_layout.addWidget(self.onoff_label)
        self.btn_onoff = QPushButton("ON / OFF")
        self.btn_onoff.setCheckable(True)
        self.btn_onoff.clicked.connect(self.on_click)
        button_layout.addWidget(self.btn_onoff)

        
        self.GPT_select = QLabel(f"GPT Model")
        button_layout.addWidget(self.GPT_select)
        self.engine_dropdown = QComboBox()
        self.engine_dropdown.addItems(["gpt-4o-mini", "gpt-4o"])
        button_layout.addWidget(self.engine_dropdown)

        top_layout.addLayout(button_layout, stretch=0)

        # Text box on right
        self.text_box = QTextEdit()
        
        self.text_box.setPlaceholderText("Type Your Prompt")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)  # enables wrapping
        top_layout.addWidget(self.text_box, stretch=1)
        self.load_window_geometry()

        main_layout.addLayout(top_layout)

        # --- Translation output area ---
        self.translation_area = QTextEdit()
        self.translation_area.setReadOnly(True)
        self.translation_area.setPlaceholderText("Polished text will appear here...")
        main_layout.addWidget(self.translation_area, stretch=1)

        self.download_transcript_btn = QPushButton("Download Polished Text")
        self.download_transcript_btn.clicked.connect(self.save_polished)
        main_layout.addWidget(self.download_transcript_btn)
        # Apply main layout
        self.setLayout(main_layout)
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)
    def on_click(self):
        global WINDOW5_ACTIVE
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("ON")
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")
            WINDOW5_ACTIVE = True
        else:
            self.btn_onoff.setText("OFF")
            self.btn_onoff.setStyleSheet("")
            WINDOW5_ACTIVE = False
    def receive_text(self, text: str):
        """Called from Window 4 signal"""
        if not self.btn_onoff.isChecked():  
            return
        text = text.strip()
        if not text or text == self.last_sent_text:
            return  # skip empty or duplicate
        self.last_sent_text = text
        self.start_polish(text)

    def try_polish(self):
        """Check if transcript changed & send for polishing"""
        if not self.btn_onoff.isChecked():
            return
        if self.latest_text.strip() and self.latest_text != self.last_sent_text:
            self.last_sent_text = self.latest_text
            self.start_polish(self.latest_text)

    def start_polish(self, text: str):
    # avoid overlapping polish requests
        if getattr(self, "is_polishing", False):
            return
        self.is_polishing = True

        prompt = self.text_box.toPlainText()

        # Create worker + thread
        self.worker_thread = QThread()
        self.worker = Polished_text_worker(text, prompt, self.engine_dropdown.currentText())
        self.worker.moveToThread(self.worker_thread)

        # Run when thread starts
        self.worker_thread.started.connect(self.worker.run)

        # On result
        def on_done(result_text: str):
            self.is_polishing = False
            self.update_translation_area(result_text)
            self.worker_thread.quit()
            self.worker_thread.wait(1000)   # stop the thread cleanly

        self.worker.text_ready.connect(on_done)

        # Cleanup safely
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    # 🔹 Update output + emit polished text
    def update_translation_area(self, polished_text: str):
        if polished_text == self.last_polished_text:
            return

        # Update text
        self.accumulated_text+=" "+polished_text
        self.translation_area.setPlainText(self.accumulated_text)
        self.last_polished_text = polished_text

        # Always scroll to bottom after repaint
        scrollbar = self.translation_area.verticalScrollBar()
        QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))
        print(f"[Window5] final polished_text = '{polished_text}'")
        requests.post("http://127.0.0.1:8000/update_transcription", json={"new_text": polished_text})
        self.polished_text_ready.emit(polished_text)

    # === Window state persistence ===
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "window5" in config:
                    g = config["window5"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
                if "window5_prompt" in config:
                    self.text_box.setText(config["window5_prompt"])
            except Exception as e:
                print("Error loading window 5 position:", e)

    def save_window_geometry(self):
        geometry = self.geometry()
        g_data = {"x": geometry.x(), "y": geometry.y(),
                  "w": geometry.width(), "h": geometry.height()}

        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
            except:
                config = {}

        config["window5"] = g_data
        config["window5_prompt"] = self.text_box.toPlainText()

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def apply_settings(self, config):
        self.setStyleSheet(get_stylesheet(config.get("theme", "light")))

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

        self.translation_area.setFont(font)
        self.text_box.setFont(font)
        self.btn_onoff.setFont(font)
        self.download_transcript_btn.setFont(font)

        self.onoff_label.setFont(font)
        self.GPT_select.setFont(font)
        self.engine_dropdown.setFont(font)


    def closeEvent(self, event):
        """Ensure cleanup when the window is closed."""
        self.save_window_geometry()
        try:
            if getattr(self, "worker_thread", None):
                if self.worker_thread.isRunning():
                    if self.worker and hasattr(self.worker, "stop"):
                        self.worker.stop()

                    try:
                        self.worker.text_ready.disconnect()
                    except Exception:
                        pass

                    self.worker_thread.quit()
                    if not self.worker_thread.wait(3000):  # wait max 3s
                        print("[Window2] Forcing thread termination")
                        self.worker_thread.terminate()
                        self.worker_thread.wait(1000)

        except Exception as e:
            print(f"[Window2] Error during closeEvent: {e}")

        # reset references
        self.worker_thread = None
        self.worker = None
        self.is_polishing = False

        self.btn_onoff.setChecked(False)
        self.btn_onoff.setText("OFF")
        self.btn_onoff.setStyleSheet("")
        self.translation_area.setPlainText("")

        super().closeEvent(event)
    def save_polished(self):
        if not self.accumulated_text.strip():
            self.translation_area.append("⚠️ No polishing to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Polished Text", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.translation_area.toPlainText())
                self.translation_area.append(f"✅ Polished Text saved to {file_path}")
            except Exception as e:
                self.translation_area.append(f"❌ Error saving Polished Text: {e}")


class FeatureWindow4(QWidget):
    polished_text_signal=pyqtSignal(str)
    raw_text_ready = pyqtSignal(str)
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 4 Transcription")
        self.setGeometry(200, 200, 600, 500)
        self.interim_text = ""

        self.settings_manager = settings_manager

        # Thread vars
        #self.speaker_thread = None
        self.speaker_worker = None
        
        # Add accumulated transcript variable
        self.accumulated_transcript = ""

        # Main vertical layout
        main_layout = QVBoxLayout()

        # --- Top bar layout ---
        top_layout = QHBoxLayout()

        # ON/OFF Button
        button_layout = QVBoxLayout()
        self.onoff_label = QLabel("ON/OFF Toggle")
        button_layout.addWidget(self.onoff_label)
        self.btn_onoff = QPushButton("ON / OFF")
        self.btn_onoff.setCheckable(True)
        self.btn_onoff.clicked.connect(self.toggle_speaker_transcription)
        button_layout.addWidget(self.btn_onoff)
        top_layout.addLayout(button_layout)

        # Language selection layout
        lang_layout = QVBoxLayout()
        self.lang_label = QLabel("Language Selection")
        lang_layout.addWidget(self.lang_label)
        self.language_dropdown = QComboBox()
        for name, code in LANGUAGE_CODES.items():
            self.language_dropdown.addItem(name, code)
        self.language_dropdown.setCurrentText("English") 
        lang_layout.addWidget(self.language_dropdown)
        top_layout.addLayout(lang_layout)

        # Engine selection layout
        engine_layout = QVBoxLayout()
        self.engine_label = QLabel(f"Transcription Engine")
        engine_layout.addWidget(self.engine_label)
        self.engine_dropdown = QComboBox()
        self.engine_dropdown.addItems(["Engine 1", "Engine 2", "Engine 3","Engine 4"])
        engine_layout.addWidget(self.engine_dropdown)
        top_layout.addLayout(engine_layout)

        dialect_layout = QVBoxLayout()
        self.dialect_label = QLabel("Dialect Selection")
        dialect_layout.addWidget(self.dialect_label)
        self.dialect_dropdown = QComboBox()
        self.dialect_label.hide()
        self.dialect_dropdown.hide()
        dialect_layout.addWidget(self.dialect_dropdown)
        top_layout.addLayout(dialect_layout)

        self.language_dropdown.currentTextChanged.connect(self.update_dialect_dropdown)
        self.language_dropdown.setCurrentText("English")
        self.update_dialect_dropdown("English")

        main_layout.addLayout(top_layout)

        # --- Transcript view ---
        self.mic_box = QTextEdit()
        self.mic_box.setReadOnly(True)
        self.mic_box.setPlaceholderText(f"Raw Transcript in {self.language_dropdown.currentText()}")
        main_layout.addWidget(self.mic_box)
        self.language_dropdown.currentTextChanged.connect(
            lambda lang: self.mic_box.setPlaceholderText(f"Raw Transcript ({lang})"))
        self.download_transcript_btn = QPushButton("Download Transcript")
        self.download_transcript_btn.clicked.connect(self.save_transcript)
        main_layout.addWidget(self.download_transcript_btn)

        # Set final layout
        self.setLayout(main_layout)
        self.load_window_geometry()

        # Connect settings updates
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

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
        self.mic_box.setFont(font)
        self.onoff_label.setFont(font)
        self.lang_label.setFont(font)
        self.engine_label.setFont(font)

        self.dialect_label.setFont(font)

        self.btn_onoff.setFont(font)
        self.language_dropdown.setFont(font)
        self.engine_dropdown.setFont(font)
        self.dialect_dropdown.setFont(font)
        self.download_transcript_btn.setFont(font)
    def update_dialect_dropdown(self, lang):
        if lang in DIALECT_OPTIONS:
            self.dialect_dropdown.clear()
            for country, code in DIALECT_OPTIONS[lang].items():
                self.dialect_dropdown.addItem(f"{lang} ({country})", code)
            self.dialect_label.show()
            self.dialect_dropdown.show()
        else:
            self.dialect_dropdown.hide()
            self.dialect_label.hide()

    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "window4" in config:
                    g = config["window4"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
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

        config["window4"] = g_data

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def closeEvent(self, event):
        if self.speaker_worker:
            self.speaker_worker.stop()
        if getattr(self, "speaker_thread", None):
            try:
                self.speaker_thread.quit()
                self.speaker_thread.wait(1000)
            except Exception as e:
                print(f"[W1] Error stopping speaker thread: {e}")
            finally:
                self.speaker_thread = None
                self.speaker_worker = None
                self.mic_box.setPlainText("")
                self.btn_onoff.setText("OFF")
                self.btn_onoff.setStyleSheet("")
                self.btn_onoff.setChecked(False)

        self.save_window_geometry()
        super().closeEvent(event)

    def toggle_speaker_transcription(self):
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("ON")
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")

            # Reset transcript when starting
            if getattr(self, "speaker_thread", None) and self.speaker_thread.isRunning():
                print("[W1] Stopping old thread before starting new one")
                if self.speaker_worker:
                    self.speaker_worker.stop()
                self.speaker_thread.quit()
                self.speaker_thread.wait(2000)
                self.speaker_thread = None
                self.speaker_worker = None

            # Reset transcript when starting
            if not getattr(self, "first_start", True):
                self.accumulated_transcript += "--- ⚠️Switched Engine/Language ---\n"
                self.mic_box.append("---⚠️ Switched Engine/Language ---\n")
            else:
                # mark first start
                self.first_start = False

            device_info = self.settings_manager.get("input_win4", {})
            device_index = device_info.get("index", None)
            transcription_language=self.language_dropdown.currentData()
            device_channel=device_info.get("channels", None)

            selected_engine = self.engine_dropdown.currentText()

            self.speaker_thread = QThread()

            if selected_engine == "Engine 1":
                self.speaker_worker = GCPTranscriptionWorker(
                    device_index=device_index,
                    rate=48000,
                    lang=transcription_language,
                    role="Client",
                    channels=device_channel
                )
            elif selected_engine == "Engine 2":
                self.speaker_worker = AzureTranscriptionWorker(
                    device_index=device_index,
                    rate=48000,
                    lang=transcription_language,
                    role="Client",
                    channels=device_channel
                )
            elif selected_engine == "Engine 3":
                self.speaker_worker=XFYunTranscriptionWorker(
                    device_index=device_index,
                    rate=48000,
                    lang=transcription_language,
                    role="Client",
                    channels=device_channel
                )
            elif selected_engine == "Engine 4":
                # 👇 Placeholder only, does nothing
                print("Engine 4 selected (not implemented yet).")
                return

            self.speaker_worker.moveToThread(self.speaker_thread)
            self.speaker_thread.started.connect(self.speaker_worker.run)
            self.speaker_worker.transcription_ready.connect(self.update_speaker_text)
            self.speaker_worker.finished.connect(self.speaker_thread.quit)
            self.speaker_worker.finished.connect(self.speaker_worker.deleteLater)

            # instead of connecting thread.finished to self.speaker_thread.deleteLater,
            # capture the thread object in a lambda and clean up safely:
            thread_ref = self.speaker_thread

            def _on_thread_finished(thread_obj=thread_ref):
                # delete the underlying C++ object and clear attributes only if it's the same object
                try:
                    thread_obj.deleteLater()
                except Exception:
                    pass
                if getattr(self, "speaker_thread", None) is thread_obj:
                    self.speaker_thread = None
                    self.speaker_worker = None

            thread_ref.finished.connect(_on_thread_finished)
            # start
            self.speaker_thread.start()

        else:
            self.btn_onoff.setText("OFF")
            self.btn_onoff.setStyleSheet("")
            if self.speaker_worker:
                self.speaker_worker.stop()
            if getattr(self, "speaker_thread", None):
                try:
                    if self.speaker_thread and self.speaker_thread.isRunning():
                        self.speaker_thread.quit()
                        self.speaker_thread.wait(2000)
                except RuntimeError:
                # thread object was deleted behind our back — treat as stopped
                    self.speaker_thread = None
                    self.speaker_worker = None

    def update_speaker_text(self, text, source):
        if not text.strip():
            return

        if source in ("gcp_interim", "azure_interim", "xfyun_interim"):
            # Overwrite interim text
            self.interim_text = text.strip()
            display_text = (self.accumulated_transcript + " " + self.interim_text).strip()
            self.mic_box.setPlainText(display_text)

        elif source in ("gcp_final", "azure_final", "xfyun_final"):
            # Lock in final text
            
            if self.accumulated_transcript:
                self.accumulated_transcript += " " + text.strip()
            else:
                self.accumulated_transcript = text.strip()

            self.interim_text = ""  # clear interim on final
            self.mic_box.setPlainText(self.accumulated_transcript)
            print(self.accumulated_transcript)

            # Emit signals for downstream
            self.polished_text_signal.emit(text.strip())
            self.raw_text_ready.emit(text.strip())
            #print(f"[Window4] update_speaker_text called with source={source}, text='{text}'")
            #print(f"[Window4] accumulated_transcript = '{self.accumulated_transcript}'")
            requests.post("http://127.0.0.1:8000/update_transcription", json={"new_text": self.accumulated_transcript}) 
            log_transcript("Window 4", text.strip())

        # Auto-scroll
        cursor = self.mic_box.textCursor()
        cursor.movePosition(cursor.End)
        self.mic_box.setTextCursor(cursor)
    def save_transcript(self):
        if not self.accumulated_transcript.strip():
            self.mic_box.append("⚠️ No transcript to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Transcript", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.mic_box.toPlainText())
                self.mic_box.append(f"✅ Transcript saved to {file_path}")
            except Exception as e:
                self.mic_box.append(f"❌ Error saving transcript: {e}")

class FeatureWindow3(QWidget):
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 3 for Translation")
        self.setGeometry(200, 200, 600, 500)
        self.settings_manager = settings_manager
        self.accumulated_text=" "

        # Main vertical layout
        main_layout = QVBoxLayout()

        # --- Top bar layout ---
        top_layout = QHBoxLayout()


        # Language selection layout
        lang_layout = QVBoxLayout()
        self.language_label = QLabel("Language Selection")
        lang_layout.addWidget(self.language_label)
        self.language_dropdown = QComboBox()
        for name, code in LANGUAGE_CODES.items():
            self.language_dropdown.addItem(name, code)
        self.language_dropdown.setCurrentText("English")
        lang_layout.addWidget(self.language_dropdown)
        top_layout.addLayout(lang_layout)

        # Engine selection layout
        engine_layout = QVBoxLayout()
        self.engine_label = QLabel("Translation Engine")
        engine_layout.addWidget(self.engine_label)
        self.engine_dropdown = QComboBox()
        self.engine_dropdown.addItems(["Engine 1", "Engine 2", "Engine 3"])
        engine_layout.addWidget(self.engine_dropdown)
        top_layout.addLayout(engine_layout)

        

        main_layout.addLayout(top_layout)

        # --- Transcript view ---
        self.text_box = QTextEdit()
        
        #self.text_box.setFixedWidth(100)
        self.text_box.setFixedHeight(80)
        self.text_box.setPlaceholderText("Type Your Prompt")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)
        self.text_box.hide()  # start hidden
        main_layout.addWidget(self.text_box)

        self.mic_box = QTextEdit()
        self.mic_box.setReadOnly(True)
        self.mic_box.setPlaceholderText(f"Translated Text in {self.language_dropdown.currentText()}")
        main_layout.addWidget(self.mic_box)
        self.language_dropdown.currentTextChanged.connect(
            lambda lang: self.mic_box.setPlaceholderText(f"Translated Text in ({lang})"))
        self.engine_dropdown.currentTextChanged.connect(self.toggle_textbox)
        self.download_transcript_btn = QPushButton("Download Transalated Text")
        self.download_transcript_btn.clicked.connect(self.save_polished)
        main_layout.addWidget(self.download_transcript_btn)
        self.load_window_geometry()
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)

        self.setLayout(main_layout)
        self.worker_thread = None
        self.worker = None
    @pyqtSlot(str)
    def handle_new_text(self, text: str):
        """Triggered when W1 or W2 sends fresh text"""
        global WINDOW2_ACTIVE  # import the global flag
        text = text.strip()
        if not text:
            return
        # ✅ If W2 is active, ignore direct W1 input
        if WINDOW2_ACTIVE and self.sender().__class__.__name__ == "FeatureWindow1":
            return

        self.start_translation(text)

    def translate_text(self):
        text = self.mic_box.toPlainText().strip()
        if text:
            self.start_translation(text)  
    def toggle_textbox(self, engine_name):
        if engine_name == "Engine 3":
            self.text_box.show()
        else:
            self.text_box.hide()
    def on_click(self):
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("ON")
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")
        else:
            self.btn_onoff.setText("OFF")
            self.btn_onoff.setStyleSheet("")
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)

                if "window3" in config:
                    g = config["window3"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))

                # ✅ Load saved default prompt

                if "window3_prompt" in config:
                    self.text_box.setPlainText(config["window3_prompt"])

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

        config["window3"] = g_data
        selected_engine = self.engine_dropdown.currentText()
        if selected_engine == "Engine 3":
            config["window3_prompt"] = self.text_box.toPlainText()

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
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
        self.mic_box.setFont(font)
        self.text_box.setFont(font)
        self.language_dropdown.setFont(font)
        self.engine_dropdown.setFont(font)
        self.download_transcript_btn.setFont(font)

        self.language_label.setFont(font)
        self.engine_label.setFont(font)
        #self.engine_label.setFont(font)
    def start_translation(self, text: str):
        if not text or not text.strip():
            print("[W3] start_translation: empty text -> skipping")
            return
        if getattr(self, "busy", False):
            print("[W6] Translation already running, skipping new request.")
            return
        self.busy = True

        target_language = self.language_dropdown.currentData() or self.language_dropdown.currentText()
        selected_engine = self.engine_dropdown.currentText()

        # Safely stop previous worker/thread if running
        if getattr(self, "worker_thread", None) is not None:
            try:
                # ask thread to quit and wait shortly
                self.worker_thread.quit()
                self.worker_thread.wait(1000)
            except Exception:
                pass
            finally:
                self.worker_thread = None
                self.worker = None

        # Create new worker + thread
        self.worker_thread = QThread()
        if selected_engine == "Engine 1":

            self.worker = Google_translation_worker(text, target_language)
            self.worker.translation_ready.connect(self.update_translation_area)

        elif selected_engine == "Engine 2":
            self.worker = Azure_translation_worker(text, target_language)
            self.worker.translation_ready.connect(self.update_translation_area)

        elif selected_engine == "Engine 3":
            #prompt = self.text_box.toPlainText()
            prompt=self.text_box.toPlainText().strip()
            self.worker=Translation_worker(text,target_language,prompt)
            self.worker.translation_ready.connect(self.update_translation_area)

        self.worker.moveToThread(self.worker_thread)

        # Normal flow: when thread starts, call run()
        self.worker_thread.started.connect(self.worker.run)
        self.worker.translation_ready.connect(lambda _: setattr(self, "busy", False))

        # Always ensure thread quits and worker gets deleted when worker signals finished
        if hasattr(self.worker, "finished"):
            self.worker.finished.connect(self.worker_thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        # Start thread
        self.worker_thread.start()


    def update_translation_area(self, translated_text: str):
        scrollbar = self.mic_box.verticalScrollBar()
    # Save distance from bottom
        distance_from_bottom = scrollbar.maximum() - scrollbar.value()
        self.accumulated_text+=" "+translated_text
        self.mic_box.setPlainText(self.accumulated_text)

        # Restore scroll relative to bottom
        scrollbar.setValue(scrollbar.maximum() - distance_from_bottom)
        

    def closeEvent(self, event):
        try:
            if getattr(self, "worker_thread", None) and self.worker_thread.isRunning():
                # tell worker to stop if it has a stop() method
                if self.worker and hasattr(self.worker, "stop"):
                    self.worker.stop()

                # disconnect signals so no callbacks after window closes
                try:
                    self.worker.translation_ready.disconnect()
                except Exception:
                    pass

                # quit and wait for thread
                self.worker_thread.quit()
                self.worker_thread.wait(2000) 
        except Exception as e:
                print(f"[Window2] Error during closeEvent: {e}")
        self.mic_box.setPlainText("")
        self.save_window_geometry()
        super().closeEvent(event)
    def save_polished(self):
        if not self.accumulated_text.strip():
            self.mic_box.append("⚠️ No Transaltion to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Translated Text", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.mic_box.toPlainText())
                self.mic_box.append(f"✅ Translated Text saved to {file_path}")
            except Exception as e:
                self.mic_box.append(f"❌ Error saving Translated Text: {e}")
class FeatureWindow2(QWidget):
    polished_text_ready = pyqtSignal(str) 
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 2 (Polished Text for window 1)")
        self.setGeometry(200, 200, 600, 500)
        self.settings_manager = settings_manager
        self.latest_text = ""
        self.last_sent_text = ""
        self.last_polished_text = ""
        self.accumulated_text=" "
        # Main vertical layout (everything stacks vertically)
        main_layout = QVBoxLayout()

        # --- Top bar (horizontal: left=button, right=text input) ---
        top_layout = QHBoxLayout()

        button_layout=QVBoxLayout()
        self.onoff_label = QLabel("ON/OFF Toggle")
        button_layout.addWidget(self.onoff_label)
        self.btn_onoff = QPushButton("ON / OFF")
        self.btn_onoff.setCheckable(True)
        self.btn_onoff.clicked.connect(self.on_click)
        button_layout.addWidget(self.btn_onoff)

        
        self.GPT_select = QLabel(f"GPT Model")
        button_layout.addWidget(self.GPT_select)
        self.engine_dropdown = QComboBox()
        self.engine_dropdown.addItems(["gpt-4o-mini", "gpt-4o"])
        button_layout.addWidget(self.engine_dropdown)

        top_layout.addLayout(button_layout, stretch=0)

        # Text box on right
        self.text_box = QTextEdit()
        
        self.text_box.setPlaceholderText("Type Your Prompt")
        self.text_box.setWordWrapMode(QTextOption.WordWrap)  # enables wrapping
        top_layout.addWidget(self.text_box, stretch=1)
        self.load_window_geometry()

        main_layout.addLayout(top_layout)

        # --- Translation output area ---
        self.translation_area = QTextEdit()
        self.translation_area.setReadOnly(True)
        self.translation_area.setPlaceholderText("Polished text will appear here...")
        main_layout.addWidget(self.translation_area, stretch=1) 

        self.download_transcript_btn = QPushButton("Download Polished Text")
        self.download_transcript_btn.clicked.connect(self.save_polished)
        main_layout.addWidget(self.download_transcript_btn)


        # Apply main layout
        self.setLayout(main_layout)
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)
    def on_click(self):
        global WINDOW2_ACTIVE
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("ON")
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")
            WINDOW2_ACTIVE = True
        else:
            self.btn_onoff.setText("OFF")
            self.btn_onoff.setStyleSheet("")
            WINDOW2_ACTIVE = False

    def receive_text(self, text: str):
        """Called from Window 1 signal"""
        if not self.btn_onoff.isChecked():  
            return 
        text = text.strip()
        if not text or text == self.last_sent_text:
            return  # skip empty or duplicate
        self.last_sent_text = text
        self.start_polish(text)

    def try_polish(self):
        """Check if transcript changed & send for polishing"""
        if not self.btn_onoff.isChecked():
            return
        if self.latest_text.strip() and self.latest_text != self.last_sent_text:
            self.last_sent_text = self.latest_text
            self.start_polish(self.latest_text)

    def start_polish(self, text: str):
    # avoid overlapping polish requests
        if getattr(self, "is_polishing", False):
            return
        self.is_polishing = True

        prompt = self.text_box.toPlainText()

        # Create worker + thread
        self.worker_thread = QThread()
        self.worker = Polished_text_worker(text, prompt, self.engine_dropdown.currentText())
        self.worker.moveToThread(self.worker_thread)

        # Run when thread starts
        self.worker_thread.started.connect(self.worker.run)

        # On result
        def on_done(result_text: str):
            self.is_polishing = False
            self.update_translation_area(result_text)
            self.worker_thread.quit()
            self.worker_thread.wait(1000)   # stop the thread cleanly

        self.worker.text_ready.connect(on_done)

        # Cleanup safely
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def update_translation_area(self, polished_text: str):
        if polished_text == self.last_polished_text:
            return

        # Update text
        self.accumulated_text+=" "+polished_text
        self.translation_area.setPlainText(self.accumulated_text)
        self.last_polished_text = polished_text

        # Always scroll to bottom after repaint
        scrollbar = self.translation_area.verticalScrollBar()
        QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))
        self.polished_text_ready.emit(polished_text)

    
    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "window2" in config:
                    g = config["window2"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
                if "window2_prompt" in config:
                    self.text_box.setText(config["window2_prompt"])
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

        config["window2"] = g_data
        config["window2_prompt"] = self.text_box.toPlainText()

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
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
        self.translation_area.setFont(font)
        self.text_box.setFont(font)
        self.btn_onoff.setFont(font)
        self.download_transcript_btn.setFont(font)

        self.onoff_label.setFont(font)
        self.GPT_select.setFont(font)
        self.engine_dropdown.setFont(font)
        #self..setFont(font)

    def closeEvent(self, event):
        """Ensure cleanup when the window is closed."""
        self.save_window_geometry()
        try:
            if getattr(self, "worker_thread", None):
                if self.worker_thread.isRunning():
                    if self.worker and hasattr(self.worker, "stop"):
                        self.worker.stop()

                    try:
                        self.worker.text_ready.disconnect()
                    except Exception:
                        pass

                    self.worker_thread.quit()
                    if not self.worker_thread.wait(3000):  # wait max 3s
                        print("[Window2] Forcing thread termination")
                        self.worker_thread.terminate()
                        self.worker_thread.wait(1000)

        except Exception as e:
            print(f"[Window2] Error during closeEvent: {e}")

        # reset references
        self.worker_thread = None
        self.worker = None
        self.is_polishing = False

        self.btn_onoff.setChecked(False)
        self.btn_onoff.setText("OFF")
        self.btn_onoff.setStyleSheet("")
        self.translation_area.setPlainText("")

        super().closeEvent(event)
    def save_polished(self):
        if not self.accumulated_text.strip():
            self.translation_area.append("⚠️ No polishing to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Polished Text", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.translation_area.toPlainText())
                self.translation_area.append(f"✅ Polished Text saved to {file_path}")
            except Exception as e:
                self.translation_area.append(f"❌ Error saving Polished Text: {e}")
class FeatureWindow1(QWidget):
    polished_text_signal=pyqtSignal(str)
    raw_text_ready = pyqtSignal(str)

    
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.setWindowTitle("Window 1 Transcription")
        self.setGeometry(200, 200, 600, 500)
        self.interim_text = ""
        

        self.settings_manager = settings_manager

        # Thread vars
        #self.speaker_thread = None
        self.speaker_worker = None
        
        # Add accumulated transcript variable
        self.accumulated_transcript = ""

        # Main vertical layout
        main_layout = QVBoxLayout()

        # --- Top bar layout ---
        top_layout = QHBoxLayout()

        # ON/OFF Button
        button_layout = QVBoxLayout()
        self.onoff_label = QLabel("ON/OFF Toggle")
        button_layout.addWidget(self.onoff_label)
        self.btn_onoff = QPushButton("ON / OFF")
        self.btn_onoff.setCheckable(True)
        self.btn_onoff.clicked.connect(self.toggle_speaker_transcription)
        button_layout.addWidget(self.btn_onoff)
        top_layout.addLayout(button_layout)

        # Language selection layout
        lang_layout = QVBoxLayout()
        self.lang_label = QLabel("Language Selection")
        lang_layout.addWidget(self.lang_label)
        self.language_dropdown = QComboBox()
        for name, code in LANGUAGE_CODES.items():
            self.language_dropdown.addItem(name, code)
        self.language_dropdown.setCurrentText("English") 
        lang_layout.addWidget(self.language_dropdown)
        top_layout.addLayout(lang_layout)

        # Engine selection layout
        engine_layout = QVBoxLayout()
        self.engine_label = QLabel(f"Transcription Engine")
        engine_layout.addWidget(self.engine_label)
        self.engine_dropdown = QComboBox()
        self.engine_dropdown.addItems(["Engine 1", "Engine 2", "Engine 3","Engine 4"])
        engine_layout.addWidget(self.engine_dropdown)
        top_layout.addLayout(engine_layout)

        dialect_layout = QVBoxLayout()
        self.dialect_label = QLabel("Dialect Selection")
        dialect_layout.addWidget(self.dialect_label)
        self.dialect_dropdown = QComboBox()
        self.dialect_label.hide()
        self.dialect_dropdown.hide()
        dialect_layout.addWidget(self.dialect_dropdown)
        top_layout.addLayout(dialect_layout)

        self.language_dropdown.currentTextChanged.connect(self.update_dialect_dropdown)
        self.language_dropdown.setCurrentText("English")
        self.update_dialect_dropdown("English")

        main_layout.addLayout(top_layout)

        # --- Transcript view ---
        self.mic_box = QTextEdit()
        self.mic_box.setReadOnly(True)
        self.mic_box.setPlaceholderText(f"Raw Transcript in {self.language_dropdown.currentText()}")
        main_layout.addWidget(self.mic_box)
        self.language_dropdown.currentTextChanged.connect(
            lambda lang: self.mic_box.setPlaceholderText(f"Raw Transcript ({lang})"))
        self.download_transcript_btn = QPushButton("Download Transcript")
        self.download_transcript_btn.clicked.connect(self.save_transcript)
        main_layout.addWidget(self.download_transcript_btn)

        # Set final layout
        self.setLayout(main_layout)
        self.load_window_geometry()

        # Connect settings updates
        self.settings_manager.setting_changed.connect(self.apply_settings)
        self.apply_settings(self.settings_manager.config)
    def update_dialect_dropdown(self, lang):
        if lang in DIALECT_OPTIONS:
            self.dialect_dropdown.clear()
            for country, code in DIALECT_OPTIONS[lang].items():
                self.dialect_dropdown.addItem(f"{lang} ({country})", code)
            self.dialect_label.show()
            self.dialect_dropdown.show()
        else:
            self.dialect_dropdown.hide()
            self.dialect_label.hide()

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
        self.mic_box.setFont(font)
        self.onoff_label.setFont(font)
        self.lang_label.setFont(font)
        self.engine_label.setFont(font)

        self.dialect_label.setFont(font)

        self.btn_onoff.setFont(font)
        self.language_dropdown.setFont(font)
        self.engine_dropdown.setFont(font)
        self.dialect_dropdown.setFont(font)
        self.download_transcript_btn.setFont(font)

    def load_window_geometry(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                if "window1" in config:
                    g = config["window1"]
                    self.setGeometry(QRect(g["x"], g["y"], g["w"], g["h"]))
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

        config["window1"] = g_data

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def closeEvent(self, event):
        if self.speaker_worker:
            self.speaker_worker.stop()
        if getattr(self, "speaker_thread", None):
            try:
                self.speaker_thread.quit()
                self.speaker_thread.wait(1000)
            except Exception as e:
                print(f"[W1] Error stopping speaker thread: {e}")
            finally:
                self.speaker_thread = None
                self.speaker_worker = None
                self.mic_box.setPlainText("")
                self.btn_onoff.setText("OFF")
                self.btn_onoff.setStyleSheet("")
                self.btn_onoff.setChecked(False)

        self.save_window_geometry()
        super().closeEvent(event)

    def toggle_speaker_transcription(self):
        if self.btn_onoff.isChecked():
            self.btn_onoff.setText("ON")
            self.btn_onoff.setStyleSheet("background-color: green; font-weight: bold;")
            if getattr(self, "speaker_thread", None) and self.speaker_thread.isRunning():
                print("[W1] Stopping old thread before starting new one")
                if self.speaker_worker:
                    self.speaker_worker.stop()
                self.speaker_thread.quit()
                self.speaker_thread.wait(2000)
                self.speaker_thread = None
                self.speaker_worker = None

            # Reset transcript when starting
            if not getattr(self, "first_start", True):
                self.accumulated_transcript += "--- ⚠️Switched Engine/Language ---\n"
                self.mic_box.append("---⚠️ Switched Engine/Language ---\n")
            else:
                # mark first start
                self.first_start = False

            device_info = self.settings_manager.get("input_win1", {})
            device_index = device_info.get("index", None)
            device_channel=device_info.get("channels", None)
            if self.dialect_dropdown.isVisible():
                transcription_language = self.dialect_dropdown.currentData()
            else:
                transcription_language = self.language_dropdown.currentData()
            device_info2 = self.settings_manager.get("input_win4", {})
            device_index2 = device_info2.get("index", None)
            device_channel2=device_info2.get("channels", None)
            #print(device_index)
            #print(device_index2)

            selected_engine = self.engine_dropdown.currentText()
            self.speaker_thread = QThread()

            if selected_engine == "Engine 1":
                self.speaker_worker = GCPTranscriptionWorker(
                    device_index=device_index,
                    rate=48000,
                    lang=transcription_language,
                    role="Developer",
                    channels=device_channel
                )
            elif selected_engine == "Engine 2":
                self.speaker_worker = AzureTranscriptionWorker(
                    device_index=device_index,
                    rate=48000,
                    lang=transcription_language,
                    role="Developer",
                    channels=device_channel
                )
            elif selected_engine == "Engine 3":
                self.speaker_worker=XFYunTranscriptionWorker(
                    device_index=device_index,
                    rate=48000,
                    lang=transcription_language,
                    role="Developer",
                    channels=device_channel
                )
            elif selected_engine == "Engine 4":
                # 👇 Placeholder only, does nothing
                print(" ")
                return
            

                        # AFTER creating self.speaker_thread and moving worker...
            self.speaker_worker.moveToThread(self.speaker_thread)
            self.speaker_thread.started.connect(self.speaker_worker.run)
            self.speaker_worker.transcription_ready.connect(self.update_speaker_text)
            self.speaker_worker.finished.connect(self.speaker_thread.quit)
            self.speaker_worker.finished.connect(self.speaker_worker.deleteLater)

            # instead of connecting thread.finished to self.speaker_thread.deleteLater,
            # capture the thread object in a lambda and clean up safely:
            thread_ref = self.speaker_thread

            def _on_thread_finished(thread_obj=thread_ref):
                # delete the underlying C++ object and clear attributes only if it's the same object
                try:
                    thread_obj.deleteLater()
                except Exception:
                    pass
                if getattr(self, "speaker_thread", None) is thread_obj:
                    self.speaker_thread = None
                    self.speaker_worker = None

            thread_ref.finished.connect(_on_thread_finished)
            # start
            self.speaker_thread.start()


        else:
            self.btn_onoff.setText("OFF")
            self.btn_onoff.setStyleSheet("")
            if self.speaker_worker:
                self.speaker_worker.stop()
            if getattr(self, "speaker_thread", None):
                try:
                    if self.speaker_thread and self.speaker_thread.isRunning():
                        self.speaker_thread.quit()
                        self.speaker_thread.wait(2000)
                except RuntimeError:
                # thread object was deleted behind our back — treat as stopped
                    self.speaker_thread = None
                    self.speaker_worker = None
                    

    def update_speaker_text(self, text, source):
        if not text.strip():
            return

        if source in ("gcp_interim", "azure_interim", "xfyun_interim"):
            # Overwrite interim text
            self.interim_text = text.strip()
            display_text = (self.accumulated_transcript + " " + self.interim_text).strip()
            self.mic_box.setPlainText(display_text)

        elif source in ("gcp_final", "azure_final", "xfyun_final"):
            # Lock in final text
            
            if self.accumulated_transcript:
                self.accumulated_transcript += " " + text.strip()
            else:
                self.accumulated_transcript = text.strip()

            self.interim_text = ""  # clear interim on final
            self.mic_box.setPlainText(self.accumulated_transcript)

            # Emit signals for downstream
            log_transcript("Window 1", text.strip())
            self.polished_text_signal.emit(text.strip())
            self.raw_text_ready.emit(text.strip())

        # Auto-scroll
        cursor = self.mic_box.textCursor()
        cursor.movePosition(cursor.End)
        self.mic_box.setTextCursor(cursor)
    def save_transcript(self):
        if not self.accumulated_transcript.strip():
            self.mic_box.append("⚠️ No transcript to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Transcript", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.mic_box.toPlainText())
                self.mic_box.append(f"✅ Transcript saved to {file_path}")
            except Exception as e:
                self.mic_box.append(f"❌ Error saving transcript: {e}")
