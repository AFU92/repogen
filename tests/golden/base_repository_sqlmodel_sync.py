"""Base repository (SQLModel sync).

Shared base repository with common CRUD operations. You may customize.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from sqlmodel import Session, select
from sqlalchemy import func

T = TypeVar("T")


class BaseRepository(Generic[T]):
    class NotFoundError(Exception):
        """Raised when an entity is not found."""

    def __init__(self, model: type[T], id_field: str) -> None:
        self.model = model
        self.id_field = id_field

    def get(self, session: Session, id: Any) -> Optional[T]:
        stmt = select(self.model).where(getattr(self.model, self.id_field) == id)
        return session.exec(stmt).first()

    def get_or_raise(self, session: Session, id: Any) -> T:
        obj = self.get(session, id)
        if obj is None:
            raise self.NotFoundError(f"{self.model.__name__} not found: {id}")
        return obj

    def list(self, session: Session, *where, limit: int = 100, offset: int = 0) -> list[T]:
        stmt = select(self.model)
        if where:
            stmt = stmt.where(*where)
        stmt = stmt.offset(offset).limit(limit)
        return list(session.exec(stmt).all())

    def find_one(self, session: Session, *where) -> Optional[T]:
        stmt = select(self.model)
        if where:
            stmt = stmt.where(*where)
        return session.exec(stmt).first()

    def create(self, session: Session, obj_in: T) -> T:
        session.add(obj_in)
        session.commit()
        session.refresh(obj_in)
        return obj_in

    def update(self, session: Session, db_obj: T, obj_in: dict[str, Any]) -> T:
        for k, v in obj_in.items():
            setattr(db_obj, k, v)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def delete(self, session: Session, db_obj: T) -> None:
        session.delete(db_obj)
        session.commit()

    def delete_by_id(self, session: Session, id: Any) -> bool:
        obj = self.get(session, id)
        if not obj:
            return False
        self.delete(session, obj)
        return True

    def exists(self, session: Session, *where) -> bool:
        stmt = select(self.model)
        if where:
            stmt = stmt.where(*where)
        return session.exec(stmt.limit(1)).first() is not None

    def count(self, session: Session, *where) -> int:
        stmt = select(func.count()).select_from(self.model)
        if where:
            stmt = stmt.where(*where)
        return int(session.exec(stmt).scalar_one())
