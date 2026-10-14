"""Tests for `poe raw-push` and `raw-pull`. A fake store stands in for R2: no network."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.raw_sync import SYNCED_FOLDERS, plan, run_sync, scan_local


class FakeStore:
    """In-memory stand-in for the R2 bucket: key -> bytes."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})
        self.deleted: list[str] = []

    def list(self, prefix: str) -> dict[str, str]:
        return {
            k: hashlib.sha256(v).hexdigest() for k, v in self.files.items() if k.startswith(prefix)
        }

    def upload(self, path: Path, key: str, sha256: str) -> None:
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha256
        self.files[key] = data

    def download(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.files[key])

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        del self.files[key]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(root: Path, rel: str, data: bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# --- the plan (pure) ----------------------------------------------------------------------


def test_plan_push_copies_new_skips_same_and_flags_conflicts():
    local = {"a.pdf": sha(b"a"), "same.pdf": sha(b"s"), "diff.pdf": sha(b"mine")}
    remote = {"same.pdf": sha(b"s"), "diff.pdf": sha(b"theirs"), "only-remote.pdf": sha(b"r")}
    p = plan(source=local, target=remote, overwrite=False, prune=False)
    assert p.copy == ["a.pdf"]
    assert p.same == ["same.pdf"]
    assert p.conflicts == ["diff.pdf"]
    assert p.delete == []
    assert p.target_only == ["only-remote.pdf"]


def test_plan_overwrite_turns_conflicts_into_copies():
    p = plan(source={"x": sha(b"1")}, target={"x": sha(b"2")}, overwrite=True, prune=False)
    assert p.copy == ["x"]
    assert p.conflicts == []


def test_plan_prune_deletes_only_target_only_files():
    p = plan(source={"keep": sha(b"k")}, target={"keep": sha(b"k"), "gone": sha(b"g")},
             overwrite=False, prune=True)  # fmt: skip
    assert p.delete == ["gone"]
    assert p.same == ["keep"]


# --- whole runs against the fake store ----------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_scan_local_covers_only_the_synced_folders(repo: Path):
    write(repo, "data/raw/wear_protection/sheet.pdf", b"pdf")
    write(repo, "evals/photos/private/a.jpg", b"jpg")
    write(repo, "ingestion/reports/wear_protection.md", b"md")
    write(repo, "docs/SPEC.md", b"not synced")
    files = scan_local(repo)
    assert sorted(files) == [
        "data/raw/wear_protection/sheet.pdf",
        "evals/photos/private/a.jpg",
        "ingestion/reports/wear_protection.md",
    ]
    assert files["data/raw/wear_protection/sheet.pdf"] == sha(b"pdf")
    assert {f.split("/")[0] for f in files} <= {s.split("/")[0] for s in SYNCED_FOLDERS}


def test_push_then_pull_gives_identical_files(repo: Path, tmp_path_factory: pytest.TempPathFactory):
    write(repo, "data/raw/wear_protection/sheet.pdf", b"pdf-bytes")
    write(repo, "evals/photos/private/a.jpg", b"jpg-bytes")
    store = FakeStore()
    assert run_sync("push", repo, store, prefix="raw/") == 0
    assert sorted(store.files) == [
        "raw/data/raw/wear_protection/sheet.pdf",
        "raw/evals/photos/private/a.jpg",
    ]

    other_machine = tmp_path_factory.mktemp("mac")
    assert run_sync("pull", other_machine, store, prefix="raw/") == 0
    assert scan_local(other_machine) == scan_local(repo)


def test_push_never_deletes_remote_without_prune(repo: Path):
    store = FakeStore({"raw/data/raw/old.pdf": b"old"})
    write(repo, "data/raw/new.pdf", b"new")
    assert run_sync("push", repo, store, prefix="raw/") == 0
    assert "raw/data/raw/old.pdf" in store.files
    assert store.deleted == []

    assert run_sync("push", repo, store, prefix="raw/", prune=True) == 0
    assert store.deleted == ["raw/data/raw/old.pdf"]


def test_conflicts_are_skipped_and_reported_with_a_failing_exit(repo: Path):
    store = FakeStore({"raw/data/raw/sheet.pdf": b"theirs"})
    write(repo, "data/raw/sheet.pdf", b"mine")
    assert run_sync("push", repo, store, prefix="raw/") == 1
    assert store.files["raw/data/raw/sheet.pdf"] == b"theirs"

    assert run_sync("pull", repo, store, prefix="raw/") == 1
    assert (repo / "data/raw/sheet.pdf").read_bytes() == b"mine"

    assert run_sync("push", repo, store, prefix="raw/", overwrite=True) == 0
    assert store.files["raw/data/raw/sheet.pdf"] == b"mine"


def test_pull_never_deletes_local_files(repo: Path):
    write(repo, "data/raw/local-only.pdf", b"local")
    assert run_sync("pull", repo, FakeStore(), prefix="raw/") == 0
    assert (repo / "data/raw/local-only.pdf").exists()


def test_dry_run_changes_nothing(repo: Path):
    write(repo, "data/raw/sheet.pdf", b"pdf")
    store = FakeStore({"raw/data/raw/stale.pdf": b"x"})
    assert run_sync("push", repo, store, prefix="raw/", prune=True, dry_run=True) == 0
    assert sorted(store.files) == ["raw/data/raw/stale.pdf"]
    assert store.deleted == []


def test_unsafe_remote_keys_are_refused(repo: Path):
    # A key that would write outside the repo must never be downloaded.
    store = FakeStore({"raw/data/raw/../../../etc/evil": b"x"})
    assert run_sync("pull", repo, store, prefix="raw/") == 1
    assert not (repo.parent / "etc").exists()
