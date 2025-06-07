#!/usr/bin/env python3
import sys
from pathlib import Path
import mimetypes
import argparse
from guessit import guessit

def is_video(file: Path) -> bool:
    mime = mimetypes.guess_type(file)[0]
    return mime is not None and "video" in mime

def _rename(src: Path, dst: Path, icon: str, dry_run: bool):
    """Common rename helper that honours dry-run mode."""
    if src == dst:
        return
    if dst.exists():
        print(f"⚠️  {dst} esiste già, salto {src}")
        return
    msg = f"{icon} {src.name} → {dst.name}"
    if dry_run:
        print(f"[dry-run] {msg}")
        return
    try:
        src.rename(dst)
        print(msg)
    except OSError as e:
        print(f"{src} => {e}")

def rename_directory_if_possible(directory: Path, dry_run: bool):
    info = guessit(directory.name)
    raw_title = info.get("title")
    title = raw_title[0] if isinstance(raw_title, list) else raw_title
    year = info.get("year")
    if title and year:
        new_path = directory.parent / f"{title} ({year})"
        _rename(directory, new_path, "📁", dry_run)

def rename_season_folder_from_files(season_dir: Path, dry_run: bool):
    if not season_dir.is_dir():
        return
    video = next((v for v in season_dir.rglob("*")
                  if v.is_file() and is_video(v)), None)
    if video is None:
        return
    season = guessit(str(video)).get("season")
    if season is None:
        return
    new_path = season_dir.parent / f"Season {int(season):02d}"
    _rename(season_dir, new_path, "📁", dry_run)

def change_file(file: Path, dry_run: bool):
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
            ep_part = (f"E{int(episodes[0]):02d}"
                       if len(episodes) == 1
                       else f"E{int(episodes[0]):02d}-E{int(episodes[-1]):02d}")
        else:
            ep_part = f"E{int(episodes):02d}"
        new_name = f"{title} - S{int(season):02d}{ep_part}{file.suffix}"
    elif media_type == "movie":
        year = info.get("year")
        if not title or not year:
            return
        new_name = f"{title} ({year}){file.suffix}"
    else:
        return
    _rename(file, file.with_name(new_name), "🎞️", dry_run)

def change_dir_movie(directory: Path, dry_run: bool):
    videos = [f for f in directory.iterdir()
              if f.is_file() and is_video(f) and "sample" not in f.name.lower()]
    if not videos:
        return
    main_video = max(videos, key=lambda f: f.stat().st_size)
    change_file(main_video, dry_run)
    rename_directory_if_possible(directory, dry_run)

def change_dir_tv(directory: Path, dry_run: bool):
    for sub in directory.iterdir():
        rename_season_folder_from_files(sub, dry_run)

    for video in directory.rglob("*"):
        if video.is_file() and is_video(video):
            change_file(video, dry_run)

    rename_directory_if_possible(directory, dry_run)

def parse_args():
    parser = argparse.ArgumentParser(
        prog="jrdf",
        description="Just Rename the Damn Files"
    )
    parser.add_argument("paths", nargs="+", help="File or directory to rename")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-M", "--movie", action="store_true",
                      help="Movie mode (rename largest video file only)")
    mode.add_argument("-T", "--tv", action="store_true",
                      help="TV mode (rename all video files)")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="Show what would be renamed without changing anything")
    return parser.parse_args()

def main():
    args = parse_args()

    for path_str in args.paths:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            print(f"{path} not found")
            continue
        if path.is_file():
            print(f"Processing file: {path}")
            change_file(path, args.dry_run)
        elif path.is_dir():
            print(f"Processing directory: {path}")
            if args.movie:
                change_dir_movie(path, args.dry_run)
            elif args.tv:
                change_dir_tv(path, args.dry_run)

if __name__ == "__main__":
    main()
