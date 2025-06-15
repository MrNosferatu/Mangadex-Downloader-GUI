import requests
import os
import json
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from PyQt5.QtCore import QObject, pyqtSignal

class MangadexAPI(QObject):
    download_progress = pyqtSignal(int, int, str, str)  # current, total, manga_title, chapter_title
    chapter_progress = pyqtSignal(int, int, str)   # current chapter, total chapters, manga_title
    download_complete = pyqtSignal(str)  # path
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.mangadex.org"
        self.session = self._create_session()
        
    def search_manga(self, title, limit=20, offset=0, content_ratings=None):
        """Search for manga by title"""
        url = f"{self.base_url}/manga"
        params = {
            "title": title,
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art", "author", "artist", "tag"],
        }
        
        # Add content ratings if provided
        if content_ratings:
            params["contentRating[]"] = content_ratings
        
        response = self._request_with_retry("GET", url, params=params)
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
            "order[chapter]": "asc",
        }
        
        response = self._request_with_retry("GET", url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"data": []}
            
    def get_downloaded_chapters(self, manga_title, output_dir, manga_id=None):
        """Get a list of already downloaded chapters for a manga"""
        downloaded_chapters = []
        incomplete_chapters = []
        
        # Get manga directory path
        manga_dir = os.path.normpath(os.path.join(output_dir, self._sanitize_filename(manga_title)))
        
        if not os.path.exists(manga_dir):
            return downloaded_chapters, incomplete_chapters
        
        # Get chapter data from API if manga_id is provided
        chapter_data_map = {}
        if manga_id:
            try:
                chapters = self.get_manga_chapters(manga_id)
                for chapter in chapters.get("data", []):
                    chapter_attrs = chapter.get("attributes", {})
                    chapter_num = chapter_attrs.get("chapter", "Unknown")
                    chapter_id = chapter.get("id")
                    chapter_data_map[chapter_num] = chapter_id
            except Exception as e:
                print(f"Error getting chapter data from API: {e}")
            
        # Check for chapter directories and PDFs
        for item in os.listdir(manga_dir):
            item_path = os.path.join(manga_dir, item)
            
            # Check if it's a chapter directory with images
            if os.path.isdir(item_path) and item.startswith("Chapter "):
                if os.listdir(item_path):  # Has files
                    chapter_num = item.split(" - ")[0].replace("Chapter ", "").strip()
                    
                    # Check if chapter is complete
                    is_complete = True
                    if chapter_num in chapter_data_map:
                        chapter_id = chapter_data_map[chapter_num]
                        try:
                            url = f"{self.base_url}/at-home/server/{chapter_id}"
                            response = self._request_with_retry("GET", url)
                            
                            if response.status_code == 200:
                                chapter_data = response.json()
                                expected_images = chapter_data["chapter"]["data"]
                                total_expected = len(expected_images)
                                
                                # Check if all expected images are downloaded
                                existing_files = os.listdir(item_path)
                                is_complete = len(existing_files) >= total_expected
                        except Exception:
                            # If API check fails, assume it's complete if it has files
                            is_complete = len(os.listdir(item_path)) > 0
                    
                    if is_complete:
                        downloaded_chapters.append(chapter_num)
                    else:
                        incomplete_chapters.append(chapter_num)
            
            # Check if it's a PDF file
            elif os.path.isfile(item_path) and item.endswith(".pdf") and item.startswith("Chapter "):
                chapter_num = item.split(" - ")[0].replace("Chapter ", "").strip()
                downloaded_chapters.append(chapter_num)
                
        return downloaded_chapters, incomplete_chapters
    
    def get_manga_details(self, manga_id):
        """Get manga details"""
        url = f"{self.base_url}/manga/{manga_id}"
        params = {
            "includes[]": ["cover_art", "author", "artist", "tag"]
        }
        
        response = self._request_with_retry("GET", url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"data": {}}
            
    def is_chapter_downloaded(self, chapter_id, manga_title, chapter_num, chapter_title, output_dir, as_pdf=False):
        """Check if a chapter has already been downloaded completely"""
        # Format chapter folder name
        chapter_folder_name = f"Chapter {chapter_num} - {chapter_title}" if chapter_title else f"Chapter {chapter_num}"
        chapter_folder_name = self._sanitize_filename(chapter_folder_name)
        
        # Get manga directory path
        manga_dir = os.path.normpath(os.path.join(output_dir, self._sanitize_filename(manga_title)))
        
        if as_pdf:
            # Check if PDF exists
            pdf_path = os.path.normpath(os.path.join(manga_dir, f"{chapter_folder_name}.pdf"))
            return os.path.exists(pdf_path)
        else:
            # Check if chapter directory exists
            chapter_dir = os.path.normpath(os.path.join(manga_dir, chapter_folder_name))
            if not os.path.exists(chapter_dir):
                return False
            
            # Get expected image count from API
            try:
                url = f"{self.base_url}/at-home/server/{chapter_id}"
                response = self._request_with_retry("GET", url)
                
                if response.status_code != 200:
                    # If API fails, just check if directory has any files
                    files = os.listdir(chapter_dir)
                    return len(files) > 0
                
                chapter_data = response.json()
                expected_images = chapter_data["chapter"]["data"]
                total_expected = len(expected_images)
                
                # Check if all expected images are downloaded
                existing_files = os.listdir(chapter_dir)
                return len(existing_files) >= total_expected
                
            except Exception as e:
                print(f"Error checking chapter completeness: {e}")
                # If there's an error, just check if directory has any files
                files = os.listdir(chapter_dir)
                return len(files) > 0
    
    def download_chapter(self, chapter_id, manga_title, output_dir, chapter_data=None, as_pdf=False):
        """Download a chapter"""
        # Get chapter data if not provided
        if not chapter_data:
            url = f"{self.base_url}/chapter/{chapter_id}"
            response = self._request_with_retry("GET", url)
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
        
        # Create manga directory - normalize path to use consistent slashes
        manga_dir = os.path.normpath(os.path.join(output_dir, self._sanitize_filename(manga_title)))
        os.makedirs(manga_dir, exist_ok=True)
        
        # Create chapter directory - normalize path to use consistent slashes
        chapter_dir = os.path.normpath(os.path.join(manga_dir, chapter_folder_name))
        
        # Check if chapter already exists as PDF
        if as_pdf:
            pdf_path = os.path.normpath(os.path.join(manga_dir, f"{chapter_folder_name}.pdf"))
            if os.path.exists(pdf_path):
                print(f"Chapter already downloaded as PDF: {chapter_folder_name}")
                return pdf_path
        
        # Get chapter images from API first to check completeness
        url = f"{self.base_url}/at-home/server/{chapter_id}"
        response = self._request_with_retry("GET", url)
        
        if response.status_code != 200:
            return False
        
        chapter_data = response.json()
        base_url = chapter_data["baseUrl"]
        chapter_hash = chapter_data["chapter"]["hash"]
        expected_images = chapter_data["chapter"]["data"]
        total_expected = len(expected_images)
        
        # Check if chapter directory exists with images
        if os.path.exists(chapter_dir) and os.listdir(chapter_dir):
            # Check if all expected images are downloaded
            existing_files = os.listdir(chapter_dir)
            
            # If all images are downloaded
            if len(existing_files) >= total_expected:
                print(f"Chapter already downloaded: {chapter_folder_name}")
                
                # If PDF conversion is requested but we have images, convert them
                if as_pdf:
                    try:
                        from PIL import Image
                        pdf_path = os.path.normpath(os.path.join(manga_dir, f"{chapter_folder_name}.pdf"))
                        
                        # Get all image files in the directory
                        image_files = [os.path.join(chapter_dir, f) for f in os.listdir(chapter_dir) 
                                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                        image_files.sort()  # Sort to ensure correct order
                        
                        if image_files:
                            images = [Image.open(img_path) for img_path in image_files]
                            images[0].save(
                                pdf_path, "PDF", resolution=100.0, 
                                save_all=True, append_images=images[1:]
                            )
                            
                            # Remove the image files after PDF creation
                            for img_path in image_files:
                                os.remove(img_path)
                            os.rmdir(chapter_dir)
                            
                            return pdf_path
                    except Exception as e:
                        print(f"Error creating PDF from existing images: {e}")
                        return chapter_dir
                
                return chapter_dir
            else:
                print(f"Chapter {chapter_folder_name} is incomplete. Resuming download...")
                # Continue with download to get missing images
        
        # Create chapter directory if it doesn't exist
        os.makedirs(chapter_dir, exist_ok=True)
        
        # We already have chapter data from the earlier check
        if not 'base_url' in locals() or not 'expected_images' in locals():
            # Get chapter images
            url = f"{self.base_url}/at-home/server/{chapter_id}"
            response = self._request_with_retry("GET", url)
            
            if response.status_code != 200:
                return False
            
            chapter_data = response.json()
            base_url = chapter_data["baseUrl"]
            chapter_hash = chapter_data["chapter"]["hash"]
            expected_images = chapter_data["chapter"]["data"]
        
        # Use the data we already have
        data = expected_images
        
        # Download images
        total_images = len(data)
        downloaded_images = []
        
        for i, image in enumerate(data):
            image_url = f"{base_url}/data/{chapter_hash}/{image}"
            image_path = os.path.normpath(os.path.join(chapter_dir, image))
            
            # Skip if image already exists
            if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                downloaded_images.append(image_path)
                self.download_progress.emit(i + 1, total_images, manga_title, f"Chapter {chapter_num}")
                continue
                
            downloaded_images.append(image_path)
            
            response = self._request_with_retry("GET", image_url)
            if response.status_code == 200:
                with open(image_path, "wb") as f:
                    f.write(response.content)
                self.download_progress.emit(i + 1, total_images, manga_title, f"Chapter {chapter_num}")
            
        # Convert to PDF if requested
        if as_pdf and downloaded_images:
            try:
                from PIL import Image
                pdf_path = os.path.normpath(os.path.join(manga_dir, f"{chapter_folder_name}.pdf"))
                
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
        
        # Windows doesn't allow filenames ending with dots or spaces
        filename = filename.rstrip('. ')
        
        # Ensure filename isn't too long for Windows
        if len(filename) > 240:
            filename = filename[:240]
            
        return filename
        
    def _create_session(self):
        """Create a requests session with retry functionality"""
        session = requests.Session()
        retry_strategy = Retry(
            total=5,  # Total number of retries
            backoff_factor=1,  # Time between retries: {backoff factor} * (2 ** ({number of total retries} - 1))
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
            allowed_methods=["GET", "POST"]  # HTTP methods to retry on
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
        
    def _request_with_retry(self, method, url, **kwargs):
        """Make a request with retry functionality"""
        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"Connection error: {e}. Retrying...")
            # If all retries failed, try one more time with a longer timeout
            time.sleep(2)
            kwargs['timeout'] = 30  # Longer timeout for the final attempt
            return self.session.request(method, url, **kwargs)