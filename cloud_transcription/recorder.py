# recorder.py
import sounddevice as sd
import soundfile as sf
import threading

# --- SETTINGS ---
samplerate = 44100
channels = 1
blocksize = 1024  # smaller chunks = smoother stop

# Global stop event and threads
stop_event = threading.Event()
threads = []


def record_audio(device_index, filename):
    print(f"[+] Recording from device {device_index} into {filename}")
    with sf.SoundFile(filename, mode='w', samplerate=samplerate,
                      channels=channels) as file:
        def callback(indata, frames, time_info, status):
            if status:
                print(f"[!] Status for device {device_index}: {status}")
            if not stop_event.is_set():
                file.write(indata.copy())
            else:
                raise sd.CallbackStop()  # stop InputStream cleanly

        with sd.InputStream(device=device_index,
                            samplerate=samplerate,
                            channels=channels,
                            blocksize=blocksize,
                            callback=callback):
            stop_event.wait()  # keep stream alive until stop_event set


# Start recording (from API)
def start_recording(device_index_1: int, device_index_4: int):
    global threads, stop_event
    if threads and any(t.is_alive() for t in threads):
        print("⚠️ Recording already running")
        return
    stop_event.clear()
    t1 = threading.Thread(target=record_audio, args=(device_index_1, "mic1.wav"), daemon=True)
    t2 = threading.Thread(target=record_audio, args=(device_index_4, "mic2.wav"), daemon=True)
    threads = [t1, t2]
    for t in threads:
        t.start()
    print("[!] Recording started...")


# Stop recording (from API)
def stop_recording():
    global threads, stop_event
    stop_event.set()
    for t in threads:
        t.join()
    threads.clear()
    print("[!] Recording stopped.")
