# xfyun_worker.py
import sounddevice as sd
import queue
import sys
import numpy as np
import websocket
import json
import base64
import hmac
import hashlib
import time
import threading
from datetime import datetime,timezone
from urllib.parse import urlencode
from PyQt5.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
import os
from pydub import AudioSegment 
import soundfile as sf

load_dotenv()



# ================= XFYun Credentials =================
# Replace these with your actual values
XFYUN_APPID = os.getenv("XFYUN_APPID")        # Replace with your XFYun App ID
XFYUN_API_SECRET = os.getenv("XFYUN_API_SECRET")   # Replace with your API Secret
XFYUN_API_KEY = os.getenv("XFYUN_API_KEY") 


class XFYunTranscriptionWorker(QObject):
    transcription_ready = pyqtSignal(str, str)  # (text, source: "xfyun_interim"/"xfyun_final")
    finished = pyqtSignal()

    def __init__(self, device_index, rate=48000, target_rate=16000, lang="en_us",role="Developer",channels=1):
        super().__init__()
        self.device_index = device_index
        self.rate = rate
        self.target_rate = target_rate
        self.lang = lang
        self.q = queue.Queue()
        self._running = True
        self.ws = None
        self.is_connected = False
        self.frame_count = 0
        self.role=role
        self.channels=channels

    # ------------------- Audio Handling -------------------
    def _callback(self, indata, frames, t, status):
        if status:
            self.transcription_ready.emit(f"[status] {status}", "xfyun_status")
        if indata.ndim > 1:
            indata = np.mean(indata, axis=1)  # stereo → mono
        self.q.put(indata.copy())

    def _resample_audio(self, audio_data, original_rate, target_rate):
        if original_rate == target_rate:
            return audio_data
        duration = len(audio_data) / original_rate
        target_length = int(duration * target_rate)
        indices = np.linspace(0, len(audio_data) - 1, target_length)
        return np.interp(indices, np.arange(len(audio_data)), audio_data)

    # ------------------- WebSocket Callbacks -------------------
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("code") != 0:
                self.transcription_ready.emit(f"XFYun Error: {data.get('message')}", "xfyun_error")
                return

            results = data.get('data', {}).get('result', {})
            if results:
                text = "".join(cw.get('w', '') for ws_item in results.get('ws', []) for cw in ws_item.get('cw', []))
                if text:
                    status = data.get('data', {}).get('status', 0)
                    if status == 2:  # final result
                        self.transcription_ready.emit(text, "xfyun_final")
                    else:  # interim
                        self.transcription_ready.emit(text, "xfyun_interim")

        except Exception as e:
            self.transcription_ready.emit(f"Parse error: {e}", "xfyun_error")

    def _on_error(self, ws, error):
        self.transcription_ready.emit(f"WebSocket error: {error}", "xfyun_error")

    def _on_close(self, ws, code, msg):
        self.is_connected = False
        self.transcription_ready.emit("🔌 Connection closed", "xfyun_status")

    def _on_open(self, ws):
        self.is_connected = True
        self.frame_count = 0
        self.transcription_ready.emit("✅ Connected to XFYun", "xfyun_status")

        # initial frame (handshake)
        params = {
            "common": {"app_id": XFYUN_APPID},
            "business": {
                "language": self.lang,
                "domain": "iat",
                "accent": "english",
                "vad_eos": 60000,
            },
            "data": {
                "status": 0,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": ""
            }
        }
        ws.send(json.dumps(params))

    # ------------------- Audio Sending -------------------
    def _send_audio_data(self):
        while self._running:
            try:
                if not self.is_connected:
                    time.sleep(0.1)
                    continue

                data = self.q.get(timeout=1.0)
                if data is None:
                    break

                resampled = self._resample_audio(data, self.rate, self.target_rate)
                audio_int16 = (resampled * 32767).astype(np.int16)
                audio_b64 = base64.b64encode(audio_int16.tobytes()).decode('utf-8')

                frame = {
                    "data": {
                        "status": 0 if self.frame_count == 0 else 1,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": audio_b64
                    }
                }
                self.ws.send(json.dumps(frame))
                self.frame_count += 1
                time.sleep(0.04)

            except queue.Empty:
                continue
            except Exception as e:
                self.transcription_ready.emit(f"Send error: {e}", "xfyun_error")
                break

    # ------------------- Main Run -------------------
    def _create_url(self):
        host = 'iat-api.xfyun.cn'
        path = '/v2/iat'
        now = datetime.now(timezone.utc)
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')

        # Signature
        signature_string = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(
                XFYUN_API_SECRET.encode('utf-8'),
                signature_string.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
        ).decode('utf-8')

        # Authorization
        auth_origin = f'api_key="{XFYUN_API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        authorization = base64.b64encode(auth_origin.encode('utf-8')).decode('utf-8')

        params = {
            'authorization': authorization,
            'date': date,
            'host': host
        }
        url = f"wss://{host}{path}?{urlencode(params)}"
        #print("[XFYun] Built WebSocket URL:", url)
        return url

    # ------------------- Main Run -------------------
    def run(self):
        try:
            print("[XFYun] Starting worker...")
            url = self._create_url()
            print("[XFYun] Connecting to:", url)

            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            ws_thread.start()

            # wait for connection
            #print("[XFYun] Waiting for connection...")
            time.sleep(2)
            if not self.is_connected:
                self.transcription_ready.emit("❌ Failed to connect to XFYun", "xfyun_error")
                print("[XFYun] Connection failed")
                self.finished.emit()
                return

            print("[XFYun] Connection established, starting audio...")
            # audio sending thread
            audio_thread = threading.Thread(target=self._send_audio_data, daemon=True)
            audio_thread.start()

            with sd.InputStream(
                samplerate=self.rate,
                device=self.device_index,
                channels=self.channels,
                blocksize=256,
                callback=self._callback
            ):
                print("[XFYun] Audio stream open, capturing...")
                while self._running:
                    time.sleep(0.1)

            #print("[XFYun] Stopping stream, sending final frame...")
            # final closing frame
            if self.is_connected and self.ws:
                final_frame = {
                    "data": {
                        "status": 2,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": ""
                    }
                }
                self.ws.send(json.dumps(final_frame))
                time.sleep(1)
                self.ws.close()

        except Exception as e:
            print("[XFYun] Exception in run:", e)
            self.transcription_ready.emit(f"Error: {e}", "xfyun_error")

        print("[XFYun] Worker finished")
        self.finished.emit()

    def stop(self):
        self._running = False
        self.q.put(None)

