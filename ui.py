from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QRadioButton, QFileDialog, QScrollArea, 
                             QButtonGroup, QDialog, QCheckBox, QProgressBar, QMessageBox,
                             QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, QObject
from PyQt5.QtGui import QPixmap, QImage
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from io import BytesIO
import os
import threading
import time

class MangaCard(QWidget):
    download_clicked = pyqtSignal(dict)
    
    def __init__(self, manga_data):
        super().__init__()
        self.manga_data = manga_data
        self.init_ui()
        
    def init_ui(self):
        self.layout = QHBoxLayout()
        
        # Cover image
        cover_layout = QVBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150, 200)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("background-color: #f0f0f0;")
        
        # Info layout - create a fixed height container
        info_container = QWidget()
        info_container.setFixedHeight(200)  # Match the cover image height
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = self.manga_data.get("attributes", {}).get("title", {}).get("en", "Unknown Title")
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        
        # Tags
        tags = []
        for tag in self.manga_data.get("attributes", {}).get("tags", []):
            tag_name = tag.get("attributes", {}).get("name", {}).get("en")
            if tag_name:
                tags.append(tag_name)
        
        if tags:
            tags_label = QLabel(f"<i>Tags: {', '.join(tags[:5])}</i>")
            tags_label.setWordWrap(True)
            info_layout.addWidget(tags_label)
        
        # Description
        description = self.manga_data.get("attributes", {}).get("description", {}).get("en", "No description available.")
        if len(description) > 200:
            description = description[:200] + "..."
        
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        # Add stretch to push content to the top
        info_layout.addStretch(1)
        
        # Download button
        download_btn = QPushButton("Download")
        download_btn.clicked.connect(self.on_download_clicked)
        info_layout.addWidget(download_btn)
        
        # Find cover art
        cover_file = None
        for relationship in self.manga_data.get("relationships", []):
            if relationship.get("type") == "cover_art":
                cover_file = relationship.get("attributes", {}).get("fileName")
                break
        
        if cover_file:
            manga_id = self.manga_data.get("id")
            cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_file}"
            
            # Create a loading placeholder
            self.cover_label.setText("Loading...")
            
            # Create signal emitter for thread communication
            class ImageSignalEmitter(QObject):
                image_loaded = pyqtSignal(QPixmap)
            
            signal_emitter = ImageSignalEmitter()
            signal_emitter.image_loaded.connect(self.set_cover_image)
            
            # Load image in a background thread
            def load_image_thread(url, emitter):
                try:
                    # Create a session with retry capability
                    session = requests.Session()
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                    )
                    adapter = HTTPAdapter(max_retries=retry_strategy)
                    session.mount("http://", adapter)
                    session.mount("https://", adapter)
                    
                    response = session.get(url)
                    if response.status_code == 200:
                        img = QImage()
                        img.loadFromData(response.content)
                        pixmap = QPixmap.fromImage(img)
                        scaled_pixmap = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        emitter.image_loaded.emit(scaled_pixmap)
                except Exception as e:
                    print(f"Error loading cover: {e}")
            
            # Start the image loading thread
            threading.Thread(target=load_image_thread, args=(cover_url, signal_emitter), daemon=True).start()
        
        cover_layout.addWidget(self.cover_label)
        self.layout.addLayout(cover_layout)
        self.layout.addWidget(info_container, 1)
        
        self.setLayout(self.layout)
        
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
    
    def set_cover_image(self, pixmap):
        """Set the cover image when loaded from the background thread"""
        self.cover_label.setPixmap(pixmap)
        
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
    def on_download_clicked(self):
        self.download_clicked.emit(self.manga_data)


