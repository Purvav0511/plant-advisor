import pytest

from scripts.forbid_private import is_forbidden


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/wear_protection/sheet.pdf",
        "evals/photos/private/a.jpg",
        "ingestion/reports/wear_protection.md",
        ".env",
        "services/api/.env",
        ".env.local",
        "certs/server.key",
        "data\\raw\\x.pdf",
    ],
)
def test_forbidden(path):
    assert is_forbidden(path)


@pytest.mark.parametrize(
    "path",
    [".env.example", "assets/eval-photos/wp-0001-a.jpg", "docs/SPEC.md", "data/README.md"],
)
def test_allowed(path):
    assert not is_forbidden(path)
