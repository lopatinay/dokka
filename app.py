from flask import Flask

from service_api.models import db, Upload, Point, Distance, Task
from service_api.resources.georevers import api
from service_api.settings import DevelopmentConfig

app = Flask(__name__)
app.register_blueprint(api)
app.config.from_object(DevelopmentConfig)


# In a real project, I would do migrations using `flask-migrate` or pure `alembic`
# but for a test solution I think it will do
db.init_app(app)
with app.app_context():
    db.create_all()


@app.route('/healthcheck')
def healthcheck():
    return "OK"
