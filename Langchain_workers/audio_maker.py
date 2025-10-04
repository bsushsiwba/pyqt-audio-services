# import numpy as np

# # global storage for audio chunks
# global_audio_store = {
#     "Developer": [],
#     "Client": []
# }

# def collect_chunk(role: str, chunk: np.ndarray):
#     """Append new chunk for a role (Developer or Client)."""
#     global_audio_store[role].append(chunk.copy())

# def save_combined():
#     """Combine all chunks and save as one WAV file."""
#     import soundfile as sf
    
#     # Concatenate per role
#     dev_audio = np.concatenate(global_audio_store["Developer"], axis=0) if global_audio_store["Developer"] else None
#     cli_audio = np.concatenate(global_audio_store["Client"], axis=0) if global_audio_store["Client"] else None
    
#     # Simple case: save separately
#     if dev_audio is not None:
#         sf.write("developer.wav", dev_audio, 48000)  # or self.rate
#     if cli_audio is not None:
#         sf.write("client.wav", cli_audio, 48000)
    
#     # If you want to merge both into 2-channel stereo:
#     if dev_audio is not None and cli_audio is not None:
#         min_len = min(len(dev_audio), len(cli_audio))
#         stereo = np.stack([dev_audio[:min_len], cli_audio[:min_len]], axis=1)
#         sf.write("conversation.wav", stereo, 48000)
