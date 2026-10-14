from scripts.db import is_local_url


def test_is_local_url():
    assert is_local_url("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    assert is_local_url("postgresql://u:p@localhost/db")
    assert not is_local_url(
        "postgresql://postgres.ref:pw@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
    )
    assert not is_local_url("")
