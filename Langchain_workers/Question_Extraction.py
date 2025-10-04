import json
from PyQt5.QtCore import QThread, pyqtSignal
from openai import OpenAI
import requests, os

class Question_extraction_worker(QThread):
    # emit a list of questions OR a single error marker string in the list
    text_ready = pyqtSignal(list)

    def __init__(self, prompt: str, gpt_model="gpt-4o-mini"):
        super().__init__()
        self.gpt_model = gpt_model
        self.prompt = prompt

    def run(self):
        try:
            # small timeout so thread doesn't hang forever
            resp = requests.get("http://127.0.0.1:8000/get_transcription", timeout=6)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            transcription = data.get("transcription", "")

            # If transcription is missing/empty -> emit structured error and stop
            if not transcription or not str(transcription).strip():
                self.text_ready.emit([f"__ERROR__: No transcription available. Please record or upload audio before running question extraction."])
                return

        except requests.RequestException as e:
            # network / server error -> emit error and stop
            self.text_ready.emit([f"__ERROR__: Failed to fetch transcription: {e}"])
            return
        except ValueError as e:
            # JSON decode error
            self.text_ready.emit([f"__ERROR__: Invalid response from transcription endpoint: {e}"])
            return

        # --- Only proceed to call OpenAI if we have a non-empty transcription ---
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
            model=self.gpt_model,
            temperature=0,         # deterministic responses
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict question extractor. Given a transcription, "
                        "identify explicit user questions and return a JSON array of strings containing "
                        "one representative question per distinct topic or intent. Follow these rules exactly:\n\n"
                        "1) RETURN ONLY: a JSON array of question strings (example: [\"Which payment methods do you accept?\"]). "
                        "Do NOT add any explanation, commentary, or code fences.\n"
                        "2) ONE PER TOPIC: If multiple lines in the transcription ask about the same topic, return a single clear representative question for that topic.\n"
                        "3) DO NOT PARAPHRASE: Do not produce multiple phrasings of the same question or invent follow-ups. If the same question appears twice, return it once.\n"
                        "4) PREFER EXPLICIT QUESTIONS: Only extract actual questions or clearly phrased intent to ask. Prefer sentences that end with a question mark. If none are present, return an empty list: [].\n"
                        "5) CLEANUP: Remove filler words and keep the question concise and well-formed. Ensure every item in the JSON array is a single question string ending with '?'.\n\n"
                        "Examples:\n"
                        "Input: \"Which payment method do you guys take is it Visa or MasterCard?\"\n"
                        "Output: [\"Which payment method do you guys take?\"]\n\n"
                        "Input: \"I was wondering about delivery times. Also, do you accept MasterCard?\"\n"
                        "Output: [\"What are your delivery times?\", \"Do you accept MasterCard?\"]\n\n"
                        "If the transcription contains no explicit question, return: []"
                    )
                },
                {
                    "role": "user",
                    "content": f"Transcription:\n{transcription}\n\nUser prompt/context: {self.prompt}"
                }
            ]
        )

            raw_output = response.choices[0].message.content.strip()

            try:
                questions = json.loads(raw_output)
                if not isinstance(questions, list):
                    questions = [str(questions)]
            except Exception:
                # If parsing fails, still return raw output as a single item (falls back gracefully)
                questions = [raw_output]

            self.text_ready.emit(questions)

        except Exception as e:
            # OpenAI or unexpected error
            self.text_ready.emit([f"__ERROR__: Error extracting questions: {e}"])
