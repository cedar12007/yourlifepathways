from flask_sqlalchemy import SQLAlchemy
from concurrent.futures import ThreadPoolExecutor

# We do not pass "app" here yet.
# It stays "unattached" until index.py calls db.init_app(app).
db = SQLAlchemy()

# Shared executor for background tasks (email, logging, etc)
executor = ThreadPoolExecutor(max_workers=4)