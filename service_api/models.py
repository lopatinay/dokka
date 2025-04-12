import enum
import uuid

from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geography
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
  pass


db = SQLAlchemy(model_class=Base)


class TaskStatus(enum.Enum):
    pending = 'pending'
    running = 'running'
    completed = 'completed'
    failed = 'failed'


class TaskType(enum.Enum):
    reverse = 'reverse'
    distance = 'distance'


class Upload(db.Model):
    uuid = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = db.Column(db.String, nullable=False)

    points = db.relationship('Point', backref='upload', lazy=True)
    distances = db.relationship('Distance', backref='upload', lazy=True)
    task = db.relationship('Task', backref='upload', uselist=False)


class Point(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    geom = db.Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    upload_uuid = db.Column(db.UUID(as_uuid=True), db.ForeignKey('upload.uuid'), nullable=False)
    address = db.Column(db.String, nullable=True)

class Distance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name_a = db.Column(db.String, nullable=False)
    name_b = db.Column(db.String, nullable=False)
    point_a = db.Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    point_b = db.Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    distance = db.Column(db.Float, nullable=True)
    upload_uuid = db.Column(db.UUID(as_uuid=True), db.ForeignKey('upload.uuid'), nullable=False)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.pending, nullable=False)
    task_type = db.Column(db.Enum(TaskType), nullable=False)
    upload_uuid = db.Column(db.UUID(as_uuid=True), db.ForeignKey('upload.uuid'), nullable=False)