class ChapterSelectionDialog(QDialog):
    def __init__(self, api, manga_id, preferred_language="en", parent=None, 
                 downloaded_chapters=None, incomplete_chapters=None):
        super().__init__(parent)
        self.api = api
        self.manga_id = manga_id
        self.preferred_language = preferred_language
        self.chapters = {"data": []}
        self.selected_chapters = []
        self.downloaded_chapters = downloaded_chapters or []
        self.incomplete_chapters = incomplete_chapters or []
        self.init_ui()
        self.load_chapters(preferred_language)
        
    def init_ui(self):
        self.setWindowTitle("Select Chapters to Download")
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Language selection
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        
        self.language_combo = QComboBox()
        self.language_combo.setMaxVisibleItems(15)  # Limit the dropdown height
        
        # Language dictionary with codes and display names
        self.languages = {
            "en": "English",
            "af": "Afrikaans",
            "sq": "Albanian",
            "ar": "Arabic",
            "az": "Azerbaijani",
            "eu": "Basque",
            "be": "Belarusian",
            "bn": "Bengali",
            "bg": "Bulgarian",
            "my": "Burmese",
            "ca": "Catalan",
            "zh": "Chinese (Simplified)",
            "zh-hk": "Chinese (Traditional)",
            "cv": "Chuvash",
            "hr": "Croatian",
            "cs": "Czech",
            "da": "Danish",
            "nl": "Dutch",
            "eo": "Esperanto",
            "et": "Estonian",
            "fil": "Filipino",
            "fi": "Finnish",
            "fr": "French",
            "ka": "Georgian",
            "de": "German",
            "el": "Greek",
            "he": "Hebrew",
            "hi": "Hindi",
            "hu": "Hungarian",
            "id": "Indonesian",
            "ga": "Irish",
            "it": "Italian",
            "ja": "Japanese",
            "jv": "Javanese",
            "kk": "Kazakh",
            "ko": "Korean",
            "la": "Latin",
            "lt": "Lithuanian",
            "ms": "Malay",
            "mn": "Mongolian",
            "ne": "Nepali",
            "no": "Norwegian",
            "fa": "Persian",
            "pl": "Polish",
            "pt": "Portuguese",
            "pt-br": "Portuguese (Br)",
            "ro": "Romanian",
            "ru": "Russian",
            "sr": "Serbian",
            "sk": "Slovak",
            "sl": "Slovenian",
            "es": "Spanish",
            "es-la": "Spanish (LATAM)",
            "sv": "Swedish",
            "ta": "Tamil",
            "te": "Telugu",
            "th": "Thai",
            "tr": "Turkish",
            "uk": "Ukrainian",
            "ur": "Urdu",
            "uz": "Uzbek",
            "vi": "Vietnamese"
        }
        
        # Add languages to combo box
        for code, name in self.languages.items():
            self.language_combo.addItem(name, code)
        
        # Set default language
        index = 0
        for i in range(self.language_combo.count()):
            if self.preferred_language == self.language_combo.itemData(i):
                index = i
                break
        self.language_combo.setCurrentIndex(index)
        
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        lang_layout.addWidget(self.language_combo)
        
        layout.addLayout(lang_layout)
        
        # Chapter list
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        
        # Set the scroll area to take up more space
        layout.addWidget(self.scroll_area, 1)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        download_btn = QPushButton("Download")
        download_btn.clicked.connect(self.accept)
        button_layout.addWidget(download_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_chapters(self, language_code):
        # Clear previous chapters
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.chapter_checkboxes = []
        
        # Show loading message
        loading_label = QLabel("Loading chapters...")
        loading_label.setAlignment(Qt.AlignCenter)
        self.scroll_layout.addWidget(loading_label)
        
        # Create signal emitter in the main thread
        from PyQt5.QtCore import QObject, pyqtSignal
        
        class SignalEmitter(QObject):
            update_signal = pyqtSignal(object)
        
        signal_emitter = SignalEmitter()
        signal_emitter.update_signal.connect(self.update_chapters_ui)
        
        # Load chapters in a separate thread to keep UI responsive
        def fetch_chapters(emitter):
            chapters = self.api.get_manga_chapters(self.manga_id, language_code)
            # Use signal to update UI in main thread
            emitter.update_signal.emit(chapters)
        
        # Start thread with the emitter as an argument
        threading.Thread(target=fetch_chapters, args=(signal_emitter,), daemon=True).start()
    
    def update_chapters_ui(self, chapters):
        # Remove loading label
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Add chapters
        self.chapters = chapters
        if not self.chapters.get("data", []):
            no_chapters = QLabel(f"No chapters available in selected language")
            no_chapters.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(no_chapters)
            return
        
        # Create a container widget to hold all checkboxes
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(2)  # Minimal spacing between items
        container_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        for chapter in self.chapters.get("data", []):
            chapter_attrs = chapter.get("attributes", {})
            chapter_num = chapter_attrs.get("chapter", "Unknown")
            chapter_title = chapter_attrs.get("title", f"Chapter {chapter_num}")
            
            checkbox = QCheckBox(f"Chapter {chapter_num}: {chapter_title}")
            checkbox.setProperty("chapter_id", chapter.get("id"))
            checkbox.setProperty("chapter_data", chapter)
            
            # Mark as downloaded if it exists
            if chapter_num in self.downloaded_chapters:
                checkbox.setText(f"✓ Chapter {chapter_num}: {chapter_title} (Already Downloaded)")
                checkbox.setStyleSheet("color: green;")
            # Mark as incomplete if it exists but is incomplete
            elif chapter_num in self.incomplete_chapters:
                checkbox.setText(f"⚠ Chapter {chapter_num}: {chapter_title} (Incomplete)")
                checkbox.setStyleSheet("color: orange;")
                checkbox.setChecked(True)  # Auto-select incomplete chapters
                
            self.chapter_checkboxes.append(checkbox)
            container_layout.addWidget(checkbox)
        
        # Add stretch at the end to push all chapters to the top with empty space below
        container_layout.addStretch(1)
        
        # Add the container to the scroll area
        self.scroll_layout.addWidget(container)
    

    
    def on_language_changed(self, index):
        language_code = self.language_combo.itemData(index)
        self.load_chapters(language_code)
    
    def select_all(self):
        for checkbox in self.chapter_checkboxes:
            checkbox.setChecked(True)
    
    def get_selected_chapters(self):
        selected = []
        for checkbox in self.chapter_checkboxes:
            if checkbox.isChecked():
                chapter_id = checkbox.property("chapter_id")
                chapter_data = checkbox.property("chapter_data")
                selected.append((chapter_id, chapter_data))
        return selected
    
    def get_selected_language(self):
        return self.language_combo.itemData(self.language_combo.currentIndex())


class DownloadThread(QThread):
    progress_updated = pyqtSignal(int, int)  # current, total
    chapter_updated = pyqtSignal(int, int)   # current chapter, total chapters
    download_finished = pyqtSignal(list)     # list of downloaded paths
    
    def __init__(self, api, chapter_data_list, manga_title, download_dir, as_pdf):
        super().__init__()
        self.api = api
        self.chapter_data_list = chapter_data_list
        self.manga_title = manga_title
        self.download_dir = download_dir
        self.as_pdf = as_pdf
        self.api_connected = False
    
    def run(self):
        # Connect signals in the same thread
        if not self.api_connected:
            self.api.download_progress.connect(self.on_download_progress)
            self.api_connected = True
            
        downloaded_paths = []
        for i, (chapter_id, chapter_data) in enumerate(self.chapter_data_list):
            path = self.api.download_chapter(chapter_id, self.manga_title, self.download_dir, chapter_data, self.as_pdf)
            if path:
                downloaded_paths.append(path)
            
            # Update chapter progress
            self.chapter_updated.emit(i + 1, len(self.chapter_data_list), self.manga_title)
        
        self.download_finished.emit(downloaded_paths)
    
    def on_download_progress(self, current, total, manga_title, chapter_title):
        self.progress_updated.emit(current, total, manga_title, chapter_title)


class ImageDownloadDialog(QDialog):
    def __init__(self, parent=None, total_chapters=1):
        super().__init__(parent)
        self.setWindowTitle("Downloading...")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        
        # Chapter progress
        self.chapter_label = QLabel("Chapter progress:")
        layout.addWidget(self.chapter_label)
        
        self.chapter_progress_bar = QProgressBar()
        self.chapter_progress_bar.setMaximum(total_chapters)
        self.chapter_progress_bar.setValue(0)
        layout.addWidget(self.chapter_progress_bar)
        
        # Image progress
        self.image_label = QLabel("Downloading images...")
        layout.addWidget(self.image_label)
        
        self.image_progress_bar = QProgressBar()
        layout.addWidget(self.image_progress_bar)
        
        self.setLayout(layout)
    
    def update_progress(self, current, total):
        self.image_progress_bar.setMaximum(total)
        self.image_progress_bar.setValue(current)
        self.image_label.setText(f"Downloading images... {current}/{total}")
    
    def update_chapter_progress(self, current, total):
        self.chapter_progress_bar.setMaximum(total)
        self.chapter_progress_bar.setValue(current)
        self.chapter_label.setText(f"Chapter progress: {current}/{total}")


class MangadexGUI(QWidget):
    def __init__(self, api, settings):
        super().__init__()
        self.api = api
        self.settings = settings
        self.download_dir = settings.get("download_dir")
        self.search_results = []
        self.current_manga = None
        self.download_thread = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Mangadex Downloader")
        self.setMinimumSize(800, 600)
        
        main_layout = QVBoxLayout()
        
        # Segment 1: Search and options
        search_segment = QWidget()
        search_layout = QVBoxLayout(search_segment)
        
        # Search bar
        search_bar_layout = QHBoxLayout()
        search_bar_layout.addWidget(QLabel("Search Manga:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter manga title...")
        search_bar_layout.addWidget(self.search_input, 1)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_manga)
        search_bar_layout.addWidget(self.search_button)
        
        search_layout.addLayout(search_bar_layout)
        
        # Download options
        options_layout = QHBoxLayout()
        
        # Directory selection
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Download Directory:"))
        
        self.dir_label = QLabel(self.download_dir)
        dir_layout.addWidget(self.dir_label, 1)
        
        self.dir_button = QPushButton("Browse")
        self.dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_button)
        
        options_layout.addLayout(dir_layout)
        
        # Download type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Download as:"))
        
        self.download_type = QButtonGroup()
        
        self.pdf_radio = QRadioButton("PDF")
        self.pdf_radio.setChecked(self.settings.get("download_as_pdf", True))
        self.download_type.addButton(self.pdf_radio)
        type_layout.addWidget(self.pdf_radio)
        
        self.images_radio = QRadioButton("Images")
        self.images_radio.setChecked(not self.settings.get("download_as_pdf", True))
        self.download_type.addButton(self.images_radio)
        type_layout.addWidget(self.images_radio)
        
        options_layout.addLayout(type_layout)
        
        search_layout.addLayout(options_layout)
        main_layout.addWidget(search_segment)
        
        # Segment 2: Search results
        results_label = QLabel("Search Results:")
        main_layout.addWidget(results_label)
        
        self.results_area = QScrollArea()
        self.results_area.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_area.setWidget(self.results_widget)
        
        main_layout.addWidget(self.results_area, 1)
        
        # Download progress bar
        progress_layout = QVBoxLayout()
        
        # Single progress label with all information
        self.progress_label = QLabel("Ready")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setVisible(False)
        
        progress_layout.addWidget(self.progress_label)
        
        self.chapter_progress_bar = QProgressBar()
        self.chapter_progress_bar.setVisible(False)
        progress_layout.addWidget(self.chapter_progress_bar)
        
        main_layout.addLayout(progress_layout)
        
        self.setLayout(main_layout)
        
        # Progress dialog for individual chapter download
        self.progress_dialog = None
    
    def search_manga(self):
        query = self.search_input.text().strip()
        if not query:
            return
        
        # Clear previous results
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Show loading message
        loading_label = QLabel("Searching...")
        loading_label.setAlignment(Qt.AlignCenter)
        self.results_layout.addWidget(loading_label)
        
        # Create signal emitter for thread communication
        class SignalEmitter(QObject):
            search_complete = pyqtSignal(object)
        
        signal_emitter = SignalEmitter()
        signal_emitter.search_complete.connect(self.display_search_results)
        
        # Run search in a separate thread
        def search_thread(query, emitter):
            results = self.api.search_manga(query)
            emitter.search_complete.emit(results)
        
        # Start the search thread
        threading.Thread(target=search_thread, args=(query, signal_emitter), daemon=True).start()
    
    def display_search_results(self, results):
        # Clear loading message
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.search_results = results.get("data", [])
        
        if not self.search_results:
            no_results = QLabel("No results found.")
            no_results.setAlignment(Qt.AlignCenter)
            self.results_layout.addWidget(no_results)
            return
        
        # Display results
        for manga in self.search_results:
            card = MangaCard(manga)
            card.download_clicked.connect(self.show_chapter_selection)
            self.results_layout.addWidget(card)
            
            # Add spacing between cards
            self.results_layout.addSpacing(10)
            
        # Add stretch at the end to push all results to the top
        self.results_layout.addStretch(1)
    
    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.download_dir)
        if dir_path:
            self.download_dir = dir_path
            self.dir_label.setText(dir_path)
            # Save to settings
            self.settings.set("download_dir", dir_path)
    
    def show_chapter_selection(self, manga_data):
        self.current_manga = manga_data
        manga_id = manga_data.get("id")
        manga_title = manga_data.get("attributes", {}).get("title", {}).get("en", "Unknown Manga")
        
        # Get preferred language from settings
        preferred_language = self.settings.get("preferred_language", "en")
        
        try:
            # Get already downloaded and incomplete chapters
            downloaded_chapters, incomplete_chapters = self.api.get_downloaded_chapters(
                manga_title, self.download_dir, manga_id
            )
        except Exception as e:
            print(f"Error getting downloaded chapters: {e}")
            downloaded_chapters, incomplete_chapters = [], []
        
        dialog = ChapterSelectionDialog(
            self.api, manga_id, preferred_language, self, 
            downloaded_chapters, incomplete_chapters
        )
        if dialog.exec_():
            selected_chapters = dialog.get_selected_chapters()
            if selected_chapters:
                # Save selected language to settings
                selected_language = dialog.get_selected_language()
                self.settings.set("preferred_language", selected_language)
                
                # Save download type preference
                self.settings.set("download_as_pdf", self.pdf_radio.isChecked())
                
                self.download_chapters(selected_chapters)
    
    def download_chapters(self, chapter_data_list):
        if not chapter_data_list:
            return
            
        # Get manga title
        manga_title = self.current_manga.get("attributes", {}).get("title", {}).get("en", "Unknown Manga")
        
        # Setup progress bar
        self.chapter_progress_bar.setMaximum(len(chapter_data_list))
        self.chapter_progress_bar.setValue(0)
        self.progress_label.setText(f"Chapter 0/{len(chapter_data_list)}             {manga_title}             Images 0/0")
        self.progress_label.setVisible(True)
        self.chapter_progress_bar.setVisible(True)
        
        # Create and start download thread
        self.download_thread = DownloadThread(
            self.api, 
            chapter_data_list, 
            manga_title, 
            self.download_dir, 
            self.pdf_radio.isChecked()
        )
        
        # Connect signals
        self.download_thread.progress_updated.connect(self.update_download_progress)
        self.download_thread.chapter_updated.connect(self.update_chapter_progress)
        self.download_thread.download_finished.connect(self.download_complete)
        
        # Start download
        self.download_thread.start()
    
    def update_download_progress(self, current, total, manga_title, chapter_title):
        # Get current chapter progress
        chapter_current = self.chapter_progress_bar.value()
        chapter_total = self.chapter_progress_bar.maximum()
        
        # Update the progress label with all information
        self.progress_label.setText(f"Chapter {chapter_current}/{chapter_total}             {manga_title}             Images {current}/{total}")
    
    def update_chapter_progress(self, current, total, manga_title):
        self.chapter_progress_bar.setMaximum(total)
        self.chapter_progress_bar.setValue(current)
        self.progress_label.setText(f"Chapter {current}/{total}             {manga_title}             Images 0/0")
    
    def download_complete(self, downloaded_paths):
        # Show completion message
        manga_dir = os.path.join(self.download_dir, self.api._sanitize_filename(
            self.current_manga.get("attributes", {}).get("title", {}).get("en", "Unknown Manga")
        ))
        QMessageBox.information(self, "Download Complete", 
                               f"All {len(downloaded_paths)} chapters downloaded to:\n{manga_dir}")
        
        # Update progress bar text
        self.progress_label.setText("Download complete!")