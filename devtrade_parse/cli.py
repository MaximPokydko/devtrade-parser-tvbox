"""Batch CLI mode (folder exchange: texts/ -> ideas/ -> pines/).

Examples:
    python -m devtrade_parse transcribe     # youtube_links.txt/insta_links.txt -> texts/
    python -m devtrade_parse extract        # texts/*.txt -> ideas/*.json
    python -m devtrade_parse generate       # ideas/*.json -> pines/*.pine (validated)
    python -m devtrade_parse all            # extract + generate (default)
    python -m devtrade_parse url <link>     # full pipeline for one link to stdout
"""

import argparse
import json
import os
import sys

from .extract import extract_strategy
from .generate import generate_pine
from .pipeline import process_url
from .transcribe import safe_filename, transcribe_url
from .validate import validate_pine

TEXTS_DIR = "texts"
IDEAS_DIR = "ideas"
PINES_DIR = "pines"


def _read_links(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


def cmd_transcribe(_args) -> None:
    os.makedirs(TEXTS_DIR, exist_ok=True)
    urls = _read_links("youtube_links.txt") + _read_links("insta_links.txt")
    if not urls:
        print("No links: fill youtube_links.txt and/or insta_links.txt")
        return
    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{len(urls)}] {url}")
        try:
            t = transcribe_url(url)
        except Exception as e:  # noqa: BLE001 — keep the batch going
            print(f"Error: {e}")
            continue
        out = os.path.join(TEXTS_DIR, f"{safe_filename(t.title)}.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(t.text)
        print(f"Saved: {out}")


def cmd_extract(_args) -> None:
    os.makedirs(IDEAS_DIR, exist_ok=True)
    for name in os.listdir(TEXTS_DIR):
        if not name.endswith(".txt"):
            continue
        with open(os.path.join(TEXTS_DIR, name), encoding="utf-8") as f:
            text = f.read()
        print(f"Processing: {name}")
        try:
            data = extract_strategy(text)
        except ValueError as e:
            print(f"Skip: {e}")
            continue
        out = os.path.join(IDEAS_DIR, name.replace(".txt", ".json"))
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved: {out}")


def cmd_generate(_args) -> None:
    os.makedirs(PINES_DIR, exist_ok=True)
    for name in os.listdir(IDEAS_DIR):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(IDEAS_DIR, name), encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("is_strategy"):
            print(f"Skipping (not strategy): {name}")
            continue
        print(f"Generating Pine: {name}")
        result = validate_pine(generate_pine(data))
        out = os.path.join(PINES_DIR, name.replace(".json", ".pine"))
        with open(out, "w", encoding="utf-8") as f:
            f.write(result.code)
        print(f"Saved: {out}")
        if result.issues:
            print(result.format_issues())


def cmd_all(args) -> None:
    cmd_extract(args)
    cmd_generate(args)


def cmd_url(args) -> None:
    res = process_url(args.url)
    if not res.is_strategy:
        print("No trading strategy found in the video.")
        return
    print(res.pine)
    if res.validation and res.validation.issues:
        print("\n--- Validator notes ---")
        print(res.validation.format_issues())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="devtrade_parse", description="Video -> PineScript pipeline")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("transcribe", help="links -> texts/")
    sub.add_parser("extract", help="texts/ -> ideas/")
    sub.add_parser("generate", help="ideas/ -> pines/")
    sub.add_parser("all", help="extract + generate (default)")
    p_url = sub.add_parser("url", help="full pipeline for one link")
    p_url.add_argument("url")

    args = parser.parse_args(argv)
    handlers = {
        "transcribe": cmd_transcribe,
        "extract": cmd_extract,
        "generate": cmd_generate,
        "all": cmd_all,
        "url": cmd_url,
        None: cmd_all,
    }
    handlers[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
