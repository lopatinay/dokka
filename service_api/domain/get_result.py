from service_api.models import Point, Distance, Task, TaskType, TaskStatus


def get_result(upload_uuid):
    points_data = _get_points_data(upload_uuid)
    links_data = _get_links_data(upload_uuid)
    tasks = _get_tasks(upload_uuid)
    statuses_data = _extract_statuses(tasks)
    overall_status = _determine_overall_status(tasks)

    return {
        "task_id": upload_uuid,
        "status": overall_status,
        "data": {"points": points_data, "links": links_data},
        "statuses": statuses_data,
    }


def _get_points_data(upload_uuid):
    points = Point.query.filter_by(upload_uuid=upload_uuid).all()
    return [{"name": point.name, "address": point.address} for point in points]


def _get_links_data(upload_uuid):
    distances = Distance.query.filter_by(upload_uuid=upload_uuid).all()
    return [
        {"name": f"{d.name_a}{d.name_b}", "distance": d.distance} for d in distances
    ]


def _get_tasks(upload_uuid):
    return Task.query.filter_by(upload_uuid=upload_uuid).all()


def _extract_statuses(tasks):
    statuses = {}
    for task in tasks:
        if task.task_type == TaskType.distance:
            statuses["distance_task"] = task.status
        elif task.task_type == TaskType.reverse:
            statuses["reverse_geocode"] = task.status
    return statuses


def _determine_overall_status(tasks):
    if any(t.status == TaskStatus.failed for t in tasks):
        return "failed"
    elif all(t.status == TaskStatus.completed for t in tasks) and tasks:
        return "completed"
    return "running"
