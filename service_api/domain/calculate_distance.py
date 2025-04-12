import os

from flask import current_app

from service_api.models import Upload, db, Task, TaskStatus, TaskType


def save_file(file, upload_uuid):
    # Generate a unique identifier for this upload.

    # Build the file path where the CSV file will be saved.
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{upload_uuid}.csv")
    file.save(save_path)

    # Create a new Upload record with the generated UUID and the original filename.
    upload = Upload(uuid=upload_uuid, filename=file.filename)
    db.session.add(upload)

    # Create two Task records:
    # - reverse_task: for reverse geocoding of points.
    # - distance_task: for calculating distances (combinations of points).
    reverse_task = Task(status=TaskStatus.pending, task_type=TaskType.reverse, upload_uuid=upload_uuid)
    distance_task = Task(status=TaskStatus.pending, task_type=TaskType.distance, upload_uuid=upload_uuid)
    db.session.add_all([reverse_task, distance_task])
    db.session.commit()
