import csv
import os

from celery import Celery, chord
from flask import current_app
from geoalchemy2.shape import to_shape
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from service_api.models import db, Point, Distance, Task, TaskStatus, TaskType
from service_api.services.geo import haversine_np, reverse_geocode


def make_celery():
    """
    Create and configure a Celery instance using the Flask application's configuration.
    This function ensures that all Celery tasks run within the Flask application context.
    """
    from app import app

    celery = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['RESULT_BACKEND']
    )
    celery.conf.update(app.config)

    # Wrap each task to run within the Flask application context.
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery_app = make_celery()


# ============================================================
# Trigger Task: Process File Tasks
# ============================================================
@celery_app.task(bind=True)
def process_file_tasks(self):
    """
    This task scans the database for all Task records with status 'pending' or 'failed',
    then for each unique upload (determined by upload_uuid), it launches the process_upload task.
    It also marks these tasks as 'running' to avoid duplicate processing.
    """
    try:
        tasks_to_process = Task.query.filter(Task.status.in_([TaskStatus.pending, TaskStatus.failed])).all()
        ran_tasks = set()
        logger.info(f'Found {len(tasks_to_process)} tasks to process')
        for task_record in tasks_to_process:
            upload_uuid = str(task_record.upload_uuid)
            # Mark task as running
            task_record.status = TaskStatus.running
            if upload_uuid in ran_tasks:
                continue
            # Launch the upload processing task asynchronously
            process_upload.delay(upload_uuid)
            ran_tasks.add(upload_uuid)
        db.session.commit()
    except Exception as e:
        logger.error(e)
        self.retry(exc=e, countdown=10)


# ============================================================
# Upload Task: Process CSV File and Insert Points
# ============================================================
@celery_app.task(bind=True)
def process_upload(self, upload_uuid):
    """
    For a given upload_uuid, open the corresponding CSV file, read its rows,
    and bulk insert the point records into the Point table.
    Once the points are inserted, launch tasks for reverse geocoding and for
    generating distance combinations.
    """
    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{upload_uuid}.csv")
        points_to_insert = []
        BATCH_SIZE = 1000

        # Read CSV file row by row and accumulate points for bulk insertion.
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                point_name = row['Point']
                lat = float(row['Latitude'])
                lon = float(row['Longitude'])
                # Store the geometry as WKT: "POINT(lon lat)" format.
                points_to_insert.append({
                    'name': point_name,
                    'geom': f'POINT({lon} {lat})',
                    'upload_uuid': upload_uuid
                })
                if len(points_to_insert) >= BATCH_SIZE:
                    db.session.bulk_insert_mappings(Point, points_to_insert)
                    db.session.commit()
                    points_to_insert = []
            if points_to_insert:
                db.session.bulk_insert_mappings(Point, points_to_insert)
                db.session.commit()

        # Launch the reverse geocoding task (see below).
        reverse_geocode_points.delay(upload_uuid)

        # Launch the distance calculation task that generates combinations.
        calculate_distances.delay(upload_uuid)

    except Exception as e:
        # On failure, mark the Task status as failed.
        Task.query.filter_by(upload_uuid=upload_uuid).update({"status": TaskStatus.failed})
        db.session.commit()
        self.retry(exc=e, countdown=10)


# ============================================================
# Distance Calculation Task: Generate Distance Combinations and Process Them
# ============================================================
@celery_app.task(bind=True)
def calculate_distances(self, upload_uuid):
    """
    This task does the following:
      1. Generates distance combination records by performing a self-join on the Point table
         for points belonging to the given upload_uuid.
      2. Paginates through these distance records in batches of 1,000.
      3. For each batch, it spawns child tasks (calculate_distance_batch) to compute the actual distances.
      4. Uses a chord to trigger a final callback (finalize_distance_calculations) once all child tasks complete.
    """
    try:
        # Insert distance combination records using a self-join on the Point table.
        query = text("""
            INSERT INTO distance (name_a, name_b, point_a, point_b, upload_uuid)
            SELECT 
                a.name AS name_a,
                b.name AS name_b,
                a.geom AS point_a,
                b.geom AS point_b,
                a.upload_uuid
            FROM point a
            JOIN point b ON a.id < b.id
            WHERE a.upload_uuid = :upload_uuid;
        """)
        db.session.execute(query, {"upload_uuid": upload_uuid})
        db.session.commit()
    except Exception as e:
        self.retry(exc=e, countdown=10)

    batch_size = 1000
    last_id = 0
    batch_tasks = []

    # Paginate through the Distance records in batches.
    while True:
        batch = (
            Distance.query
            .filter(Distance.upload_uuid == upload_uuid, Distance.id > last_id)
            .order_by(Distance.id)
            .limit(batch_size)
            .all()
        )
        if not batch:
            break
        batch_ids = [record.id for record in batch]
        last_id = batch_ids[-1]
        # Append the signature of the child task for this batch.
        batch_tasks.append(calculate_distance_batch.s(batch_ids))

    if batch_tasks:
        # Use a chord to run all child tasks in parallel and then finalize.
        chord(batch_tasks)(finalize_distance_calculations.s(upload_uuid))


