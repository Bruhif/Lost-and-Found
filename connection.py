import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

import secrets
from datetime import datetime, timedelta
from unittest import result
from functools import wraps
from contextlib import contextmanager
import uuid

import jwt

from flask import Flask, render_template, request, jsonify, send_from_directory, g
from flask_cors import CORS
import psycopg2

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
CORS(app)

DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_CONFIG = {
    "host": "100.121.226.108",
    "port": 5432,
    "database": "lnf",
    "user": "teentin",
    "password": DB_PASSWORD
}

# Secret used to sign session tokens. Preferred: set the JWT_SECRET
# environment variable (e.g. in your TrueNAS app's env config) — never
# commit a real secret to source control.
#
# Fallback: if JWT_SECRET isn't set, generate one and persist it to a local
# file so restarts don't invalidate every logged-in session. This file
# should NOT be committed to git or shared — add it to .gitignore.
_SECRET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".jwt_secret")


def _load_or_create_secret():
    env_secret = os.getenv("JWT_SECRET")
    if env_secret:
        return env_secret

    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE, "r") as f:
            return f.read().strip()

    new_secret = secrets.token_hex(32)
    with open(_SECRET_FILE, "w") as f:
        f.write(new_secret)
    os.chmod(_SECRET_FILE, 0o600)  # readable/writable by the owner only
    return new_secret


JWT_SECRET = _load_or_create_secret()
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24


def generate_token(payload):
    to_encode = dict(payload)
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def require_auth(role=None):
    """
    Decorator for routes that need a logged-in user or admin.
    Reads 'Authorization: Bearer <token>', verifies it, and stashes the
    decoded claims on flask.g so the route can use g.user_id / g.usertype
    (or g.admin_id for admin tokens) instead of trusting anything the
    client sent in the request body/query string.

    role=None    -> any valid token (user or admin) is accepted
    role="admin" -> only a token issued by /admin/login is accepted
    role="user"  -> only a token issued by /login is accepted
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")

            if not auth_header.startswith("Bearer "):
                return jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401

            token = auth_header[len("Bearer "):]

            try:
                claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            except jwt.ExpiredSignatureError:
                return jsonify({"success": False, "error": "Session expired, please log in again"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"success": False, "error": "Invalid session token"}), 401

            token_role = claims.get("role")

            if role and token_role != role:
                return jsonify({"success": False, "error": "Not authorized for this action"}), 403

            g.claims = claims
            g.user_id = claims.get("user_id")
            g.usertype = claims.get("usertype")
            g.admin_id = claims.get("admin_id")

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_json_body():
    """
    Like request.get_json(), but never lets a technically-valid-but-wrong-
    shaped JSON body (literal null, an array, a bare number/string) reach
    route code that assumes it can call .get() on the result. Returns None
    if the body isn't a JSON object; routes should check for that and
    return a 400 rather than crashing with an unhandled AttributeError.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    return data


