#!/usr/bin/env python3

import sys
from pathlib import Path
import mimetypes
import argparse
from guessit import guessit

VERBOSE = False

def vprint(*args, **kwargs):
    if VERBOSE:
        print("[~]", *args, **kwargs)

def is_video(file: Path) -> bool:
    mime = mimetypes.guess_type(file)[0]
    return mime is not None and "video" in mime

def _season_from_parent(file: Path) -> int | None:
    """Try to extract season number from a parent directory named 'Season XX'."""
    for parent in file.parents:
        if parent.name.startswith("Season "):
            try:
                return int(parent.name[7:])
            except ValueError:
                continue
    return None

def organize_into_seasons(directory: Path, dry_run: bool):
    subdirs_with_videos = []
    for subdir in directory.iterdir():
        if subdir.is_dir() and any(is_video(f) for f in subdir.iterdir() if f.is_file()):
            subdirs_with_videos.append(subdir)
    
    if subdirs_with_videos:
        for subdir in subdirs_with_videos:
            info = guessit(subdir.name)
            season = info.get("season")
            if season is None:
                continue
            new_name = f"Season {int(season):02d}"
            new_path = directory / new_name
            if subdir.name == new_name:
                continue
            if new_path.exists():
                for video in subdir.iterdir():
                    if video.is_file() and is_video(video):
                        dst = new_path / video.name
                        if dst.exists():
                            print(f"[!] {dst} already exists, skipping {video.name}")
                            continue
                        if dry_run:
                            print(f"[dry-run] [>] moving {video.name} into {new_name}/")
                        else:
                            video.rename(dst)
                if dry_run:
                    print(f"[dry-run] [-] removing empty directory {subdir.name}")
                else:
                    try:
                        subdir.rmdir()
                    except OSError:
                        print(f"[!] Could not remove {subdir.name} (not empty)")
                continue
            msg = f"[+] {subdir.name} -> {new_name}"
            if dry_run:
                print(f"[dry-run] {msg}")
            else:
                subdir.rename(new_path)
                print(msg)
    else:
        seasons = {}
        for video in directory.iterdir():
            if not video.is_file() or not is_video(video):
                continue
            info = guessit(str(video))
            season = info.get("season")
            if not season:
                season = 1
            if season in seasons:
                seasons[season].append(video)
            else:
                seasons[season] = [video]
        for season, files in seasons.items():
            season_dir = directory / f"Season {int(season):02d}"
            if not season_dir.exists():
                if dry_run:
                    print(f"[dry-run] [+] creating {season_dir}")
                else:
                    season_dir.mkdir()
            for f in files:
                dst = season_dir / f.name
                if dry_run:
                    print(f"[dry-run] [>] moving {f.name} in {season_dir.name}/")
                else:
                    f.rename(dst)

def change_file(file: Path, dry_run: bool, season_hint: int | None = None, title_hint: str | None = None):
    options = {"type": "episode"} if season_hint is not None else {}
    info = guessit(str(file), options)
    media_type = info.get("type")
    raw_title = info.get("title")
    title = raw_title[0] if isinstance(raw_title, list) else raw_title

    vprint(f"  file: {file.name}")
    vprint(f"  guessit: {dict(info)}")
    vprint(f"  hints: season_hint={season_hint}, title_hint={title_hint!r}")

    if media_type == "episode":
        season = info.get("season")
        if season is None:
            season = season_hint
        if season is None:
            season = _season_from_parent(file)
        if season is not None and int(season) == 0:
            vprint(f"  SKIP: season 0")
            return
        episodes = info.get("episode")
        if season is None or episodes is None:
            vprint(f"  SKIP: season={season}, episodes={episodes}")
            return
        if isinstance(episodes, list):
            ep_part = (f"E{int(episodes[0]):02d}" \
                       if len(episodes) == 1 \
                       else f"E{int(episodes[0]):02d}-E{int(episodes[-1]):02d}")
        else:
            ep_part = f"E{int(episodes):02d}"

        ep_title = title_hint if title_hint else title
        if not ep_title:
            vprint(f"  SKIP: no title")
            return
        new_name = f"{ep_title} S{int(season):02d}{ep_part}{file.suffix}"
    elif media_type == "movie":
        year = info.get("year")
        if not title or not year:
            vprint(f"  SKIP: movie missing title={title!r} or year={year}")
            return
        new_name = f"{title} ({year}){file.suffix}"
    else:
        vprint(f"  SKIP: type={media_type!r}")
        return

    dst = file.with_name(new_name)
    if file == dst:
        vprint(f"  SKIP: already correct")
        return
    if dst.exists():
        print(f"[!] {dst} already exists, skipping {file.name}")
        return
    msg = f"[*] {file.name} -> {dst.name}"
    if dry_run:
        print(f"[dry-run] {msg}")
    else:
        file.rename(dst)
        print(msg)

def change_dir_tv(directory: Path, dry_run: bool):
    dir_info = guessit(directory.name)
    raw_title = dir_info.get("title")
    title_hint = raw_title[0] if isinstance(raw_title, list) else raw_title
    vprint(f"show dir: {directory.name!r} -> title_hint={title_hint!r}")

    has_season_dirs = any(
        d.name.startswith("Season ") for d in directory.iterdir() if d.is_dir()
    )

    for video in directory.rglob("*"):
        if video.is_file() and is_video(video):
            season_hint = _season_from_parent(video)
            if season_hint is None and not has_season_dirs:
                season_hint = 1
            change_file(video, dry_run, season_hint=season_hint, title_hint=title_hint)
    organize_into_seasons(directory, dry_run)
    rename_directory_if_possible(directory, dry_run)

def change_dir_movie(directory: Path, dry_run: bool):
    videos = [f for f in directory.iterdir()
              if f.is_file() and is_video(f) and "sample" not in f.name.lower()]
    if not videos:
        return
    main_video = max(videos, key=lambda f: f.stat().st_size)
    change_file(main_video, dry_run)
    rename_directory_if_possible(directory, dry_run)

def rename_directory_if_possible(directory: Path, dry_run: bool):
    info = guessit(directory.name)
    raw_title = info.get("title")
    title = raw_title[0] if isinstance(raw_title, list) else raw_title
    year = info.get("year")
    if title and year:
        new_path = directory.parent / f"{title} ({year})"
        if directory == new_path:
            return
        if new_path.exists():
            print(f"[!] {new_path} already exists, skipping {directory.name}")
            return
        msg = f"[+] {directory.name} -> {new_path.name}"
        if dry_run:
            print(f"[dry-run] {msg}")
        else:
            directory.rename(new_path)
            print(msg)

def parse_args():
    parser = argparse.ArgumentParser(
        prog="jrdf",
        description="Just Rename the Damn Files"
    )
    parser.add_argument("paths", nargs="+", help="File or directory to rename")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-M", "--movie", action="store_true",
                      help="Movie mode (renames only the largest video)")
    mode.add_argument("-T", "--tv", action="store_true",
                      help="TV mode (renames all episodes and organize)")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="Run without writing the changes")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show debug info from guessit parsing")
    return parser.parse_args()

def jrdf() -> None:
    global VERBOSE
    args = parse_args()
    VERBOSE = args.verbose
    for path_str in args.paths:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            print(f"{path} not found")
            continue
        if path.is_file():
            change_file(path, args.dry_run)
        elif path.is_dir():
            if args.movie:
                change_dir_movie(path, args.dry_run)
            elif args.tv:
                change_dir_tv(path, args.dry_run)
