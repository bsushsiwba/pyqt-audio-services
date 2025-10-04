# main.py
import sys
from PyQt5.QtWidgets import QApplication
from ui_main import MainApp
from settings import SettingsManager

# disable warnings
import warnings

warnings.filterwarnings("ignore")

# if __name__ == "__main__":
app = QApplication(sys.argv)
settings_manager = SettingsManager()
window = MainApp(settings_manager)
window.show()
sys.exit(app.exec_())
