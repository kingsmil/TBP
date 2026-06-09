from app.db.session import _sqlalchemy_url


def test_sqlalchemy_url_selects_installed_psycopg_driver():
    assert _sqlalchemy_url("postgresql://user:pass@db/app") == (
        "postgresql+psycopg://user:pass@db/app"
    )
    assert _sqlalchemy_url("postgres://user:pass@db/app") == (
        "postgresql+psycopg://user:pass@db/app"
    )


def test_sqlalchemy_url_preserves_explicit_driver():
    url = "postgresql+psycopg://user:pass@db/app"
    assert _sqlalchemy_url(url) == url
