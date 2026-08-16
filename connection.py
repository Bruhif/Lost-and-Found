import smtplib
from email.message import EmailMessage
import os

import secrets
from datetime import datetime, timedelta
from unittest import result

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    "host": "100.121.226.108",
    "port": 5432,
    "database": "lnf",
    "user": "teentin",
    "password": "1712"
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)

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
    data = request.get_json()

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
        conn = get_connection()
        cursor = conn.cursor()

        # Clear out old/expired verification rows before inserting a new one
        cursor.execute("""
            DELETE FROM emailverification
            WHERE expiresat < NOW()
            OR (verified = TRUE AND createdat < NOW() - INTERVAL '1 hour');
        """)

        conn.commit()

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

        conn.commit()

        cursor.close()

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

    data = request.get_json()

    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({
            "success": False,
            "error": "Email and code are required"
        }), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

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
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "No verification code found for this email"
            }), 400

        verification_id = verification[0]
        stored_code = verification[1]
        expires_at = verification[2]
        verified = verification[3]

        if verified:
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "Email has already been verified"
            }), 400

        if datetime.now() > expires_at:
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "Verification code has expired"
            }), 400

        if code != stored_code:
            cursor.close()
            conn.close()

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

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Email verified successfully"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required"
        }), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT userid, username, email, usertype, password
            FROM Users
            WHERE username = %s;
        """

        cursor.execute(query, (username,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            if check_password_hash(user[4], password):
                return jsonify({
                    "success": True,
                    "user": {
                        "id": user[0],
                        "name": user[1],
                        "email": user[2],
                        "usertype": user[3]
                    }
                })
            else:
                return jsonify({"success": False, "error": "Invalid credentials"}), 401
        else:
            return jsonify({"success": False, "error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/add/student", methods=["POST"])
def add_student():
    data = request.get_json()

    name = data.get("username")
    email = data.get("email")
    hashed_password = generate_password_hash(data.get("password"))
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

    try:
        conn = get_connection()
        cursor = conn.cursor()

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
            cursor.close()
            conn.close()

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
        conn.commit()

        cursor.close()
        conn.close()

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
    data = request.get_json()

    name = data.get("username")
    email = data.get("email")
    hashed_password = generate_password_hash(data.get("password"))
    password = data.get("password")
    number = data.get("phone_number")
    usertype = data.get("usertype")
    department = data.get("department")

    if not name or not email or not password or not number or not department:
        return jsonify({
            "success": False,
            "error": "All fields are required"
        }), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

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
            cursor.close()
            conn.close()

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
        conn.commit()

        cursor.close()
        conn.close()

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
    data = request.get_json()

    name = data.get("username")
    email = data.get("email")
    hashed_password = generate_password_hash(data.get("password"))
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

    try:
        conn = get_connection()
        cursor = conn.cursor()

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
            cursor.close()
            conn.close()

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
        conn.commit()

        cursor.close()
        conn.close()

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
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT itemid, category, status, image, location, date, reportedbyuserid
            FROM itemlist order by date desc;
            """
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify([
            {
                "itemID": row[0],
                "category": row[1],
                "status": row[2],
                "image": row[3],
                "location": row[4],
                "date": row[5].isoformat() if row[5] else None,
                "reportedByUserID": row[6]
            }
            for row in rows
        ])

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/debug/schema", methods=["GET"])
def debug_schema():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'itemlist';
        """)

        columns = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify([{"column": c[0], "type": c[1]} for c in columns])

    except Exception as e:
        return jsonify({"error": str(e)}), 500

UPLOAD_FOLDER = "uploads"  # make sure this folder exists next to your Flask file
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/add/lost", methods=["POST"])
def add_lost():
    category = request.form.get("category")
    status = request.form.get("status", "Lost")
    date = request.form.get("date")
    reportedbyuserid = request.form.get("reportedbyuserid")

    if not category or not status or not date or not reportedbyuserid:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    image_path = None
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(save_path)
        image_path = f"{request.host_url}uploads/{filename}"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO itemlist (category, status, date, image, reportedbyuserid)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING itemid;
        """
        values = (category, status, date, image_path, reportedbyuserid)
        cursor.execute(query, values)

        item_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Lost item reported successfully.",
            "itemID": item_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/add/found", methods=["POST"])
