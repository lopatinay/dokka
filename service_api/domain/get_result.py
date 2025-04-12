from service_api.models import Point, Distance, Task, TaskType, TaskStatus


def get_result(upload_uuid):
    # Query all the points associated with this upload.
    # Each point is expected to have a 'name' and an 'address' field.
    points = Point.query.filter_by(upload_uuid=upload_uuid).all()
    points_data = [{"name": point.name, "address": point.address} for point in points]

    # Query all the distance (link) records associated with this upload.
    # The link name is constructed by concatenating the names of the two points.
    distances = Distance.query.filter_by(upload_uuid=upload_uuid).all()
    links_data = [{"name": f"{d.name_a}{d.name_b}", "distance": d.distance} for d in distances]

    # Query the task records associated with this upload.
    tasks = Task.query.filter_by(upload_uuid=upload_uuid).all()
    statuses_data = {}
    for t in tasks:
        if t.task_type == TaskType.distance:
            # Use t.status.value if t.status is an enum, or t.status directly.
            statuses_data["distance_task"] = t.status.value if hasattr(t.status, "value") else t.status
        elif t.task_type == TaskType.reverse:
            statuses_data["reverse_geocode"] = t.status.value if hasattr(t.status, "value") else t.status

    # Determine overall status:
    # If any task is failed, overall status is 'failed'.
    # If all tasks are completed, overall status is 'completed'.
    # Otherwise, we assume 'running'.
    if any(t.status == TaskStatus.failed for t in tasks):
        overall_status = "failed"
    elif all(t.status == TaskStatus.completed for t in tasks) and tasks:
        overall_status = "completed"
    else:
        overall_status = "running"

    return {
        "task_id": upload_uuid,
        "status": overall_status,
        "data": {
            "points": points_data,
            "links": links_data
        },
        "statuses": statuses_data
    }