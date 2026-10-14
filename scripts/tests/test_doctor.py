from pathlib import PurePosixPath, PureWindowsPath

from scripts.doctor import (
    compare_env,
    crlf_files,
    location_problems,
    major_version,
    migration_drift,
    parse_env_names,
)


def test_parse_env_names_reads_names_and_emptiness():
    text = """
# comment
DEV_MACHINE=pc-wsl
APP_ENV=
export QUOTED="value"
EMPTY_QUOTES=""
not a line
=novalue
"""
    assert parse_env_names(text) == {
        "DEV_MACHINE": True,
        "APP_ENV": False,
        "QUOTED": True,
        "EMPTY_QUOTES": False,
    }


def test_compare_env_reports_missing_and_empty_in_example_order():
    example = {"A": False, "B": False, "C": False}
    actual = {"A": True, "C": False, "EXTRA": True}
    assert compare_env(example, actual) == (["B"], ["C"])


def test_crlf_files_flags_crlf_and_mixed_index_entries():
    out = (
        "i/lf    w/lf    attr/text=auto eol=lf \tREADME.md\n"
        "i/crlf  w/crlf  attr/text=auto eol=lf \tbad.py\n"
        "i/mixed w/mixed attr/                 \tmixed.txt\n"
        "i/-text w/-text attr/-text            \timage.png\n"
    )
    assert crlf_files(out) == ["bad.py", "mixed.txt"]


def test_location_flags_windows_drive_from_wsl_only():
    path = PurePosixPath("/mnt/c/Users/me/code/plant-advisor")
    assert location_problems(path, is_wsl=True)
    assert location_problems(path, is_wsl=False) == []
    assert location_problems(PurePosixPath("/home/me/code/plant-advisor"), is_wsl=True) == []


def test_location_flags_synced_folders():
    mac = PurePosixPath("/Users/me/Library/Mobile Documents/com~apple~CloudDocs/plant-advisor")
    win = PureWindowsPath(r"C:\Users\me\OneDrive\code\plant-advisor")
    assert location_problems(mac, is_wsl=False)
    assert location_problems(win, is_wsl=False)


def test_migration_drift_both_directions():
    assert migration_drift(["001", "002"], ["001", "003"]) == (["002"], ["003"])
    assert migration_drift([], []) == ([], [])


def test_major_version():
    assert major_version("v22.23.3") == 22
    assert major_version("garbage") is None
