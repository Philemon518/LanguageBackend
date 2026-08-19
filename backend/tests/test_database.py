"""Database connection helper tests."""

import ssl

from app.core.database import _postgres_connect_args


def test_internal_railway_postgres_skips_ssl():
    url = "postgresql+asyncpg://user:pass@postgres.railway.internal:5432/railway"
    assert _postgres_connect_args(url) == {}


def test_external_railway_postgres_uses_unverified_ssl_context():
    url = "postgresql+asyncpg://user:pass@containers-us-west-123.railway.app:6543/railway"
    args = _postgres_connect_args(url)
    assert "ssl" in args
    assert isinstance(args["ssl"], ssl.SSLContext)
    assert args["ssl"].verify_mode == ssl.CERT_NONE
    assert args["ssl"].check_hostname is False
