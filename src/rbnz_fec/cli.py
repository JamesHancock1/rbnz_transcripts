import argparse

from . import discover, download, export, transcribe


def main() -> None:
    ap = argparse.ArgumentParser(prog="rbnz-fec")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="build data/catalogue.csv")
    d.add_argument("--crawl-from", type=int, help="crawl RBNZ events pages from this year")
    d.add_argument("--no-search", action="store_true")

    dl = sub.add_parser("download", help="fetch audio for catalogue rows")
    dl.add_argument("--all", action="store_true", help="include unverified rows")
    dl.add_argument("--cookies", help="cookies.txt (needed for Facebook videos)")

    t = sub.add_parser("transcribe")
    t.add_argument("--model", default="large-v3")
    t.add_argument("--no-diarize", action="store_true")
    t.add_argument("--force", action="store_true")

    e = sub.add_parser("export", help="txt files + combined data/corpus.csv")
    e.add_argument("--media-corpus", help="CSV of media-conference turns to merge in")

    a = ap.parse_args()
    if a.cmd == "discover":
        yrs = range(a.crawl_from, 2027) if a.crawl_from else None
        discover.run(crawl_years=yrs, search=not a.no_search)
    elif a.cmd == "download":
        download.run(only_verified=not a.all, cookies=a.cookies)
    elif a.cmd == "transcribe":
        transcribe.run(a.model, diarize=not a.no_diarize, force=a.force)
    else:
        export.run(a.media_corpus)


if __name__ == "__main__":
    main()
