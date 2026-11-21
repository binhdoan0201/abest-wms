"""ABEST WMS - Kết nối và quản lý Transaction CSDL (SQLAlchemy 2.x + Psycopg 3)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from server.app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Lớp cơ sở cho các ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Dependency cung cấp Session CSDL cho FastAPI request.

    Một transaction mỗi request:
    - Tự động commit khi request xử lý thành công không có lỗi.
    - Tự động rollback khi phát sinh bất kỳ ngoại lệ nào.
    - Luôn giải phóng kết nối trong khối finally.
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
