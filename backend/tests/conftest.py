import os

# The provider store is initialized during API import; auth tests use an isolated SQLite URL.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
