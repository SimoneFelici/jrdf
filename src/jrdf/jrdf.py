#!/usr/bin/env python3

from pathlib import Path
import mimetypes
import argparse
import logging
from guessit import guessit

log = logging.getLogger(__name__)

def is_video(file: Path) -> bool:
    mime = mimetypes.guess_type(file)[0]
    return mime is not None and mime.startswith("video/")


def season_hint_from_season_dir(file: Path) -> int | None:
    for parent in file.parents:
        if not parent.name.startswith("Season "):
            continue

        season = parent.name[7:]
        if season.isdigit():
            return int(season)

    return None

def get_title(info) -> str | None:
    raw = info.get("title")
    if isinstance(raw, list):
        return raw[0] if raw else None
    return raw


def episode_part(episodes) -> str:
    episodes = episodes if isinstance(episodes, list) else [episodes]

    part = f"E{int(episodes[0]):02d}"
    if episodes[0] != episodes[-1]:
        part += f"-E{int(episodes[-1]):02d}"

    return part

def cleanup_empty_source_dirs(root: Path, dry_run: bool, planned_sources: set[Path]):
    candidate_dirs: set[Path] = set()

    for src in planned_sources:
        parent = src.parent
        while parent != root:
            candidate_dirs.add(parent)
            parent = parent.parent

    removable_dirs: set[Path] = set()

    for directory in sorted(candidate_dirs, key=lambda p: len(p.parts), reverse=True):
        if not directory.exists():
            continue

        if dry_run:
            empty = True
            for child in directory.iterdir():
                if child.is_file() and child not in planned_sources:
                    empty = False
                    break
                if child.is_dir() and child not in removable_dirs:
                    empty = False
                    break

            if empty:
                print(f"[dry-run] [-] removing empty directory {directory.relative_to(root)}")
                removable_dirs.add(directory)
        else:
            try:
                directory.rmdir()
                print(f"[-] removed empty directory {directory.relative_to(root)}")
            except OSError:
                pass

def change_file(file: Path, dry_run: bool):
    info = guessit(str(file))
    media_type = info.get("type")
    title = get_title(info)

    log.debug("file: %s", file.name)
    log.debug("guessit: %s", dict(info))

    if media_type == "episode":
        season = info.get("season")
        episodes = info.get("episode")

        if season is None or episodes is None:
            log.debug("SKIP: season=%s, episodes=%s", season, episodes)
            return

        if int(season) == 0:
            log.debug("SKIP: season 0")
            return

        if not title:
            log.debug("SKIP: no title")
            return

        new_name = f"{title} S{int(season):02d}{episode_part(episodes)}{file.suffix}"

    elif media_type == "movie":
        year = info.get("year")
        if not title or not year:
            log.debug("SKIP: movie missing title=%r or year=%s", title, year)
            return

        new_name = f"{title} ({year}){file.suffix}"

    else:
        log.debug("SKIP: type=%r", media_type)
        return

    dst = file.with_name(new_name)

    if file == dst:
        log.debug("SKIP: already correct")
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

def change_tv_file(
    file: Path,
    root: Path,
    dry_run: bool,
    title_hint: str | None,
    planned_dirs: set[Path],
    planned_dsts: set[Path],
    planned_sources: set[Path],
):
    parse_name = str(Path(root.name) / file.relative_to(root))
    info = guessit(parse_name, {"type": "episode"})
    title = get_title(info)

    log.debug("file: %s", file.name)
    log.debug("parse_name: %s", parse_name)
    log.debug("guessit: %s", dict(info))
    log.debug("title_hint=%r", title_hint)

    season = info.get("season")
    if season is None:
        season = season_hint_from_season_dir(file)
    if season is None:
        season = 1

    if int(season) == 0:
        log.debug("SKIP: season 0")
        return

    episodes = info.get("episode")
    if episodes is None:
        log.debug("SKIP: season=%s, episodes=%s", season, episodes)
        return

    series_title = title_hint if title_hint else title
    if not series_title:
        log.debug("SKIP: no title")
        return

    new_name = f"{series_title} S{int(season):02d}{episode_part(episodes)}{file.suffix}"
    season_dir = root / f"Season {int(season):02d}"
    dst = season_dir / new_name

    if file == dst:
        log.debug("SKIP: already correct")
        return

    if dst.exists() or dst in planned_dsts:
        print(f"[!] {dst} already exists, skipping {file.name}")
        return

    if not season_dir.exists() and season_dir not in planned_dirs:
        if dry_run:
            print(f"[dry-run] [+] creating {season_dir}")
        else:
            season_dir.mkdir()
        planned_dirs.add(season_dir)

    msg = f"[*] {file.relative_to(root)} -> {dst.relative_to(root)}"
    if dry_run:
        print(f"[dry-run] {msg}")
    else:
        file.rename(dst)
        print(msg)

    planned_dsts.add(dst)
    planned_sources.add(file)


def change_dir_tv(directory: Path, dry_run: bool):
    dir_info = guessit(directory.name)
    title_hint = get_title(dir_info)
    log.debug("show dir: %r -> title_hint=%r", directory.name, title_hint)

    planned_dirs: set[Path] = set()
    planned_dsts: set[Path] = set()
    planned_sources: set[Path] = set()

    videos = [
        video
        for video in directory.rglob("*")
        if video.is_file() and is_video(video)
    ]

    for video in videos:
        change_tv_file(
            video,
            directory,
            dry_run,
            title_hint=title_hint,
            planned_dirs=planned_dirs,
            planned_dsts=planned_dsts,
            planned_sources=planned_sources,
        )

    cleanup_empty_source_dirs(directory, dry_run, planned_sources)
    rename_directory_if_possible(directory, dry_run)

def change_dir_movie(directory: Path, dry_run: bool):
    videos = [
        f for f in directory.iterdir()
        if f.is_file() and is_video(f) and "sample" not in f.name.lower()
    ]

    if not videos:
        return

    main_video = max(videos, key=lambda f: f.stat().st_size)
    change_file(main_video, dry_run)
    rename_directory_if_possible(directory, dry_run)

def rename_directory_if_possible(directory: Path, dry_run: bool):
    info = guessit(directory.name)
    title = get_title(info)
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
        description="Just Rename the Damn Files",
    )

    parser.add_argument("paths", nargs="+", help="File or directory to rename")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-M", "--movie",
        action="store_true",
        help="Movie mode (renames only the largest video)",
    )
    mode.add_argument(
        "-T", "--tv",
        action="store_true",
        help="TV mode (renames all episodes and organize)",
    )

    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Run without writing the changes",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show debug info from guessit parsing",
    )

    return parser.parse_args()

def jrdf() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="[~] %(message)s",
    )

    for path_str in args.paths:
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            print(f"{path} not found")
            continue

        if path.is_file():
            if args.tv:
                planned_dirs: set[Path] = set()
                planned_dsts: set[Path] = set()
                planned_sources: set[Path] = set()

                root = path.parent
                root_info = guessit(root.name)
                title_hint = get_title(root_info)

                change_tv_file(
                    path,
                    root,
                    args.dry_run,
                    title_hint=title_hint,
                    planned_dirs=planned_dirs,
                    planned_dsts=planned_dsts,
                    planned_sources=planned_sources,
                )
                cleanup_empty_source_dirs(root, args.dry_run, planned_sources)
            else:
                change_file(path, args.dry_run)

        elif path.is_dir():
            if args.movie:
                change_dir_movie(path, args.dry_run)
            elif args.tv:
                change_dir_tv(path, args.dry_run)
