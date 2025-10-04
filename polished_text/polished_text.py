from PyQt5.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
import os
from openai import OpenAI
load_dotenv()

class Polished_text_worker(QObject):
    text_ready=pyqtSignal(str)
    def __init__(self,text:str,prompt:str,model="gpt-4o-mini"):
        super().__init__()
        self.raw_text=text
        self.prompt=prompt
        self.gpt_model=model
        self._running = True
    def stop(self):
        self._running = False
    def run(self):
        if not self._running:
            return
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            system_prompt = (
                "You are a text editor. "
                "Your only job is to transform the given text according to instructions. "
                "If the input is small (like a letter, symbol, or filler word), "
                "return it unchanged. "
                "Never refuse, never explain, never add anything outside the edited text."
            )
            response = client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Instruction: {self.prompt}\nText: {self.raw_text}"}
                ]
            )
            polished_text = response.choices[0].message.content
            self.text_ready.emit(polished_text)
        except Exception as e:
            self.text_ready.emit(f"Error polishing text: {e}")
    

