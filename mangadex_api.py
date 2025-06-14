import requests
import os
import json
from PyQt5.QtCore import QObject, pyqtSignal

class MangadexAPI(QObject):
    download_progress = pyqtSignal(int, int)  # current, total
    chapter_progress = pyqtSignal(int, int)   # current chapter, total chapters
    download_complete = pyqtSignal(str)  # path
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.mangadex.org"
        
    def search_manga(self, title, limit=20, offset=0):
        """Search for manga by title"""
        url = f"{self.base_url}/manga"
        params = {
            "title": title,
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art", "author", "artist", "tag"]
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"data": []}
    
    def get_manga_chapters(self, manga_id, language="en"):
        """Get chapters for a manga"""
        url = f"{self.base_url}/manga/{manga_id}/feed"
        params = {
            "translatedLanguage[]": [language],
            "limit": 100,
            "order[chapter]": "asc"
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"data": []}
    
    def get_manga_details(self, manga_id):
        """Get manga details"""
        url = f"{self.base_url}/manga/{manga_id}"
        params = {
            "includes[]": ["cover_art", "author", "artist", "tag"]
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"data": {}}
            
    def download_chapter(self, chapter_id, manga_title, output_dir, chapter_data=None, as_pdf=False):
        """Download a chapter"""
        # Get chapter data if not provided
        if not chapter_data:
            url = f"{self.base_url}/chapter/{chapter_id}"
            response = requests.get(url)
            if response.status_code == 200:
                chapter_data = response.json()["data"]
            else:
                return False
        
        # Get chapter info
        chapter_attrs = chapter_data.get("attributes", {})
        chapter_num = chapter_attrs.get("chapter", "Unknown")
        chapter_title = chapter_attrs.get("title", f"Chapter {chapter_num}")
        chapter_folder_name = f"Chapter {chapter_num} - {chapter_title}" if chapter_title else f"Chapter {chapter_num}"
        chapter_folder_name = self._sanitize_filename(chapter_folder_name)
        
        # Create manga directory
        manga_dir = os.path.join(output_dir, self._sanitize_filename(manga_title))
        os.makedirs(manga_dir, exist_ok=True)
        
        # Create chapter directory
        chapter_dir = os.path.join(manga_dir, chapter_folder_name)
        os.makedirs(chapter_dir, exist_ok=True)
        
        # Get chapter images
        url = f"{self.base_url}/at-home/server/{chapter_id}"
        response = requests.get(url)
        
        if response.status_code != 200:
            return False
        
        chapter_data = response.json()
        base_url = chapter_data["baseUrl"]
        chapter_hash = chapter_data["chapter"]["hash"]
        data = chapter_data["chapter"]["data"]
        
        # Download images
        total_images = len(data)
        downloaded_images = []
        
        for i, image in enumerate(data):
            image_url = f"{base_url}/data/{chapter_hash}/{image}"
            image_path = os.path.join(chapter_dir, image)
            downloaded_images.append(image_path)
            
            response = requests.get(image_url)
            if response.status_code == 200:
                with open(image_path, "wb") as f:
                    f.write(response.content)
                self.download_progress.emit(i + 1, total_images)
            
        # Convert to PDF if requested
        if as_pdf and downloaded_images:
            try:
                from PIL import Image
                pdf_path = os.path.join(manga_dir, f"{chapter_folder_name}.pdf")
                
                images = [Image.open(img_path) for img_path in downloaded_images]
                if images:
                    images[0].save(
                        pdf_path, "PDF", resolution=100.0, 
                        save_all=True, append_images=images[1:]
                    )
                    
                    # Remove the image files after PDF creation
                    for img_path in downloaded_images:
                        os.remove(img_path)
                    os.rmdir(chapter_dir)
                    
                    return pdf_path
            except Exception as e:
                print(f"Error creating PDF: {e}")
                return chapter_dir
        
        return chapter_dir
        
    def _sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename