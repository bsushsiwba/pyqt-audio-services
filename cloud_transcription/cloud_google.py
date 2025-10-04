# gcp_worker.py
import sounddevice as sd
import queue
import sys
import numpy as np
import time
from pydub import AudioSegment 
import soundfile as sf
from PyQt5.QtCore import QObject, pyqtSignal
from google.cloud import speech
import os
import requests
import io
import threading
from dotenv import load_dotenv

load_dotenv()
path = os.getenv("Google_json_path")
#print(path)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("Google_json_path")


class GCPTranscriptionWorker(QObject):
    transcription_ready = pyqtSignal(str, str)  # text, source
    finished = pyqtSignal()

    def __init__(self, device_index, rate=48000, lang="en-GB",role="Developer",channels=1):
        super().__init__()
        self.device_index = device_index
        self.rate = rate
        self.lang = lang
        self.q = queue.Queue()
        self._running = True
        self.audio_buffer = []
        #self.save_path="developer.mp3" 
        self.role=role
        self.send_buffer = []
        self.channels=channels

    def _callback(self, indata, frames, t, status):
        if status:
            self.transcription_ready.emit(f"[status] {status}", "gcp")
        if indata.ndim > 1:
            indata = np.mean(indata, axis=1)  # stereo → mono
        self.q.put(indata.copy())



    def _request_generator(self):
        while self._running:
            data = self.q.get()
            if data is None:
                break
            audio_int16 = (data * 32767).astype(np.int16).tobytes()
            yield speech.StreamingRecognizeRequest(audio_content=audio_int16)


    def run(self):
            reconnect_delay = 1.0
            try_count = 0
            while self._running:
                try:
                    client = speech.SpeechClient()
                    config = speech.RecognitionConfig(
                        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=self.rate,
                        language_code=self.lang,
                    )
                    streaming_config = speech.StreamingRecognitionConfig(
                        config=config,
                        interim_results=True
                    )

                    with sd.InputStream(
                        samplerate=self.rate,
                        device=self.device_index,
                        blocksize=256,
                        channels=self.channels,
                        callback=self._callback
                    ):
                        # generator that yields audio chunks
                        requests = self._request_generator()
                        responses = client.streaming_recognize(streaming_config, requests)

                        for response in responses:
                            if not self._running:
                                break
                            for result in response.results:
                                transcript = result.alternatives[0].transcript
                                if result.is_final:
                                    self.transcription_ready.emit(transcript, "gcp_final")
                                else:
                                    self.transcription_ready.emit(transcript, "gcp_interim")

                    # if loop exits cleanly, break if stopping, otherwise try reconnecting
                    if not self._running:
                        break

                except Exception as e:
                    # emit useful debug to UI and try to reconnect a few times
                    try_count += 1
                    self.transcription_ready.emit(f"[gcp error] {repr(e)} (attempt {try_count})", "error")
                    # short delay before reconnecting; if user requested stop, this will end
                    for _ in range(int(reconnect_delay * 10)):
                        if not self._running:
                            break
                        time.sleep(0.1)
                    # gradually increase delay (cap it)
                    reconnect_delay = min(5.0, reconnect_delay * 1.5)
                    continue

            # final cleanup
            self.finished.emit()


    def stop(self):
            self._running = False
            # push sentinel to unblock request generator
            try:
                self.q.put(None)
            except Exception:
                pass

