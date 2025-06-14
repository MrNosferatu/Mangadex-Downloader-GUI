import sys
from PyQt5.QtWidgets import QApplication
from mangadex_api import MangadexAPI
from ui import MangadexGUI
from settings import Settings

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a consistent look
    
    # Initialize settings
    settings = Settings()
    
    # Initialize API
    api = MangadexAPI()
    
    # Create and show the GUI
    window = MangadexGUI(api, settings)
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()