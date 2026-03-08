Structure:
yourlifepathways/
├── index.py            # Main entry point (formerly run.py)
├── extensions.py       # Shared SQLAlchemy object
├── models.py           # Database classes
├── routes_blog.py      # Blog logic
├── routes_main.py      # Home & Email logic
└── templates/          # HTML files

Dev Notes:
python -m pip install --upgrade pip
pip install flask-sqlalchemy --only-binary :all:

Database:
Supabase - postgres

pip install psycopg2-binary