# Mangadex GUI

A simple PyQt application for searching and downloading manga from MangaDex.

## Features

- Search for manga by title
- View manga information including cover, title, tags, and description
- Download chapters as PDF or image files
- Select multiple chapters to download

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