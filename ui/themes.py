dark_theme = {
    "background": "#000000",
    "text": "#FFFFFF",
    "button": "#333333",
    "button_text": "#FFFFFF",
    "input": "#222222",
    "input_text": "#FFFFFF"
}

light_theme = {
    "background": "#FFFFFF",
    "text": "#000000",
    "button": "#DDDDDD",
    "button_text": "#000000",
    "input": "#FFFFFF",
    "input_text": "#000000"
}


def get_stylesheet(theme: str) -> str:
    if theme == "dark":
        return """
        QWidget {
            background-color: #121212;
            color: #FFFFFF;
        }
        QPushButton {
            background-color: #1E1E1E;
            color: #FFFFFF;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 6px;
        }
        QPushButton:hover {
            background-color: #2C2C2C;
        }
        QLabel {
            color: #FFFFFF;
        }
        QComboBox {
            background-color: #1E1E1E;
            color: #FFFFFF;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 4px;
        }
        QTextEdit {
            background-color: #1E1E1E;
            color: #FFFFFF;
            border: 1px solid #333;
            border-radius: 6px;
        }
        """
    else:  # default light theme
        return """
        QWidget {
            background-color: #FFFFFF;
            color: #000000;
        }
        QPushButton {
            background-color: #F0F0F0;
            color: #000000;
            border: 1px solid #CCC;
            border-radius: 6px;
            padding: 6px;
        }
        QPushButton:hover {
            background-color: #E0E0E0;
        }
        QLabel {
            color: #000000;
        }
        QComboBox {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #CCC;
            border-radius: 6px;
            padding: 4px;
        }
        QTextEdit {
            background-color: #FFFFFF;
            color: #000000;
            border: 1px solid #CCC;
            border-radius: 6px;
        }
        """
LANGUAGE_CODES = {
    "Chinese": "zh-CN",
    "English": "en-US",
    "French": "fr-FR",
    "German": "de-DE",
    "Spanish": "es-ES",
    "Portuguese": "pt-PT",
    "Japanese": "ja-JP",
    "Russian": "ru-RU",
    "Arabic": "ar-SA"
}
GPT_Models={
    "gpt 4o":"gpt-4o-2024-05-13",
    "gpt 4 turbo":"gpt-4-turbo-2024-04-09"
}
DIALECT_OPTIONS = {
    "English": {
        "UK": "en-GB",
        "US": "en-US",
        "Ghana": "en-GH",
        "Kenya": "en-KE",
        "Tanzania": "en-TZ",
        "India": "en-IN"
    },
    "French": {
        "France": "fr-FR",
        "Canada": "fr-CA",
        "Switzerland": "fr-CH"
    },
    "German": {
        "Germany": "de-DE",
        "Austria": "de-AT",
        "Switzerland": "de-CH"
    }
}
