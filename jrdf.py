import sys
from pathlib import Path
import mimetypes
import argparse
from guessit import guessit


def parse_args():
    parser = argparse.ArgumentParser(
        prog="jrdf",
        description="Just Rename the Damn Files"
    )
    parser.add_argument("paths", nargs="+", help="File or directory to rename")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-M", "--movie", action="store_true", help="Movie mode (rename largest video file only)")
    mode.add_argument("-T", "--tv", action="store_true", help="TV mode (rename all video files)")
    return parser.parse_args()

def is_video(file: Path) -> bool:
    mime = mimetypes.guess_type(file)[0]
    return mime is not None and "video" in mime

def rename_directory_if_possible(directory: Path):
    info = guessit(directory.name)
    raw_title = info.get("title")
    title = raw_title[0] if isinstance(raw_title, list) else raw_title
    year = info.get("year")
    if title and year:
        new_name = f"{title} ({year})"
        if directory.name == new_name:
            return
        new_path = directory.parent / new_name
        if new_path.exists():
            print(f"⚠️  {new_path} esiste già, salto {directory}")
            return
        try:
            directory.rename(new_path)
            print(f"📁 {directory.name} → {new_name}")
        except OSError as e:
            print(f"{directory} => {e}")

def rename_season_folder_from_files(season_dir: Path):
    if not season_dir.is_dir():
        return

    video = next((v for v in season_dir.rglob("*") if v.is_file() and is_video(v)), None)
    if video is None:
        return

    season = guessit(str(video)).get("season")
    if season is None:
        return

    new_name = f"Season {int(season):02d}"
    if season_dir.name == new_name:
        return

    new_path = season_dir.parent / new_name
    if new_path.exists():
        print(f"⚠️  {new_path} already exists, skipping {season_dir}")
        return

    try:
        season_dir.rename(new_path)
        print(f"📁 {season_dir.name} → {new_name}")
    except OSError as e:
        print(f"{season_dir} => {e}")

def change_file(file: Path):
    info = guessit(str(file))

    media_type = info.get("type")

    raw_title = info.get("title")
    title = raw_title[0] if isinstance(raw_title, list) else raw_title

    if media_type == "episode":
        season = info.get("season")
        if season is not None and int(season) == 0:
            return
        episodes = info.get("episode")
        if season is None or episodes is None:
            return

        if isinstance(episodes, list):
            if len(episodes) == 1:
                ep_part = f"E{int(episodes[0]):02d}"
            else:
                ep_part = f"E{int(episodes[0]):02d}-E{int(episodes[-1]):02d}"
        else:
            ep_part = f"E{int(episodes):02d}"

        season_num = int(season)
        new_name = f"{title} - S{season_num:02d}{ep_part}{file.suffix}"

    elif media_type == "movie":
        year = info.get("year")
        if not title or not year:
            return
        new_name = f"{title} ({year}){file.suffix}"

    else:
        return

    if file.name == new_name:
        return

    new_path = file.with_name(new_name)
    if new_path.exists():
        print(f"⚠️  {new_path} esiste già, salto {file.name}")
        return

    try:
        file.rename(new_path)
        print(f"🎞️ {file.name} → {new_name}")
    except OSError as e:
        print(f"{file} => {e}")

def change_dir_movie(directory: Path):
    videos = [f for f in directory.iterdir()
              if f.is_file() and is_video(f) and "sample" not in f.name.lower()]
    if not videos:
        return

    main_video = max(videos, key=lambda f: f.stat().st_size)
    change_file(main_video)

    rename_directory_if_possible(directory)

def change_dir_tv(directory: Path):
    for sub in list(directory.iterdir()):
        rename_season_folder_from_files(sub)

    for video in directory.rglob("*"):
        if video.is_file() and is_video(video):
            change_file(video)

    rename_directory_if_possible(directory)


def main():
    args = parse_args()
    for path_str in args.paths:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            print(f"{path} not found")
            continue

        if path.is_file():
            print(f"Processing file: {path}")
            change_file(path)
        elif path.is_dir():
            print(f"Processing directory: {path}")
            if args.movie:
                change_dir_movie(path)
            elif args.tv:
                change_dir_tv(path)


if __name__ == "__main__":
    main()
