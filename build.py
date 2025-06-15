import os
import subprocess
import shutil

def build_executable():
    print("Building Mangadex Downloader GUI executable...")
    
    # Clean any previous build artifacts
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # Build the executable with PyInstaller
    cmd = [
        "pyinstaller",
        "--name=MangadexDownloader",
        "--windowed",  # No console window
        "--onefile",   # Single executable file
        "--icon=NONE", # Replace with path to your icon if you have one
        "--add-data=settings.json;.",  # Include settings.json
        "main.py"
    ]
    
    subprocess.run(cmd)
    
    print("\nBuild complete! Executable is in the 'dist' folder.")
    print("You can run 'MangadexDownloader.exe' from there.")

if __name__ == "__main__":
    build_executable()