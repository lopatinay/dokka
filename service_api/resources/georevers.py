from uuid import uuid4

from flask import Blueprint, request, jsonify

from service_api.domain.calculate_distance import save_file
from service_api.domain.get_result import get_result
from service_api.services.utils import allowed_file

api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/calculateDistances', methods=['POST'])
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
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']

    # Verify that a file was selected.
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Validate the file using the allowed_file function.
    if file and allowed_file(file.filename):
        upload_uuid = uuid4()

        save_file(file, upload_uuid)

        # Lazy import to avoid circular dependency issues.
        from service_api.tasks import process_file_tasks
        # Launch the processing task asynchronously.
        process_file_tasks.delay()

        return jsonify({
            "message": "File uploaded and tasks created successfully",
            "upload_uuid": str(upload_uuid),
            "task_status": "pending"
        }), 200

    # If the file is not allowed (i.e. the file type is invalid), return an error.
    return jsonify({"error": "Invalid file"}), 400


@api.route('/getResult/<upload_uuid>', methods=['GET'])
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