import smtplib 
from email.message import EmailMessage
import os

import secrets
from datetime import datetime, timedelta
from unittest import result

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import psycopg2

from werkzeug.security import generate_password_hash, check_password_hash

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

    print(name)
    print(email)
    print(password)
    print(number)
    print(usertype)
    print(department)
    print(year)

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

    print(name)
    print(email)
    print(password)
    print(number)
    print(usertype)
    print(department)

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
    role = data.get("department")

    print(name)
    print(email)
    print(password)
    print(number)
    print(usertype)
    print(role)

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
            SELECT itemid, category, status, image, location, date
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
                "date": row[5].isoformat()
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
    
@app.route("/add/lost", methods=["POST"])
def add_lost():
    data = request.get_json()

    category = data.get("category")
    status = data.get("status")
    date = data.get("date")
    reportedbyuserid = data.get("reportedbyuserid")

    print(category)
    print(status)
    print(date)
    print(reportedbyuserid)

    if not category or not status or not date or not reportedbyuserid:
        return jsonify({"error": "All fields are required"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO itemlist (category, status, date, reportedbyuserid)
            VALUES (%s, %s, %s, %s)
            RETURNING itemid;
        """

        values = (
            category,
            status,
            date,
            reportedbyuserid
        )

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
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )