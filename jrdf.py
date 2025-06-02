import sys
from pathlib import Path
import mimetypes
from guessit import guessit

def is_video(file: Path) -> bool:
    mime = mimetypes.guess_type(file)[0]
    return mime is not None and "video" in mime

def change_file(file: Path):
    info = guessit(str(file))
    title = info.get("title")
    year = info.get("year")
    if not title or not year:
        return

    new_name = f"{title} ({year}){file.suffix}"
    if file.name == new_name:
        return
    new_path = file.with_name(new_name)
    if not new_path.exists():
        try:
            file.rename(new_path)
        except OSError as e:
            printf(f"{file} => {e}")

def change_dir(directory: Path):
    for f in directory.iterdir():
        if f.is_file() and is_video(f):
            change_file(f)

    info = guessit(directory.name)
    title = info.get("title")
    year = info.get("year")

    if title and year:
        new_name = f"{title} ({year})"
        if directory.name == new_name:
            return
        new_path = directory.parent / new_name
        if not new_path.exists():
            try:
                directory.rename(new_path)
            except OSError as e:
                print(f"{directory} => {e}")

def main():
    if len(sys.argv) == 1:
        printf("Usage: rename_to_jellyfin.py <file_or_dir> [...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"{path} not found")
            continue
        elif path.is_dir():
            print(f"Processing directory: {path}")
            change_dir(path)
        elif path.is_file():
            print(f"Processing file: {path}")
            change_file(path)

if __name__ == "__main__":
    main()

