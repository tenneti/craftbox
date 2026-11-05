"""Canonical JSON and SHA-256 fingerprints shared by the service layer and craft engines."""
import hashlib
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()
