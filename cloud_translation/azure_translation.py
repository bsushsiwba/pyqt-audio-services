# Azure Translation worker
from PyQt5.QtCore import QObject, pyqtSignal
import os, traceback, requests
from dotenv import load_dotenv

class Azure_translation_worker(QObject):
    translation_ready = pyqtSignal(str)   # normal result or error message
    finished = pyqtSignal()               # always emitted at end (success or error)

    def __init__(self, text: str, target_language: str):
        super().__init__()
        self.text = text
        self.target_language = target_language
        load_dotenv()
        # You need to set these as env vars or replace with your values
        self.endpoint = "https://api.cognitive.microsofttranslator.com"
        self.subscription_key = os.getenv("AZURE_KEY")
        self.region = "japanwest" # required for global endpoint
    def run(self):
        try:
            if not self.subscription_key or not self.region:
                raise ValueError("Azure Translator credentials not set in environment variables")

            if isinstance(self.text, bytes):
                self.text = self.text.decode("utf-8")

            if not (self.text and self.text.strip()):
                self.translation_ready.emit("")
                return

            path = "/translate?api-version=3.0"
            params = f"&to={self.target_language}"
            constructed_url = self.endpoint + path + params

            headers = {
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Ocp-Apim-Subscription-Region": self.region,
                "Content-type": "application/json",
            }

            body = [{"text": self.text}]

            response = requests.post(constructed_url, headers=headers, json=body)
            response.raise_for_status()

            result = response.json()
            translated = result[0]["translations"][0]["text"]

            self.translation_ready.emit(translated)

        except Exception as e:
            traceback.print_exc()
            try:
                self.translation_ready.emit(f"[Translation error] {e}")
            except Exception:
                pass

        finally:
            try:
                self.finished.emit()
            except Exception:
                pass
