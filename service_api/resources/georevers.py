import csv
import os
from uuid import uuid4

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text

from service_api.domain.calculate_distance import save_file
from service_api.domain.get_result import get_result
from service_api.models import Upload, db, Point
from service_api.services.utils import allowed_file

api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/runtime-distance", methods=["POST"])
def calculate_distance_in_runtime():
    """
    POST /api/runtime-distance

    This endpoint processes an uploaded CSV file containing point data in real time.
    The workflow is as follows:

      1. Validate the uploaded CSV file.
      2. Generate a unique upload ID (upload_uuid) and save the file locally.
      3. Create an Upload record in the database.
      4. Parse the CSV file and bulk insert its rows into the Point table.
      5. Immediately execute a PostGIS query via SQLAlchemy that:
         - Performs a self-join on the Point table for the given upload_uuid to generate unique point pairs,
         - Calculates the pairwise distance using PostGIS's ST_Distance function,
         - Concatenates the point names (with a dash) to form a combination name.
      6. Return the computed combinations and distances as a JSON response.

    Expected CSV format:
      Point,Latitude,Longitude
      A,50.448069,30.5194453
      B,50.448616,30.5116673
      C,50.913788,34.7828343
    """

    # Check that a file has been uploaded in the request
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    # Generate a unique UUID for this upload and save the file to the UPLOAD_FOLDER
    upload_uuid = uuid4()
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"{upload_uuid}.csv")
    file.save(save_path)

    # Create a new Upload record in the database
    upload = Upload(uuid=upload_uuid, filename=file.filename)
    db.session.add(upload)
    db.session.commit()  # Commit immediately to persist the upload record

    # Read the CSV file and prepare the data for bulk insertion into the Point table
    points_to_insert = []
    with open(save_path, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            point_name = row["Point"]
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
            # Geometry is stored as WKT in the format: "POINT(lon lat)"
            points_to_insert.append(
                {
                    "name": point_name,
                    "geom": f"POINT({lon} {lat})",
                    "upload_uuid": str(upload_uuid),
                }
            )

    if points_to_insert:
        db.session.bulk_insert_mappings(Point, points_to_insert)
        db.session.commit()

    # Use a PostGIS-enabled SQL query to generate point combinations with distances.
    # The query performs a self-join on the Point table (for the given upload_uuid) so that
    # each unique pair of points (e.g., A-B, A-C, B-C) is generated.
    # It concatenates the two point names (with a dash in between) as 'combination' and
    # calculates the distance between the two points with ST_Distance.
    query = text("""
        SELECT 
            a.name || b.name AS combination,
            ST_Distance(a.geom, b.geom) AS distance
        FROM point a
        JOIN point b ON a.id < b.id
        WHERE a.upload_uuid = :upload_uuid
    """)
    result = db.session.execute(query, {"upload_uuid": str(upload_uuid)})

    # Process the query results into a list of dictionaries
    combinations = []
    for row in result:
        combinations.append({"combination": row.combination, "distance": row.distance})

    # Return a JSON response containing the upload_uuid and the generated combinations with distances.
    return jsonify({"upload_uuid": str(upload_uuid), "combinations": combinations}), 200


@api.route("/calculateDistances", methods=["POST"])
def calculate_distance():
    """
    POST /api/calculateDistances

    This endpoint receives a CSV file containing point data and initiates the processing tasks.
    The process is as follows:
      1. Validate the incoming file.
      2. Generate a unique upload identifier (upload_uuid) and save the CSV file locally.
      3. Create an Upload record in the database with the generated upload_uuid and original filename.
      4. Create two Task records with a 'pending' status:
         - One for reverse geocoding: to convert point coordinates into human-readable addresses.
         - One for distance calculation: to compute the pairwise distances between points.
      5. Commit these records to the database.
      6. Asynchronously launch the Celery task (process_file_tasks) which reads the CSV,
         bulk inserts points, and then kicks off the reverse geocoding and distance calculation pipelines.

    The response returns a JSON object containing the upload_uuid and an initial task status.
    If the file is missing or invalid, it returns an error JSON response.
    """
    # Check if the file part exists in the request.
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]

    # Verify that a file was selected.
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Validate the file using the allowed_file function.
    if file and allowed_file(file.filename):
        upload_uuid = uuid4()

        save_file(file, upload_uuid)

        # Lazy import to avoid circular dependency issues.
        from service_api.tasks import process_file_tasks

        # Launch the processing task asynchronously.
        process_file_tasks.delay()

        return jsonify(
            {
                "message": "File uploaded and tasks created successfully",
                "upload_uuid": str(upload_uuid),
                "task_status": "pending",
            }
        ), 200

    # If the file is not allowed (i.e. the file type is invalid), return an error.
    return jsonify({"error": "Invalid file"}), 400


@api.route("/getResult/<upload_uuid>", methods=["GET"])
def get_file_result(upload_uuid):
    """
    GET /api/getResult/<upload_uuid>

    This endpoint returns the result for a given upload. It gathers all related points,
    the computed distance links, and the status of the processing tasks.

    The returned JSON has the following structure:

    {
      "task_id": "<upload_uuid>",
      "status": "<overall status>",
      "data": {
          "points": [
              { "name": "A", "address": "Some address..." },
              { "name": "B", "address": "Some address..." },
              { "name": "C", "address": "Some address..." }
          ],
          "links": [
              { "name": "AB", "distance": 350.6 },
              { "name": "BC", "distance": 125.8 },
              { "name": "AC", "distance": 1024.9 }
          ]
      },
      "statuses": {
          "distance_task": "<status>",
          "reverse_geocode": "<status>"
      }
    }

    The overall status is determined by aggregating the statuses of individual tasks:
      - 'completed' if all tasks are completed,
      - 'failed' if any task failed,
      - 'running' otherwise.

    Note: This endpoint uses the upload_uuid as the task ID.
    """
    result = get_result(upload_uuid)

    return jsonify(result), 200
