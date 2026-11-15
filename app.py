
import os
import hmac
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

database_url = os.environ.get("DATABASE_URL", "").strip()

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Local development only. Vercel's filesystem is not persistent.
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///portfolio.db"

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("VERCEL") == "1",
)

# Only enable proxy fix when deployed behind a trusted platform proxy.
if os.environ.get("VERCEL") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db = SQLAlchemy(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Web Development")
    tech_stack = db.Column(db.String(300), nullable=False, default="")
    project_url = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    subject = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def valid_external_url(value):
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in ("https", "http") and bool(parsed.netloc)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.context_processor
def inject_portfolio_settings():
    return {
        "portfolio_name": os.environ.get("PORTFOLIO_NAME", "Alex Morgan"),
        "portfolio_role": os.environ.get(
            "PORTFOLIO_ROLE", "Student • Developer • Creator"
        ),
    }


@app.get("/")
def home():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("index.html", projects=projects)


@app.get("/api/projects")
def api_projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify([
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "category": p.category,
            "tech_stack": p.tech_stack,
            "project_url": p.project_url,
        }
        for p in projects
    ])


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(status="error", database="unavailable"), 503


@app.post("/contact")
@limiter.limit("5 per hour")
def contact():
    # Simple honeypot: bots often fill hidden fields.
    if request.form.get("website", "").strip():
        return redirect(url_for("home") + "#contact")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    if not all((name, email, subject, message)):
        flash("Please complete every field.", "error")
        return redirect(url_for("home") + "#contact")

    if (
        len(name) > 120
        or len(email) > 254
        or len(subject) > 180
        or len(message) > 5000
        or "@" not in email
        or "\n" in email
    ):
        flash("Please check your details and try again.", "error")
        return redirect(url_for("home") + "#contact")

    try:
        db.session.add(ContactMessage(
            name=name,
            email=email,
            subject=subject,
            message=message,
        ))
        db.session.commit()
        flash("Message received! Thanks for reaching out.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Unable to save contact message")
        flash("We couldn't save your message. Please try again later.", "error")

    return redirect(url_for("home") + "#contact")


@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        expected_username = os.environ.get("ADMIN_USERNAME", "")
        expected_password = os.environ.get("ADMIN_PASSWORD", "")

        # Admin credentials must be configured in the environment.
        valid = (
            bool(expected_username)
            and bool(expected_password)
            and hmac.compare_digest(username, expected_username)
            and hmac.compare_digest(password, expected_password)
        )

        if valid:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid credentials.", "error")

    return render_template("login.html")


@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    messages = ContactMessage.query.order_by(
        ContactMessage.created_at.desc()
    ).all()
    return render_template("admin.html", projects=projects, messages=messages)


@app.post("/admin/projects")
@admin_required
def create_project():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "Web Development").strip()
    tech_stack = request.form.get("tech_stack", "").strip()
    project_url = request.form.get("project_url", "").strip()

    if (
        not title or not description
        or len(title) > 160
        or len(description) > 3000
        or len(category) > 80
        or len(tech_stack) > 300
        or len(project_url) > 500
        or not valid_external_url(project_url)
    ):
        flash("Please check the project fields and URL.", "error")
        return redirect(url_for("admin_dashboard"))

    db.session.add(Project(
        title=title,
        description=description,
        category=category or "Web Development",
        tech_stack=tech_stack,
        project_url=project_url,
    ))
    db.session.commit()
    flash("Project added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/projects/<int:project_id>/delete")
@admin_required
def delete_project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("base.html", page_title="Page not found"), 404


with app.app_context():
    try:
        db.create_all()
    except SQLAlchemyError:
        # Keep the app importable during a temporary database outage.
        app.logger.exception("Database initialization failed")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
