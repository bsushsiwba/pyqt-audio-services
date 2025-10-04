from PyQt5.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
import os, traceback
from openai import OpenAI

load_dotenv()

class Translation_worker(QObject):
    translation_ready = pyqtSignal(str)   # translation or error
    finished = pyqtSignal()               # always emitted at end

    def __init__(self, text: str, target_language: str, prompt: str = None, model: str = "gpt-4o-mini"):
        super().__init__()
        self.text = text
        self.target_language = target_language
        self.gpt_prompt = prompt
        self.gpt_model = model

    def run(self):
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            if self.gpt_prompt:
                system_prompt = f"{self.gpt_prompt}\nAlways translate the text into {self.target_language} clearly and naturally."
            else:
                system_prompt = f"You are a translation assistant. Translate all user text into {self.target_language} clearly and naturally."

            response = client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": self.text}
                ]
            )

            translated_text = response.choices[0].message.content.strip()
            self.translation_ready.emit(translated_text)

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
