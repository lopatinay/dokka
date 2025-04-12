import os
from flask import Flask

from service_api.models import db, Upload, Point, Distance, Task
from service_api.resources.georevers import api

app = Flask(__name__)
app.register_blueprint(api)
app.config['CELERY_BROKER_URL'] = os.environ.get('CELERY_BROKER_URL', 'redis://localhost')
app.config['RESULT_BACKEND'] = os.environ.get('RESULT_BACKEND', 'redis://localhost')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:pwd@localhost/postgres')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = "statics/uploads"

db.init_app(app)
with app.app_context():
    db.create_all()


@app.route('/healthcheck')
def healthcheck():
    return "OK"
