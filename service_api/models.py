import enum
import uuid
from uuid import UUID

from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geography
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship, mapped_column


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class TaskStatus(enum.StrEnum):
    pending = enum.auto()
    running = enum.auto()
    completed = enum.auto()
    failed = enum.auto()


class TaskType(enum.StrEnum):
    reverse = enum.auto()
    distance = enum.auto()


class Upload(db.Model):
    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str]

    points: Mapped[list["Point"]] = relationship("Point", backref="upload", lazy=True)
    distances: Mapped[list["Distance"]] = relationship(
        "Distance", backref="upload", lazy=True
    )
    task: Mapped["Task"] = relationship("Task", backref="upload", uselist=False)


class Point(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    geom: Mapped[Geography] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    upload_uuid: Mapped[UUID] = mapped_column(ForeignKey("upload.uuid"), nullable=False)
    address: Mapped[str] = mapped_column(nullable=True)


class Distance(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name_a: Mapped[str] = mapped_column(db.String, nullable=False)
    name_b: Mapped[str] = mapped_column(db.String, nullable=False)
    point_a: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    point_b: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    distance: Mapped[float] = mapped_column(nullable=True)
    upload_uuid: Mapped[UUID] = mapped_column(ForeignKey("upload.uuid"), nullable=False)


class Task(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[TaskStatus] = mapped_column(
        default=TaskStatus.pending, nullable=False
    )
    task_type: Mapped[TaskType] = mapped_column(nullable=False)
    upload_uuid: Mapped[UUID] = mapped_column(ForeignKey("upload.uuid"), nullable=False)
