import gzip
import shutil
import urllib.request
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

URL = "https://snap.stanford.edu/data/wiki-Vote.txt.gz"

ARCHIVE_PATH = DATA_DIR / "wiki-Vote.txt.gz"
OUTPUT_PATH = DATA_DIR / "wiki-Vote.txt"


def download_file():
    DATA_DIR.mkdir(exist_ok=True)

    if OUTPUT_PATH.exists():
        print(f"Dataset already exists: {OUTPUT_PATH}")
        return

    print("Downloading Wiki-Vote dataset...")

    urllib.request.urlretrieve(URL, ARCHIVE_PATH)

    print("Download complete.")

    print("Extracting dataset...")

    with gzip.open(ARCHIVE_PATH, "rb") as source:
        with open(OUTPUT_PATH, "wb") as destination:
            shutil.copyfileobj(source, destination)

    print(f"Extracted dataset to: {OUTPUT_PATH}")

    ARCHIVE_PATH.unlink()

    print("Temporary archive removed.")


if __name__ == "__main__":
    download_file()