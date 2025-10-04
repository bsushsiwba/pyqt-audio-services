# Live Transcriber

This project is a **real-time transcription tool** built with **PyQt5** and **OpenAI Whisper**. It allows you to capture audio from a selected input device and transcribe it live. Additionally, it integrates with various cloud services for transcription and translation, including Google Cloud, Azure, and iFlyTech XFYun.

A video guide for this project can be found here: https://www.loom.com/share/your-video-id

---

## 📦 Installation

### Prerequisites

1. **Python Version**: Ensure you have Python 3.9.10 installed.
   1. Download and install Python 3.9.10 from the official [Python website](https://www.python.org/downloads/release/python-3910/).
2. **Git CLI**: Install Git to clone the repository if you haven't already. You can download zip directly from GitHub if you prefer not to use Git.
3. **Virtual Environment**: It is recommended to use a virtual environment to manage dependencies.

### Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/bsushsiwba/pyqt-audio-services
   cd pyqt-audio-services
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python --version  # Ensure it's Python 3.9.10
   python -m venv venv
   # Activate the virtual environment
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - For Google Cloud services, save your JSON key file (e.g., `my-key.json`) and set the environment variable in env along with other cloud service credentials.
     - copy .env.example to .env and fill in the required credentials
       ```bash
         cp .env.example .env
       ```
     - Open and add all the required credentials in the `.env` file.
   - Updating `Google_json_path`,
     - Windows: Use double backslashes `C:\\path\\to\\your\\my-key.json`
     - macOS/Linux: Use single forward slashes `/path/to/your/my-key.json`

---

## ▶️ Running the Application

1. **Run the PyQt application**:
   ```bash
   python main.py
   ```

2. **Select Input Devices for Transcription**:
   - The app supports multiple windows for different transcription streams.
   - In the settings, you’ll find an Input Options dropdown to select the desired input device.
  
3. **Run Desired Windows**:
   - You can now open and run the application windows for transcription and other functionalities.

---

## 🌐 Supported Cloud Services

1. **Google Cloud**: Speech-to-Text and Translation
2. **Azure**: Speech-to-Text and Translation
3. **iFlyTech XFYun**: Speech-to-Text
4. **ChatGPT**: Text polishing and translation

---

## 🛠️ Features

- Real-time transcription from multiple audio input devices.
- Integration with cloud services for enhanced transcription and translation.
- Support for multiple transcription streams in separate windows.
- Customizable themes and settings.

---