def add_found():
    category = request.form.get("category")
    location = request.form.get("location")
    date = request.form.get("date")
    status = request.form.get("status", "Found")
    reportedbyuserid = request.form.get("reportedbyuserid")

    if not category or not location or not date or not reportedbyuserid:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    image_path = None
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(save_path)
        image_path = f"{request.host_url}uploads/{filename}"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO itemlist (category, status, location, date, image, reportedbyuserid)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING itemid;
        """
        values = (category, status, location, date, image_path, reportedbyuserid)
        cursor.execute(query, values)

        item_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

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
# SECURITY NOTE: this checks that the userID sent in the request body
# matches the item's reportedbyuserid — but since userID just comes from
# the frontend's localStorage (not a verified login session/token), a
# person could technically edit their browser's localStorage to claim a
# different userID and bypass this check. This is "casual misuse"
# protection, not real security.
@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    data = request.get_json() or {}
    requesting_user_id = data.get("userid")

    if not requesting_user_id:
        return jsonify({"success": False, "error": "userid is required to delete an item"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT reportedbyuserid FROM itemlist WHERE itemid = %s;",
            (item_id,)
        )
        row = cursor.fetchone()

        if not row:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "error": "Item not found"}), 404

        actual_owner_id = row[0]

        if str(actual_owner_id) != str(requesting_user_id):
            cursor.close()
            conn.close()
            return jsonify({"success": False, "error": "You are not authorized to delete this item"}), 403

        cursor.execute("DELETE FROM itemlist WHERE itemid = %s RETURNING itemid;", (item_id,))
        deleted = cursor.fetchone()

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Item deleted successfully."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims", methods=["POST"])
def add_claim():
    data = request.get_json()

    itemid = data.get("itemid")
    claimuserid = data.get("claimuserid")
    verificationnotes = data.get("verificationnotes")
    claimdate = data.get("claimdate")
    claimstatus = data.get("claimstatus", "Pending")

    if not itemid or not claimuserid or not claimdate:
        return jsonify({"success": False, "error": "Required fields missing"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO claims (itemid, claimuserid, verificationnotes, claimdate, claimstatus)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING claimid;
        """
        values = (itemid, claimuserid, verificationnotes, claimdate, claimstatus)
        cursor.execute(query, values)

        claim_id = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE itemlist SET status = %s WHERE itemid = %s;",
            ("Pending Claim", itemid)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Claim submitted successfully.",
            "claimID": claim_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims/user/<int:user_id>", methods=["GET"])
def get_user_claims(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT claimid, itemid, claimuserid, verificationnotes, claimdate, claimstatus
            FROM claims
            WHERE claimuserid = %s
            ORDER BY claimdate DESC;
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify([
            {
                "claimid": row[0],
                "itemid": row[1],
                "claimuserid": row[2],
                "verificationnotes": row[3],
                "claimdate": row[4].isoformat() if row[4] else None,
                "claimstatus": row[5]
            }
            for row in rows
        ])

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims/pending", methods=["GET"])
def get_pending_claims():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT claimid, itemid, claimuserid, verificationnotes, claimdate, claimstatus
            FROM claims
            WHERE claimstatus = 'Pending'
            ORDER BY claimdate ASC;
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify([
            {
                "claimid": row[0],
                "itemid": row[1],
                "claimuserid": row[2],
                "verificationnotes": row[3],
                "claimdate": row[4].isoformat() if row[4] else None,
                "claimstatus": row[5]
            }
            for row in rows
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
        msg.set_content(f"Good news! Your claim for '{category}' has been approved.")
    else:
        msg.set_content(f"Your claim for '{category}' was not approved. Contact the admin office for details.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        pass

def _review_claim(claim_id, new_status):
    data = request.get_json() or {}
    verifiedby = data.get("verifiedby")

    try:
        conn = get_connection()
        cursor = conn.cursor()

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
            cursor.close()
            conn.close()
            return jsonify({"success": False, "error": "Claim not found"}), 404

        itemid, claimant_email, category = row

        cursor.execute(
            "UPDATE claims SET claimstatus = %s, verifiedby = %s WHERE claimid = %s;",
            (new_status, verifiedby, claim_id)
        )

        item_status = "Claimed" if new_status == "Approved" else "Found"
        cursor.execute(
            "UPDATE itemlist SET status = %s WHERE itemid = %s;",
            (item_status, itemid)
        )

        conn.commit()
        cursor.close()
        conn.close()

        send_claim_notification(claimant_email, new_status == "Approved", category)

        return jsonify({"success": True, "message": f"Claim {new_status.lower()}."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/claims/<int:claim_id>/approve", methods=["POST"])
def approve_claim(claim_id):
    return _review_claim(claim_id, "Approved")

@app.route("/claims/<int:claim_id>/reject", methods=["POST"])
def reject_claim(claim_id):
    return _review_claim(claim_id, "Rejected")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )