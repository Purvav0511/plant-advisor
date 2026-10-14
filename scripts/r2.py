"""Cloudflare R2 access for the dev tools (PLAN 0.5): the raw-file store and the bucket's CORS.

`uv run poe r2-cors` checks the bucket's CORS the way a browser would (and prints the
rules from `config/r2-cors.json` to paste if it's wrong). R2 speaks the S3 API, so this
uses boto3 with R2's endpoint. Credentials come from `.env` (R2_* names in `.env.example`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import boto3

from scripts._common import REPO_ROOT

CORS_FILE = REPO_ROOT / "config" / "r2-cors.json"
SHA_META = "sha256"  # stored as x-amz-meta-sha256 on every upload


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"error: {name} is empty. Fill it in .env (DEV_SETUP §5).")
    return value


def client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=f"https://{env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def raw_prefix() -> str:
    """The private prefix for synced files, always ending in `/` (default `raw/`)."""
    prefix = os.environ.get("R2_RAW_PREFIX", "") or "raw/"
    return prefix if prefix.endswith("/") else f"{prefix}/"


class R2Store:
    """The `Store` used by `scripts.raw_sync`, backed by one R2 bucket."""

    def __init__(self, s3: Any, bucket: str) -> None:
        self.s3 = s3
        self.bucket = bucket

    @classmethod
    def from_env(cls) -> R2Store:
        return cls(client(), env("R2_BUCKET"))

    def list(self, prefix: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for page in self.s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                head = self.s3.head_object(Bucket=self.bucket, Key=key)
                digest = head.get("Metadata", {}).get(SHA_META)
                result[key] = digest or self._hash_remote(key)
        return result

    def _hash_remote(self, key: str) -> str:
        """Checksum of an object uploaded without our metadata (e.g. through the dashboard)."""
        digest = hashlib.sha256()
        body = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
        for chunk in iter(lambda: body.read(1 << 20), b""):
            digest.update(chunk)
        return digest.hexdigest()

    def upload(self, path: Path, key: str, sha256: str) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.s3.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"Metadata": {SHA_META: sha256}, "ContentType": content_type},
        )

    def download(self, key: str, path: Path) -> None:
        """Download to a temporary file, verify the checksum, then move it into place."""
        path.parent.mkdir(parents=True, exist_ok=True)
        expected = (
            self.s3.head_object(Bucket=self.bucket, Key=key).get("Metadata", {}).get(SHA_META)
        )
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".download-")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            self.s3.download_file(self.bucket, key, str(tmp))
            if expected:
                actual = hashlib.sha256(tmp.read_bytes()).hexdigest()
                if actual != expected:
                    raise SystemExit(f"error: checksum mismatch downloading {key}; nothing written")
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)


# --- CORS -------------------------------------------------------------------------------
# The app's R2 token can only read and write objects, not change bucket settings (least
# privilege). So the rules are pasted into the dashboard once, and this checks them the way
# a browser does: a CORS preflight against a presigned upload URL.

# Must be allowed by config/r2-cors.json; the last one must be refused.
CHECK_ORIGINS = {
    "http://localhost:3000": True,
    "https://example-tunnel.trycloudflare.com": True,
    "https://not-our-site.example.com": False,
}


def wanted_cors() -> list[dict[str, Any]]:
    return json.loads(CORS_FILE.read_text(encoding="utf-8"))["CORSRules"]


def preflight_allows(url: str, origin: str) -> bool:
    """Whether R2 answers a browser's upload preflight from `origin` with permission."""
    request = urllib.request.Request(
        url,
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            allowed = response.headers.get("Access-Control-Allow-Origin", "")
    except urllib.error.HTTPError as exc:
        allowed = exc.headers.get("Access-Control-Allow-Origin", "") if exc.code < 500 else ""
    return allowed in (origin, "*")


def check_cors() -> dict[str, bool]:
    """Preflight result per origin in CHECK_ORIGINS. Uploads nothing."""
    url = client().generate_presigned_url(
        "put_object",
        Params={"Bucket": env("R2_BUCKET"), "Key": f"{raw_prefix()}.cors-check"},
        ExpiresIn=300,
    )
    return {origin: preflight_allows(url, origin) for origin in CHECK_ORIGINS}


def cors_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="r2-cors")
    parser.add_argument("--rules", action="store_true", help="print the rules to paste")
    args = parser.parse_args(argv)
    rules = json.dumps(wanted_cors(), indent=2)
    if args.rules:
        print(rules)
        return 0
    results = check_cors()
    ok = True
    for origin, allowed in results.items():
        expected = CHECK_ORIGINS[origin]
        ok = ok and allowed == expected
        verdict = "allowed" if allowed else "refused"
        mark = "ok" if allowed == expected else "WRONG"
        print(f"[{mark:>5}] {origin}: {verdict} (should be {'allowed' if expected else 'refused'})")
    if ok:
        print("CORS works: browsers on our origins can upload; other sites can't.")
        return 0
    print(
        "\nThe bucket's CORS doesn't match config/r2-cors.json. In the Cloudflare dashboard:\n"
        "R2 → your bucket → Settings → CORS Policy → Add/Edit → JSON tab, paste this, save:\n"
    )
    print(rules)
    print("\nThen run `uv run poe r2-cors` again (R2 can take up to 30 seconds to apply).")
    return 1


if __name__ == "__main__":
    sys.exit(cors_main(sys.argv[1:]))
