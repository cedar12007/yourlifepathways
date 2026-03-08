from datetime import datetime, timezone
from sqlalchemy.sql import func
from extensions import db
from utils import slugify
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    login_history = db.relationship('LoginHistory', backref='user', lazy=True)


class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username_attempted = db.Column(db.String(150))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    status = db.Column(db.String(20))  # 'success', 'failed'
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())


class Post(db.Model):
    __tablename__ = 'posts'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=True)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    category = db.Column(db.String(100))

    # NEW COLUMNS
    is_featured = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False, index=True)  # Index makes filtering fast

    # TIMESTAMPS
    # server_default=func.now() lets Postgres handle the initial time
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # onupdate=func.now() automatically updates the time whenever the row is edited
    updated_date = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # RELATIONSHIPS
    likes_data = db.relationship('PostLike', backref='parent', lazy='dynamic', cascade="all, delete-orphan")
    shares_data = db.relationship('PostShare', backref='parent', lazy='dynamic', cascade="all, delete-orphan")
    views_data = db.relationship('PostView', backref='parent', lazy='dynamic', cascade="all, delete-orphan")

    comments = db.relationship('Comment', backref='post', lazy=True)


    def __init__(self, **kwargs):
        super(Post, self).__init__(**kwargs)
        if not self.slug:
            self.slug = slugify(self.title)

class PostLike(db.Model):
    __tablename__ = 'post_likes'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    visitor_ip = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
    is_deleted = db.Column(db.Boolean, default=False, index=True)


class PostShare(db.Model):
    __tablename__ = 'post_shares'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    visitor_ip = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())


class PostView(db.Model):
    __tablename__ = 'post_views'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    visitor_ip = db.Column(db.String(45))
    visitor_location = db.Column(db.String(255))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

class SiteVisit(db.Model):
    __tablename__ = 'site_visits'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500))
    visitor_ip = db.Column(db.String(45))
    visitor_location = db.Column(db.String(255))
    user_agent = db.Column(db.Text)
    referrer = db.Column(db.Text)  # Added for tracking source
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)  # Added optional email
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_approved = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    # Relationship for replies
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')


class ManualBot(db.Model):
    __tablename__ = 'manual_bots'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False, index=True)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