@contextmanager
def db_cursor():
    """
    Use as: with db_cursor() as (conn, cursor): ...

    Guarantees the connection and cursor are ALWAYS closed, whether the
    route finishes normally or raises — the old pattern of manually calling
    cursor.close()/conn.close() only in the success path meant every error
    leaked an open connection to Postgres. Also auto-commits when the block
    finishes without error, and auto-rolls-back if it raises, so a
    partially-completed multi-step insert (e.g. add_student's Users row
    followed by its student row) doesn't leave a dangling uncommitted
    transaction either.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "Welcome to the Flask backend!"
    })

@app.route("/test", methods=["GET"])
def test():
    return jsonify({
        "success": True,
        "message": "Flask backend is working!"
    })

@app.route("/debug/routes", methods=["GET"])
def debug_routes():
    return jsonify(sorted([str(rule) for rule in app.url_map.iter_rules()]))

@app.route("/send-email", methods=["POST"])
def send_email():
    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    email = data.get("email")

    if not email:
        return jsonify({
            "success": False,
            "error": "Email is required"
        })

    code = str(secrets.randbelow(1000000)).zfill(6)
    expires_at = datetime.now() + timedelta(minutes=10)

    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return jsonify({
            "success": False,
            "error": "Email credentials are not set in environment variables"
        })

    msg = EmailMessage()

    msg["Subject"] = "LnF - Email Verification"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = email

    msg.set_content(
        f"""
        Your verification code is: {code}
        """
    )

    try:
        with db_cursor() as (conn, cursor):
            # Clear out old/expired verification rows before inserting a new one
            cursor.execute("""
                DELETE FROM emailverification
                WHERE expiresat < NOW()
                OR (verified = TRUE AND createdat < NOW() - INTERVAL '1 hour');
            """)

            query = """
                INSERT INTO emailverification (email, code, createdat, expiresat, verified)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING verificationid;
            """

            values = (
                email,
                code,
                datetime.now(),
                expires_at,
                False
            )

            cursor.execute(query, values)
            verification_id = cursor.fetchone()[0]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        return jsonify({
            "success": True,
            "message": "Verification email sent successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/verify-email", methods=["POST"])
def verify_email():

    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({
            "success": False,
            "error": "Email and code are required"
        }), 400

    try:
        with db_cursor() as (conn, cursor):
            query = """
                SELECT verificationid, code, expiresat, verified
                FROM emailverification
                WHERE email = %s
                ORDER BY verificationid DESC
                LIMIT 1;
            """

            cursor.execute(query, (email,))
            verification = cursor.fetchone()

            if not verification:
                return jsonify({
                    "success": False,
                    "error": "No verification code found for this email"
                }), 400

            verification_id = verification[0]
            stored_code = verification[1]
            expires_at = verification[2]
            verified = verification[3]

            if verified:
                return jsonify({
                    "success": False,
                    "error": "Email has already been verified"
                }), 400

            if datetime.now() > expires_at:
                return jsonify({
                    "success": False,
                    "error": "Verification code has expired"
                }), 400

            if code != stored_code:
                return jsonify({
                    "success": False,
                    "error": "Invalid verification code"
                }), 400

            update_query = """
                UPDATE emailverification
                SET verified = TRUE
                WHERE verificationid = %s;
            """

            cursor.execute(update_query, (verification_id,))

        return jsonify({
            "success": True,
            "message": "Email verified successfully"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ---------- Rate limiting (5 attempts per minute per IP) ----------
# Simple in-memory tracker — no new dependency required. Good enough for a
# single-process dev/class-project deployment; note for the writeup that
# this resets on restart and wouldn't scale past one server process, since
# the attempt counts live in this process's memory, not a shared store.
from collections import defaultdict

_login_attempts = defaultdict(list)  # { ip_address: [timestamp, timestamp, ...] }
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60

def check_rate_limit(ip_address):
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)

    # Drop timestamps older than the window before counting
    _login_attempts[ip_address] = [
        t for t in _login_attempts[ip_address] if t > window_start
    ]

    if len(_login_attempts[ip_address]) >= RATE_LIMIT_MAX_ATTEMPTS:
        return False

    _login_attempts[ip_address].append(now)
    return True

# ---------- Timing-safe comparison ----------
# A fixed, valid password hash with no real matching password. When no
# user/admin is found, we still run check_password_hash against this, so
# a nonexistent username takes the same time to reject as a wrong password
# on a real one — the response time itself can't be used to tell which.
_DECOY_HASH = generate_password_hash(str(uuid.uuid4()))


@app.route("/login", methods=["POST"])
def login():
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    if not check_rate_limit(ip_address):
        return jsonify({
            "success": False,
            "error": "Too many login attempts. Please wait a minute and try again."
        }), 429

    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required"
        }), 400

    try:
        with db_cursor() as (conn, cursor):
            query = """
                SELECT userid, username, email, usertype, password
                FROM Users
                WHERE username = %s;
            """

            cursor.execute(query, (username,))
            user = cursor.fetchone()

            admin_query = """
                SELECT adminid, adminname, adminnumber, password, adminemail
                FROM admin
                WHERE adminname = %s;
            """

            cursor.execute(admin_query, (username,))
            admin = cursor.fetchone()

        if user:
            password_ok = check_password_hash(user[4], password)
        elif admin:
            password_ok = check_password_hash(admin[3], password)
        else:
            # Neither table matched — still do a hash comparison against the
            # decoy so this branch takes the same time as a real mismatch.
            check_password_hash(_DECOY_HASH, password)
            password_ok = False

        if user and password_ok:
            token = generate_token({
                "user_id": user[0],
                "usertype": user[3],
                "role": "user"
            })
            return jsonify({
                "success": True,
                "token": token,
                "user": {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "usertype": user[3]
                }
            })
        elif admin and password_ok:
            token = generate_token({
                "admin_id": admin[0],
                "role": "admin"
            })
            return jsonify({
                "success": True,
                "token": token,
                "admin": {
                    "id": admin[0],
                    "name": admin[1],
                    "number": admin[2],
                    "email": admin[4],
                    "usertype": "admin"
                }
            })
        else:
            return jsonify({"success": False, "error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/add/student", methods=["POST"])
def add_student():
    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    name = data.get("username")
    email = data.get("email")
    password = data.get("password")
    number = data.get("phone_number")
    usertype = data.get("usertype")
    department = data.get("department")
    year = data.get("year")

    if not name or not email or not password or not number or not department or not year:
        return jsonify({
            "success": False,
            "error": "All fields are required"
        }), 400

    hashed_password = generate_password_hash(password)

    try:
        with db_cursor() as (conn, cursor):
            verify_query = """
                SELECT verified
                FROM emailverification
                WHERE email = %s
                ORDER BY verificationid DESC
                LIMIT 1;
            """

            cursor.execute(verify_query, (email,))
            verification = cursor.fetchone()

            if not verification or not verification[0]:
                return jsonify({
                    "success": False,
                    "error": "Email is not verified"
                }), 400

            userquery = """
                INSERT INTO Users (username, email, password, phone_number, usertype)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING userid;
            """

            values = (
                name,
                email,
                hashed_password,
                number,
                usertype
            )

            cursor.execute(userquery, values)
            user_id = cursor.fetchone()[0]

            studentquery = """
                INSERT INTO student (userid, student_department, student_year)
                VALUES (%s, %s, %s)
                RETURNING userid;
            """

            student_values = (
                user_id,
                department,
                year
            )

            cursor.execute(studentquery, student_values)
            student_id = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "id": user_id,
            "student_id": student_id,
            "name": name,
            "email": email
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/add/lecturer", methods=["POST"])
def add_lecturer():
    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    name = data.get("username")
    email = data.get("email")
    password = data.get("password")
    number = data.get("phone_number")
    usertype = data.get("usertype")
    department = data.get("department")

    if not name or not email or not password or not number or not department:
        return jsonify({
            "success": False,
            "error": "All fields are required"
        }), 400

    hashed_password = generate_password_hash(password)

    try:
        with db_cursor() as (conn, cursor):
            verify_query = """
                SELECT verified
                FROM emailverification
                WHERE email = %s
                ORDER BY verificationid DESC
                LIMIT 1;
            """

            cursor.execute(verify_query, (email,))
            verification = cursor.fetchone()

            if not verification or not verification[0]:
                return jsonify({
                    "success": False,
                    "error": "Email is not verified"
                }), 400

            userquery = """
                INSERT INTO Users (username, email, password, phone_number, usertype)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING userid;
            """

            values = (
                name,
                email,
                hashed_password,
                number,
                usertype
            )

            cursor.execute(userquery, values)
            user_id = cursor.fetchone()[0]

            lecturerquery = """
                INSERT INTO lecturer (userid, lecturer_department)
                VALUES (%s, %s)
                RETURNING userid;
            """

            lecturer_values = (
                user_id,
                department
            )

            cursor.execute(lecturerquery, lecturer_values)
            lecturer_id = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "id": user_id,
            "lecturer_id": lecturer_id,
            "name": name,
            "email": email
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/add/community", methods=["POST"])
def add_community():
    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    name = data.get("username")
    email = data.get("email")
    password = data.get("password")
    number = data.get("phone_number")
    usertype = data.get("usertype")
    # NOTE: frontend now sends this as "role", not "department" — updated to match.
    role = data.get("role")

    if not name or not email or not password or not number or not role:
        return jsonify({
            "success": False,
            "error": "All fields are required"
        }), 400

    hashed_password = generate_password_hash(password)

    try:
        with db_cursor() as (conn, cursor):
            verify_query = """
                SELECT verified
                FROM emailverification
                WHERE email = %s
                ORDER BY verificationid DESC
                LIMIT 1;
            """

            cursor.execute(verify_query, (email,))
            verification = cursor.fetchone()

            if not verification or not verification[0]:
                return jsonify({
                    "success": False,
                    "error": "Email is not verified"
                }), 400

            userquery = """
                INSERT INTO Users (username, email, password, phone_number, usertype)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING userid;
            """

            values = (
                name,
                email,
                hashed_password,
                number,
                usertype
            )

            cursor.execute(userquery, values)
            user_id = cursor.fetchone()[0]

            communityquery = """
                INSERT INTO community (userid, community_role)
                VALUES (%s, %s)
                RETURNING userid;
            """

            community_values = (
                user_id,
                role
            )

            cursor.execute(communityquery, community_values)
            community_id = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "id": user_id,
            "community_id": community_id,
            "name": name,
            "email": email
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/items", methods=["GET"])
def get_items():
    try:
        with db_cursor() as (conn, cursor):
            # Once an item has an approved claim, it's resolved — hide it
            # from the active listing instead of leaving it cluttering
            # Browse/All Reports forever. (The claimant still sees it via
            # their own /claims/me — this only affects the items list.)
            cursor.execute(
                """
                SELECT i.itemid, i.category, i.status, i.image, i.location, i.date, i.reportedbyuserid, u.username
                FROM itemlist i
                LEFT JOIN users u ON i.reportedbyuserid = u.userid
                WHERE NOT EXISTS (
                    SELECT 1 FROM claims c
                    WHERE c.itemid = i.itemid AND c.claimstatus = 'Approved'
                )
                ORDER BY i.date DESC;
                """
            )
            rows = cursor.fetchall()

        return jsonify([
            {
                "itemID": row[0],
                "category": row[1],
                "status": row[2],
                "image": row[3],
                "location": row[4],
                "date": row[5].isoformat() if row[5] else None,
                "reportedByUserID": row[6],
                "reportedByUsername": row[7]
            }
            for row in rows
        ])

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/admin/items", methods=["GET"])
@require_auth(role="admin")
def get_admin_items():
    try:
        with db_cursor() as (conn, cursor):
            # Unlike the public /items list, admins should see every report —
            # including ones with an approved claim — so nothing is filtered out.
            cursor.execute(
                """
                SELECT i.itemid, i.category, i.status, i.image, i.location, i.date,
                       i.reportedbyuserid, u.username, u.email, u.phone_number
                FROM itemlist i
                LEFT JOIN users u ON i.reportedbyuserid = u.userid
                ORDER BY i.date DESC;
                """
            )
            rows = cursor.fetchall()

        return jsonify([
            {
                "itemID": row[0],
                "category": row[1],
                "status": row[2],
                "image": row[3],
                "location": row[4],
                "date": row[5].isoformat() if row[5] else None,
                "reportedByUserID": row[6],
                "reportedByUsername": row[7],
                "reportedByEmail": row[8],
                "reportedByPhone": row[9]
            }
            for row in rows
        ])

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/debug/schema", methods=["GET"])
def debug_schema():
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'itemlist';
            """)
            columns = cursor.fetchall()

        return jsonify([{"column": c[0], "type": c[1]} for c in columns])

    except Exception as e:
        return jsonify({"error": str(e)}), 500

