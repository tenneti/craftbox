"""Content-addressed local store for design assets (images, textures, backgrounds). Local files only; nothing is sent anywhere.

Files are stored once under ``<data>/assets/<first two hex>/<sha256>.<ext>``. The type is decided from the file's first bytes,
not from its name, and only a short list of raster image types is accepted (no SVG, so a stored file can never carry script).
"""
import hashlib
from pathlib import Path

MAX_BYTES = 8_000_000
TYPES = {"png": ("image/png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")), "jpg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
         "gif": ("image/gif", lambda b: b.startswith((b"GIF87a", b"GIF89a"))), "webp": ("image/webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP")}


class AssetError(ValueError):
    pass


def root(data_dir):
    return Path(data_dir) / "assets"


def sniff(data):
    for ext, (mime, test) in TYPES.items():
        if test(data):
            return ext, mime
    raise AssetError("Only PNG, JPEG, GIF and WebP pictures can be added. Convert the file and try again.")


def store(data_dir, data, filename=""):
    if not data:
        raise AssetError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise AssetError(f"The file is {len(data) // 1_000_000} MB. The limit is {MAX_BYTES // 1_000_000} MB; make it smaller and try again.")
    ext, mime = sniff(data)
    sha = hashlib.sha256(data).hexdigest()
    path = root(data_dir) / sha[:2] / f"{sha}.{ext}"
    existed = path.exists()
    if not existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    return {"sha256": sha, "size_bytes": len(data), "mime": mime, "ext": ext, "filename": Path(filename).name[:120] if filename else f"{sha[:12]}.{ext}", "already_stored": existed}


def ingest_path(data_dir, raw):
    p = Path(raw)
    if not p.is_absolute():
        raise AssetError("Give the full path, starting with a drive letter such as C:\\.")
    if not p.is_file():
        raise AssetError("No file was found at that path. Check the spelling, or upload the file instead.")
    if p.stat().st_size > MAX_BYTES:
        raise AssetError(f"That file is larger than {MAX_BYTES // 1_000_000} MB. Make it smaller and try again.")
    out = store(data_dir, p.read_bytes(), p.name)
    out["origin_path"] = str(p)
    return out


def find(data_dir, sha):
    if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
        return None
    d = root(data_dir) / sha[:2]
    for ext in TYPES:
        f = d / f"{sha}.{ext}"
        if f.is_file():
            return f, TYPES[ext][0]
    return None


def present(data_dir, sha):
    return find(data_dir, sha) is not None
