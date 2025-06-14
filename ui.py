from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QRadioButton, QFileDialog, QScrollArea, 
                             QButtonGroup, QDialog, QCheckBox, QProgressBar, QMessageBox,
                             QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, QObject
from PyQt5.QtGui import QPixmap, QImage
import requests
from io import BytesIO
import os
import threading

class MangaCard(QWidget):
    download_clicked = pyqtSignal(dict)
    
    def __init__(self, manga_data):
        super().__init__()
        self.manga_data = manga_data
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout()
        
        # Cover image
        cover_layout = QVBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150, 200)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("background-color: #f0f0f0;")
        
        # Find cover art
        cover_file = None
        for relationship in self.manga_data.get("relationships", []):
            if relationship.get("type") == "cover_art":
                cover_file = relationship.get("attributes", {}).get("fileName")
                break
        
        if cover_file:
            manga_id = self.manga_data.get("id")
            cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_file}"
            
            try:
                response = requests.get(cover_url)
                if response.status_code == 200:
                    img = QImage()
                    img.loadFromData(response.content)
                    pixmap = QPixmap.fromImage(img)
                    self.cover_label.setPixmap(pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception as e:
                print(f"Error loading cover: {e}")
        
        cover_layout.addWidget(self.cover_label)
        layout.addLayout(cover_layout)
        
        # Info layout
        info_layout = QVBoxLayout()
        
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
        
        # Download button
        download_btn = QPushButton("Download")
        download_btn.clicked.connect(self.on_download_clicked)
        info_layout.addWidget(download_btn)
        
        layout.addLayout(info_layout, 1)
        self.setLayout(layout)
        
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
    def __init__(self, api, manga_id, preferred_language="en", parent=None):
        super().__init__(parent)
        self.api = api
        self.manga_id = manga_id
        self.preferred_language = preferred_language
        self.chapters = {"data": []}
        self.selected_chapters = []
        self.init_ui()
        self.load_chapters(preferred_language)
        
    def init_ui(self):
        self.setWindowTitle("Select Chapters to Download")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Language selection
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English (en)", "Japanese (ja)", "Spanish (es)", "French (fr)", "German (de)"])
        
        # Set default language
        index = 0
        for i in range(self.language_combo.count()):
            if self.preferred_language in self.language_combo.itemText(i):
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
        
        layout.addWidget(self.scroll_area)
        
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
    
    def load_chapters(self, language):
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
        
        # Get language code from combo box text
        lang_code = language
        if "(" in language and ")" in language:
            lang_code = language.split("(")[1].split(")")[0]
        
        # Create signal emitter in the main thread
        from PyQt5.QtCore import QObject, pyqtSignal
        
        class SignalEmitter(QObject):
            update_signal = pyqtSignal(object)
        
        signal_emitter = SignalEmitter()
        signal_emitter.update_signal.connect(self.update_chapters_ui)
        
        # Load chapters in a separate thread to keep UI responsive
        def fetch_chapters(emitter):
            chapters = self.api.get_manga_chapters(self.manga_id, lang_code)
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
        
        for chapter in self.chapters.get("data", []):
            chapter_attrs = chapter.get("attributes", {})
            chapter_num = chapter_attrs.get("chapter", "Unknown")
            chapter_title = chapter_attrs.get("title", f"Chapter {chapter_num}")
            
            checkbox = QCheckBox(f"Chapter {chapter_num}: {chapter_title}")
            checkbox.setProperty("chapter_id", chapter.get("id"))
            checkbox.setProperty("chapter_data", chapter)
            self.chapter_checkboxes.append(checkbox)
            self.scroll_layout.addWidget(checkbox)
    

    
    def on_language_changed(self, index):
        language = self.language_combo.currentText()
        self.load_chapters(language)
    
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
        language = self.language_combo.currentText()
        if "(" in language and ")" in language:
            return language.split("(")[1].split(")")[0]
        return language


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
            self.chapter_updated.emit(i + 1, len(self.chapter_data_list))
        
        self.download_finished.emit(downloaded_paths)
    
    def on_download_progress(self, current, total):
        self.progress_updated.emit(current, total)


class ImageDownloadDialog(QDialog):
    def __init__(self, total_chapters=1, parent=None):
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
        
        self.chapter_progress_label = QLabel("Download Progress:")
        self.chapter_progress_label.setVisible(False)
        progress_layout.addWidget(self.chapter_progress_label)
        
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
        
        # Search manga
        results = self.api.search_manga(query)
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
        
        # Get preferred language from settings
        preferred_language = self.settings.get("preferred_language", "en")
        
        dialog = ChapterSelectionDialog(self.api, manga_id, preferred_language, self)
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
        self.chapter_progress_label.setText(f"Downloading chapters: 0/{len(chapter_data_list)}")
        self.chapter_progress_label.setVisible(True)
        self.chapter_progress_bar.setVisible(True)
        
        # Create progress dialog for individual chapter
        self.progress_dialog = ImageDownloadDialog(self)
        self.progress_dialog.show()
        
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
    
    def update_download_progress(self, current, total):
        if self.progress_dialog:
            self.progress_dialog.update_progress(current, total)
    
    def update_chapter_progress(self, current, total):
        self.chapter_progress_bar.setMaximum(total)
        self.chapter_progress_bar.setValue(current)
        self.chapter_progress_label.setText(f"Downloading chapters: {current}/{total}")
    
    def download_complete(self, downloaded_paths):
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        # Show completion message
        manga_dir = os.path.join(self.download_dir, self.api._sanitize_filename(
            self.current_manga.get("attributes", {}).get("title", {}).get("en", "Unknown Manga")
        ))
        QMessageBox.information(self, "Download Complete", 
                               f"All {len(downloaded_paths)} chapters downloaded to:\n{manga_dir}")
        
        # Update progress bar text
        self.chapter_progress_label.setText("Download complete!")