"""Build pointer-only API metadata from an extracted official Fusion help archive."""

import argparse
import csv
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

BASE_URL = "https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/"
KINDS = frozenset(
    {"Method", "Property", "Event", "Object", "Enumeration", "Enumerator"}
)


class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.parts = []
        self.canonical = None
        self.namespace = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href")
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.parts.append(data)
        prefix = 'Defined in namespace "'
        if prefix in data:
            namespace = data.partition(prefix)[2].partition('"')[0].replace("::", ".")
            if namespace.startswith("adsk.") and all(
                part.isidentifier() for part in namespace.split(".")
            ):
                self.namespace = namespace


def reference_pointer(filename: str, source: str) -> tuple[str, str, str] | None:
    parser = TitleParser()
    parser.feed(source)
    title = " ".join("".join(parser.parts).split())
    symbol, separator, kind = title.rpartition(" ")
    if not separator or kind not in KINDS or not symbol:
        return None
    if Path(filename).name != filename or not filename.endswith(".htm"):
        raise ValueError("Reference filename must be a local .htm basename")
    url = urlsplit(urljoin(BASE_URL, parser.canonical or quote(filename)))
    if url.scheme != "https" or url.netloc != "help.autodesk.com":
        raise ValueError(
            "Canonical URL must point to Autodesk's official API reference"
        )
    if not url.path.startswith(urlsplit(BASE_URL).path):
        raise ValueError("Canonical URL must remain inside the API reference")
    namespace = filename.partition("_")[0]
    if parser.namespace:
        symbol = f"{parser.namespace}.{symbol}"
    elif namespace in {"core", "fusion", "cam", "drawing"}:
        symbol = f"adsk.{namespace}.{symbol}"
    category = "enumeration" if kind == "Enumerator" else kind.lower()
    return symbol, category, url._replace(query="", fragment="").geturl()


def build_index(source_dir: Path, output: Path) -> dict[str, int]:
    rows = set()
    for path in source_dir.rglob("*.htm"):
        if path.parent.name.lower() not in {"files", "html"}:
            continue
        pointer = reference_pointer(path.name, path.read_text(encoding="utf-8-sig"))
        if pointer is not None:
            rows.add(pointer)
    if not rows or not any(row[1] == "method" for row in rows):
        raise ValueError("No API method reference pages found; refusing an empty index")
    counts = {}
    for _, kind, _ in rows:
        counts[kind] = counts.get(kind, 0) + 1
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(("symbol", "kind", "url"))
        writer.writerows(sorted(rows))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Extracted official FusionAPI.chm")
    parser.add_argument("output", type=Path, help="Destination pointer-only TSV")
    args = parser.parse_args()
    counts = build_index(args.source, args.output)
    for kind, count in sorted(counts.items()):
        print(f"{kind}: {count}")


if __name__ == "__main__":
    main()