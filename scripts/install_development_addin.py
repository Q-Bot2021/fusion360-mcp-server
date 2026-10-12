"""Install or refresh a persistent, hash-owned CAD development add-in."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

OWNERSHIP = ".fusion-mcp-test-ownership.json"


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(repository: Path, destination: Path) -> int:
    if destination.is_symlink():
        raise ValueError("Refusing linked installation directory")
    record_path = destination / OWNERSHIP
    previous = {}
    if record_path.exists():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("kind") != "fusion-mcp-development-fixture":
            raise ValueError("Unknown installation ownership")
        previous = record["files"]
    entries = {}
    for source, prefix in (
        (repository / "tests/fusion_addins/Fusion360MCPDev", ""),
        (repository / "addon/server", "server"),
    ):
        for path in source.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".manifest"}:
                entries[(Path(prefix) / path.relative_to(source)).as_posix()] = path
    if "Fusion360MCPDev.py" not in entries or "server/event_bridge.py" not in entries:
        raise ValueError("Required development sources are missing")
    for relative in set(previous) | set(entries):
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Unsafe ownership path")
        target = destination / relative
        if target.is_symlink() or not target.resolve().is_relative_to(
            destination.resolve()
        ):
            raise ValueError("Unsafe installation target")
        if target.exists():
            if not target.is_file() or previous.get(relative) != checksum(target):
                raise ValueError(f"Modified or unowned file preserved: {relative}")
    destination.mkdir(parents=True, exist_ok=True)
    for relative in previous.keys() - entries.keys():
        (destination / relative).unlink(missing_ok=True)
    hashes = {}
    for relative, source in entries.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[relative] = checksum(source)
    record_path.write_text(
        json.dumps(
            {
                "kind": "fusion-mcp-development-fixture",
                "files": hashes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(hashes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count = install(Path(__file__).resolve().parents[1], args.destination)
    print(f"Installed {count} owned files")


if __name__ == "__main__":
    main()
