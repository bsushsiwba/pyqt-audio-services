# shared_state.py
from threading import Lock

class SharedState:
    def __init__(self):
        self._lock = Lock()
        self._transcription = ""

    def set_transcription(self, text: str):
        with self._lock:
            print(f"[SharedState] set_transcription: '{self._transcription}'")
            self._transcription = text.strip()

    def get_transcription(self) -> str:
        with self._lock:
            print(f"[SharedState] get_transcription returning: '{self._transcription}'")

            return self._transcription

# Global instance
shared_state = SharedState()
