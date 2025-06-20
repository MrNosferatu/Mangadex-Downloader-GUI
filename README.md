# Mangadex Downloader GUI

A simple PyQt application for searching and downloading manga from MangaDex with a responsive user interface.

## Features

- Search for manga by title with responsive UI
- View manga information including cover, title, tags, and description
- Download chapters as PDF or image files
- Select multiple chapters to download
- Background processing for improved performance
- Consistent UI layout with proper spacing
- Resume incomplete downloads

## Installation

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the application:
```
python main.py
```
Or run using the bat file
```
run.bat
```

## Functionality

1. Enter a manga title in the search box and click "Search"
2. Browse the search results
3. Click "Download" on a manga card to select chapters
4. Choose which chapters to download
5. Click "Download" to start downloading

## Requirements

- Python 3.6+
- PyQt5
- Requests
- Pillow (for PDF conversion)

## Performance Improvements

- Manga searches run in background threads to keep UI responsive
- Cover images load asynchronously
- Chapter lists maintain consistent spacing regardless of chapter count
- Search results are displayed with consistent card sizes

## UI Features

- Dark mode interface with MangaDex-inspired color scheme:
  - Background: #191a1c
  - Cards: #2c2c2c
  - Dropdowns: #4f4f4f
  - Buttons: #c45236
- High contrast white text for better readability
- Consistent styling across all dialogs and components