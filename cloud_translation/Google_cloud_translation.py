from PyQt5.QtCore import QObject, pyqtSignal
from google.cloud import translate_v2 as translate
import os, traceback
from dotenv import load_dotenv

load_dotenv()
path = os.getenv("Google_json_path")
#print(path)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("Google_json_path")

class Google_translation_worker(QObject):
    translation_ready = pyqtSignal(str)   # normal result or error message
    finished = pyqtSignal()               # always emitted at end (success or error)

    def __init__(self, text: str, target_language: str):
        super().__init__()
        self.text = text
        self.target_language = target_language

    def run(self):
        try:
            translate_client = translate.Client()

            if isinstance(self.text, bytes):
                self.text = self.text.decode("utf-8")

            # Defensive: don't call API on empty text
            if not (self.text and self.text.strip()):
                self.translation_ready.emit("") 
                return

            # Perform translation
            result = translate_client.translate(
                self.text,
                target_language=self.target_language,
                format_="text"
            )
            translated = result.get("translatedText", "")
            self.translation_ready.emit(translated)

        except Exception as e:
            traceback.print_exc()
            # emit a readable error to UI so slot gets called and thread can be cleaned
            try:
                self.translation_ready.emit(f"[Translation error] {e}")
            except Exception:
                # best-effort: swallow emission errors
                pass

        finally:
            # Always notify that worker finished (so thread can be quit/cleaned)
            try:
                self.finished.emit()
            except Exception:
                pass