@celery_app.task(bind=True)
def calculate_distance_batch(self, batch_ids):
    """
    This child task processes a batch of Distance records identified by their IDs.
    For each record, it:
      - Extracts the geometries for point_a and point_b.
      - Computes the distance using the haversine_np function.
      - Prepares an update mapping to update the record's distance field.
    Finally, it performs a bulk update for the entire batch.
    """
    Session = sessionmaker(bind=db.engine)
    session = Session()

    try:
        records = session.query(Distance).filter(Distance.id.in_(batch_ids)).all()
        update_mappings = []
        for rec in records:
            # Convert the stored geography to a Shapely geometry.
            geom_a = to_shape(rec.point_a)
            geom_b = to_shape(rec.point_b)
            # Compute distance using haversine_np (inputs: lon, lat for each point).
            distance = haversine_np(geom_a.x, geom_a.y, geom_b.x, geom_b.y)
            update_mappings.append({'id': rec.id, 'distance': distance})
        if update_mappings:
            session.bulk_update_mappings(Distance, update_mappings)
            session.commit()
    except Exception as e:
        self.retry(exc=e, countdown=10)
    finally:
        session.close()


# ============================================================
# Reverse Geocode Task: Process Points Sequentially Due to API Restrictions
# ============================================================
@celery_app.task(bind=True)
def reverse_geocode_points(self, upload_uuid):
    """
    For the given upload_uuid, this task processes all Point records in batches of 1,000.
    For each point in a batch, it calls the reverse_geocode API sequentially (to respect API rate limits
    and avoid simultaneous calls which may cause blocking) and accumulates the results.
    After processing each batch, it performs a bulk update to store the addresses.
    Finally, it updates the Task status to completed.
    """
    # Use a dedicated session for pagination to avoid issues with the scoped session.
    Session = sessionmaker(bind=db.engine)
    session = Session()

    task_status = TaskStatus.completed  # Default to 'completed'
    try:
        page_size = 1000
        last_id = 0

        while True:
            # Retrieve a batch of Point records (selecting only id and geom)
            batch = (
                session.query(Point.id, Point.geom)
                .filter(Point.upload_uuid == upload_uuid, Point.id > last_id)
                .order_by(Point.id)
                .limit(page_size)
                .all()
            )
            if not batch:
                break

            update_mappings = []
            for row in batch:
                point_id, geom_val = row  # row is a tuple (id, geom)
                shapely_geom = to_shape(geom_val)  # Convert to Shapely geometry
                # Call reverse_geocode sequentially using (latitude, longitude)
                address = reverse_geocode(shapely_geom.y, shapely_geom.x)
                update_mappings.append({'id': point_id, 'address': address})

            if update_mappings:
                session.bulk_update_mappings(Point, update_mappings)
                session.commit()

            last_id = batch[-1][0]  # Update the cursor with the last processed point's id
    except Exception as e:
        task_status = TaskStatus.failed
        raise
    finally:
        # Update the overall Task record to reflect the outcome of reverse geocoding.
        session.query(Task).filter_by(
            task_type=TaskType.reverse,
            status=TaskStatus.running,
            upload_uuid=upload_uuid,
        ).update({"status": task_status})
        session.commit()
        session.close()

    logger.info("Reverse geocode update completed for upload_uuid: {}", upload_uuid)
    return "Reverse geocode update completed"


@celery_app.task(bind=True)
def finalize_distance_calculations(self, results, upload_uuid):
    """
    This callback task is triggered once all child tasks for distance calculation (calculate_distance_batch)
    have completed. It updates the overall Task record for distance calculations to 'completed'.
    """
    Task.query.filter_by(
        task_type=TaskType.distance,
        status=TaskStatus.running,
        upload_uuid=upload_uuid,
    ).update(dict(status=TaskStatus.completed))
    db.session.commit()
