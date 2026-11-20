import pytest

from app.db import normalize_url


@pytest.mark.parametrize("given,expected", [
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("sqlite:///./roster.db", "sqlite:///./roster.db"),
])
def test_normalize_url(given, expected):
    assert normalize_url(given) == expected