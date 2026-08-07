import email

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import psycopg2

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

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT userid, username, email, usertype
            FROM Users
            WHERE username = %s AND password = %s;
        """

        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
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
        return jsonify({"error": "All fields are required"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        s2fa = input("insert data to student table? (y/n): ")

        if s2fa.lower() != "y":
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "user creation aborted by admin"
            }), 400

        userquery = """
            INSERT INTO Users (username, email, password, phone_number, usertype)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING userid;
        """

        values = (
            name,
            email,
            password,
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
        return jsonify({"error": "All fields are required"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        l2fa = input("insert data to lecturer table? (y/n): ")

        if l2fa.lower() != "y":
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "user creation aborted by admin"
            }), 400

        userquery = """
            INSERT INTO Users (username, email, password, phone_number, usertype)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING userid;
        """

        values = (
            name,
            email,
            password,
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
        return jsonify({"error": "All fields are required"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        c2fa = input("insert data to community table? (y/n): ")

        if c2fa.lower() != "y":
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "error": "user creation aborted by admin"
            }), 400

        userquery = """
            INSERT INTO Users (username, email, password, phone_number, usertype)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING userid;
        """

        values = (
            name,
            email,
            password,
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

@app.route("/data")
def get_data():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, name, email FROM test_users ORDER BY id;')

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify([
            {
                "id": row[0],
                "name": row[1],
                "email": row[2]
            }
            for row in rows
        ])

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )