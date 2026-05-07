TEXT_FILE_SUFFIXES = {".md", ".py", ".toml"}
EXCLUDED_PARTS = {
    ".idea",
    ".pytest-tmp",
    ".ruff_cache",
    ".test-output",
    "__pycache__",
}
MOJIBAKE_MARKERS = (
    chr(0x3F) * 3,
    chr(0xFFFD),
    chr(0x93C4),
    chr(0x935A),
    chr(0x6DC7),
    chr(0x951B),
)


def test_repository_text_files_do_not_contain_encoding_damage() -> None:
    from pathlib import Path

    damaged: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_FILE_SUFFIXES:
            continue
        if any(
            part in EXCLUDED_PARTS or part.startswith("pytest-cache-files-")
            for part in path.parts
        ):
            continue
        text = path.read_text(encoding="utf-8")
        for marker in MOJIBAKE_MARKERS:
            if marker in text:
                damaged.append(f"{path}:{marker.encode('unicode_escape').decode('ascii')}")

    assert damaged == []
