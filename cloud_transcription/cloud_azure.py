# azure_worker.py
import sounddevice as sd
import queue
import numpy as np
import os
import threading
from pydub import AudioSegment 
import soundfile as sf
from PyQt5.QtCore import QObject, pyqtSignal
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()


class AzureTranscriptionWorker(QObject):
    transcription_ready = pyqtSignal(str, str)  # text, source ("azure_interim"/"azure_final")
    finished = pyqtSignal()

    def __init__(self, device_index, rate=48000, lang="en-US",role="Developer",channels=1):
        super().__init__()
        self.device_index = device_index
        self.rate = rate
        self.lang = lang
        self.q = queue.Queue()
        self.audio_buffer = []
        self._running = True
        self.role=role
        self.channels=channels

        # Azure setup
        AZURE_KEY = os.getenv("AZURE_KEY")
        AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")

        speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, endpoint=AZURE_ENDPOINT)
        speech_config.speech_recognition_language = self.lang

        audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=self.rate, bits_per_sample=16, channels=1)
        self.stream = speechsdk.audio.PushAudioInputStream(audio_format)
        audio_config = speechsdk.audio.AudioConfig(stream=self.stream)

        self.recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        # 🔥 Attach both interim + final
        self.recognizer.recognizing.connect(self._on_recognizing)   # interim
        self.recognizer.recognized.connect(self._on_recognized)     # final
        self.recognizer.canceled.connect(self._on_canceled)
        self.recognizer.session_stopped.connect(self._on_session_stopped)

    # ==== Audio ====
    def _callback(self, indata, frames, t, status):
        if status:
            self.transcription_ready.emit(f"[status] {status}", "azure_status")
        if indata.ndim > 1:
            indata = np.mean(indata, axis=1)  # Stereo → mono
        self.q.put(indata.copy())
        #self.audio_buffer.append(indata.copy())

    def _feed_audio(self):
        while self._running:
            data = self.q.get()
            if data is None:
                self.stream.close()
                break
            audio_int16 = (data * 32767).astype(np.int16).tobytes()
            self.stream.write(audio_int16)

    # ==== Event Handlers ====
    def _on_recognizing(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            # emit interim
            self.transcription_ready.emit(evt.result.text, "azure_interim")

    def _on_recognized(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # emit final
            self.transcription_ready.emit(evt.result.text, "azure_final")

    def _on_canceled(self, evt):
        self.transcription_ready.emit(f"[canceled] {evt}", "azure")

    def _on_session_stopped(self, evt):
        self.transcription_ready.emit("[session stopped]", "azure")
        self.stop()

    # ==== Main Run ====
    def run(self):
        try:
            with sd.InputStream(
                samplerate=self.rate,
                device=self.device_index,
                channels=self.channels,
                blocksize=256,
                callback=self._callback
            ):
                self.recognizer.start_continuous_recognition()
                self._feed_audio()  # blocks until stopped

        except Exception as e:
            self.transcription_ready.emit(f"Error: {e}", "error")

        self.finished.emit()

    def stop(self):
        if not self._running:
            return
        self._running = False
        self.q.put(None)
        try:
            self.recognizer.stop_continuous_recognition()
        except Exception:
            pass

