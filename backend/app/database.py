from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> set[str]:
    """轻量迁移：为旧库补 oven_type 列（无 Alembic 环境）。

    返回本次刚补过列的表名，供一次性数据回填使用。
    """
    migrated: set[str] = set()
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in ("products", "ovens"):
            if table not in inspector.get_table_names():
                continue
            cols = {c["name"] for c in inspector.get_columns(table)}
            if "oven_type" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE " + table + " ADD COLUMN oven_type "
                        "VARCHAR(10) DEFAULT 'tray' NOT NULL"
                    )
                )
                migrated.add(table)
    return migrated