UPLOAD_FOLDER = "uploads"  # make sure this folder exists next to your Flask file
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def save_uploaded_image(image_file):
    """
    Saves an uploaded image and returns its public URL, or None if no file
    was provided. Raises a plain Exception (caught by the caller's existing
    try/except) on any failure, instead of letting it crash the request
    unhandled the way the old inline version did.

    Prefixes every filename with a random hex string so two different
    uploads that happen to share an original filename (very common with
    phone photos, e.g. "IMG_0001.jpg") never collide and overwrite each
    other on disk.
    """
    if not image_file or not image_file.filename:
        return None

    original_name = secure_filename(image_file.filename)
    if not original_name:
        raise ValueError("Uploaded file has an invalid or empty filename.")

    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    image_file.save(save_path)
    # request.host_url is "http://..." because the Tailscale tunnel terminates
    # TLS and forwards to Flask over plain HTTP — Flask never sees the https
    # the browser actually used. Force it so links we hand back don't 404/refuse.
    host = request.host_url.replace("http://", "https://", 1)
    return f"{host}uploads/{unique_name}"

@app.route("/add/lost", methods=["POST"])
@require_auth(role="user")
def add_lost():
    category = request.form.get("category")
    status = request.form.get("status", "Lost")
    date = request.form.get("date")
    location = request.form.get("location") or None  # optional — the person may not know
    reportedbyuserid = g.user_id  # from the verified token, not the form body

    if not category or not status or not date:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    try:
        image_path = save_uploaded_image(request.files.get("image"))

        with db_cursor() as (conn, cursor):
            query = """
                INSERT INTO itemlist (category, status, date, image, location, reportedbyuserid)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING itemid;
            """
            values = (category, status, date, image_path, location, reportedbyuserid)
            cursor.execute(query, values)
            item_id = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "message": "Lost item reported successfully.",
            "itemID": item_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/add/found", methods=["POST"])
