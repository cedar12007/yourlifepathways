from flask_sqlalchemy import SQLAlchemy

# We do not pass "app" here yet.
# It stays "unattached" until index.py calls db.init_app(app).
db = SQLAlchemy()