@require_auth(role="user")
def add_found():
    category = request.form.get("category")
    location = request.form.get("location")
    date = request.form.get("date")
    status = request.form.get("status", "Found")
    reportedbyuserid = g.user_id  # from the verified token, not the form body

    if not category or not location or not date:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    try:
        image_path = save_uploaded_image(request.files.get("image"))

        with db_cursor() as (conn, cursor):
            query = """
                INSERT INTO itemlist (category, status, location, date, image, reportedbyuserid)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING itemid;
            """
            values = (category, status, location, date, image_path, reportedbyuserid)
            cursor.execute(query, values)
            item_id = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "message": "Found item reported successfully.",
            "itemID": item_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Serves the uploaded images back out so <img src="..."> tags can load them
@app.route("/uploads/<filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------- Delete an item report ----------
# Now requires a valid session token — the acting user comes from the
# verified token (g.user_id), not from anything the client sends in the
# request body, so it can no longer be spoofed via localStorage.
@app.route("/items/<int:item_id>", methods=["DELETE"])
@require_auth(role="user")
def delete_item(item_id):
    requesting_user_id = g.user_id

    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "SELECT reportedbyuserid FROM itemlist WHERE itemid = %s;",
                (item_id,)
            )
            row = cursor.fetchone()

            if not row:
                return jsonify({"success": False, "error": "Item not found"}), 404

            actual_owner_id = row[0]

            if str(actual_owner_id) != str(requesting_user_id):
                return jsonify({"success": False, "error": "You are not authorized to delete this item"}), 403

            cursor.execute("DELETE FROM itemlist WHERE itemid = %s RETURNING itemid;", (item_id,))
            deleted = cursor.fetchone()

        return jsonify({"success": True, "message": "Item deleted successfully."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims", methods=["POST"])
@require_auth(role="user")
def add_claim():
    # The frontend sends this as FormData (it includes the verification photo
    # taken via the camera), i.e. multipart/form-data — not JSON — so this
    # reads request.form/request.files like add_lost/add_found do, instead of
    # get_json_body(), which was rejecting every claim submission.
    itemid = request.form.get("itemid")
    claimuserid = g.user_id  # from the verified token, not the request body
    verificationnotes = request.form.get("verificationnotes")
    claimdate = request.form.get("claimdate")
    claimstatus = request.form.get("claimstatus", "Pending")

    if not itemid or not claimdate:
        return jsonify({"success": False, "error": "Required fields missing"}), 400

    idcard_file = request.files.get("idcard")
    if not idcard_file or not idcard_file.filename:
        return jsonify({"success": False, "error": "Student ID card photo is required"}), 400

    try:
        verificationphoto = save_uploaded_image(request.files.get("image"))
        studentidcard = save_uploaded_image(idcard_file)

        with db_cursor() as (conn, cursor):
            query = """
                INSERT INTO claims (itemid, claimuserid, verificationnotes, claimdate, claimstatus, verificationphoto, studentidcard)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING claimid;
            """
            cursor.execute(query, (itemid, claimuserid, verificationnotes, claimdate, claimstatus, verificationphoto, studentidcard))
            claim_id = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "message": "Claim submitted successfully.",
            "claimID": claim_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims/me", methods=["GET"])
@require_auth(role="user")
def get_user_claims():
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                """
                SELECT claimid, itemid, claimuserid, verificationnotes, claimdate, claimstatus, verificationphoto, studentidcard
                FROM claims
                WHERE claimuserid = %s
                ORDER BY claimdate DESC;
                """,
                (g.user_id,)
            )
            rows = cursor.fetchall()

        return jsonify([
            {
                "claimid": r[0], "itemid": r[1], "claimuserid": r[2],
                "verificationnotes": r[3],
                "claimdate": r[4].isoformat() if r[4] else None, "claimstatus": r[5],
                "verificationPhoto": r[6], "studentIDCard": r[7]
            }
            for r in rows
        ])

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims/pending", methods=["GET"])
@require_auth(role="admin")
def get_pending_claims():
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                """
                SELECT c.claimid, c.itemid, c.claimuserid, c.verificationnotes, c.claimdate, c.claimstatus, c.verificationphoto, c.studentidcard,
                       i.image, i.category, u.username, u.email, u.phone_number
                FROM claims c
                JOIN itemlist i ON c.itemid = i.itemid
                JOIN users u ON c.claimuserid = u.userid
                WHERE c.claimstatus = 'Pending'
                ORDER BY c.claimdate ASC;
                """
            )
            rows = cursor.fetchall()

        return jsonify([
            {
                "claimid": r[0], "itemid": r[1], "claimuserid": r[2],
                "verificationnotes": r[3],
                "claimdate": r[4].isoformat() if r[4] else None, "claimstatus": r[5],
                "verificationPhoto": r[6], "studentIDCard": r[7],
                "itemImage": r[8], "itemCategory": r[9], "claimantUsername": r[10],
                "claimantEmail": r[11], "claimantPhone": r[12]
            }
            for r in rows
        ])

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def send_claim_notification(to_email, approved, category):
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return

    msg = EmailMessage()
    msg["Subject"] = "LnF - Claim Update"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    if approved:
        msg.set_content(
            f"Good news! Your claim for '{category}' has been approved.\n\n"
            f"Please come to the library during office hours 08:00-17:00 to collect your item. Bring a valid ID for verification."
        )
    else:
        msg.set_content(f"Your claim for '{category}' was not approved. Contact the admin office for details.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        pass

def _review_claim(claim_id, new_status):
    verifiedby = g.admin_id  # from the verified admin token, not the request body

    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                """
                SELECT c.itemid, u.email, i.category
                FROM claims c
                JOIN users u ON c.claimuserid = u.userid
                JOIN itemlist i ON c.itemid = i.itemid
                WHERE c.claimid = %s;
                """,
                (claim_id,)
            )
            row = cursor.fetchone()

            if not row:
                return jsonify({"success": False, "error": "Claim not found"}), 404

            itemid, claimant_email, category = row

            competing_emails = []
            if new_status == "Approved":
                # Auto-reject every other still-pending claim on this same
                # item — that's the whole point of letting multiple people
                # claim it: the admin picks the real owner and everyone
                # else's claim resolves automatically instead of sitting in
                # limbo forever. Collect their emails while we still have
                # the join available, so we can notify them too.
                cursor.execute(
                    """
                    SELECT u.email
                    FROM claims c
                    JOIN users u ON c.claimuserid = u.userid
                    WHERE c.itemid = %s AND c.claimid != %s AND c.claimstatus = 'Pending';
                    """,
                    (itemid, claim_id)
                )
                competing_emails = [r[0] for r in cursor.fetchall()]

                cursor.execute(
                    "UPDATE claims SET claimstatus = 'Rejected' WHERE itemid = %s AND claimid != %s AND claimstatus = 'Pending';",
                    (itemid, claim_id)
                )

            cursor.execute(
                "UPDATE claims SET claimstatus = %s, verifiedby = %s WHERE claimid = %s;",
                (new_status, verifiedby, claim_id)
            )

            # itemlist.status only allows 'Lost'/'Found' — only touch it on rejection,
            # to put the item back to Found. On approval, leave itemlist.status alone;
            # claim state (Pending/Approved/Rejected) already lives in claims.claimstatus.
            if new_status == "Rejected":
                cursor.execute("UPDATE itemlist SET status = %s WHERE itemid = %s;", ("Found", itemid))

        send_claim_notification(claimant_email, new_status == "Approved", category)
        for competitor_email in competing_emails:
            send_claim_notification(competitor_email, False, category)

        return jsonify({"success": True, "message": f"Claim {new_status.lower()}."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims/<int:claim_id>/approve", methods=["POST"])
@require_auth(role="admin")
def approve_claim(claim_id):
    return _review_claim(claim_id, "Approved")

@app.route("/claims/<int:claim_id>/reject", methods=["POST"])
@require_auth(role="admin")
def reject_claim(claim_id):
    return _review_claim(claim_id, "Rejected")

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = get_json_body()
    if data is None:
        return jsonify({"success": False, "error": "Request body must be a JSON object"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    try:
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "SELECT adminid, adminname, adminemail, password FROM admin WHERE adminemail = %s;",
                (email,)
            )
            admin = cursor.fetchone()

        if admin and check_password_hash(admin[3], password):
            token = generate_token({
                "admin_id": admin[0],
                "role": "admin"
            })
            return jsonify({
                "success": True,
                "token": token,
                "admin": {
                    "id": admin[0],
                    "name": admin[1],
                    "email": admin[2]
                }
            })
        else:
            return jsonify({"success": False, "error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )