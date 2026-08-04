import socket
import struct
import time
import traceback
import subprocess
import sys

HOST = "100.121.226.108"
PORT = 5432

USER = "teentin"
DATABASE = "lnf"
PASSWORD = "1712"


def log(message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def hex_dump(data):
    if not data:
        return "(empty)"

    return " ".join(f"{b:02x}" for b in data)


def decode_postgres_response(data):
    if not data:
        return "EMPTY RESPONSE"

    message_type = chr(data[0])

    message_names = {
        "R": "Authentication",
        "E": "ErrorResponse",
        "S": "ParameterStatus",
        "K": "BackendKeyData",
        "Z": "ReadyForQuery",
        "N": "NoticeResponse",
        "T": "RowDescription",
        "D": "DataRow",
        "C": "CommandComplete",
    }

    return message_names.get(
        message_type,
        f"Unknown PostgreSQL message type: {message_type!r}"
    )


def test_dns():
    log("=" * 60)
    log("STEP 1: HOSTNAME / IP RESOLUTION")
    log("=" * 60)

    try:
        result = socket.getaddrinfo(
            HOST,
            PORT,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM
        )

        for item in result:
            family, socktype, proto, canonname, sockaddr = item

            log(f"Address family : {family}")
            log(f"Socket type   : {socktype}")
            log(f"Protocol      : {proto}")
            log(f"Resolved addr : {sockaddr}")

        log("RESULT: PASS")

    except Exception as e:
        log("RESULT: FAIL")
        log(f"{type(e).__name__}: {e}")
        return False

    return True


def test_tcp():
    log("")
    log("=" * 60)
    log("STEP 2: TCP CONNECTION")
    log("=" * 60)

    sock = None

    try:
        log(f"Target: {HOST}:{PORT}")
        log("Creating TCP socket...")

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        sock.settimeout(10)

        log("Connecting...")
        start = time.perf_counter()

        sock.connect((HOST, PORT))

        elapsed = time.perf_counter() - start

        log("TCP connection established!")
        log(f"Connection time: {elapsed:.4f} seconds")

        local_ip, local_port = sock.getsockname()

        log(f"Local endpoint : {local_ip}:{local_port}")
        log(f"Remote endpoint: {HOST}:{PORT}")

        log("RESULT: PASS")

        return sock

    except Exception as e:
        log("RESULT: FAIL")
        log(f"{type(e).__name__}: {e}")
        return None


def test_ssl_request(sock):
    log("")
    log("=" * 60)
    log("STEP 3: POSTGRESQL SSL REQUEST")
    log("=" * 60)

    try:
        # PostgreSQL SSLRequest:
        #
        # Length = 8
        # SSLRequest code = 80877103

        packet = struct.pack(
            "!II",
            8,
            80877103
        )

        log("Sending PostgreSQL SSLRequest...")
        log(f"Bytes sent: {hex_dump(packet)}")

        sock.sendall(packet)

        log("Waiting for PostgreSQL response...")

        response = sock.recv(1)

        if not response:
            log("Server closed connection!")
            log("RESULT: FAIL")
            return False

        log(f"Response byte: {hex_dump(response)}")

        if response == b"S":
            log("PostgreSQL says: SSL SUPPORTED")
            log("RESULT: PASS")
            return True

        elif response == b"N":
            log("PostgreSQL says: SSL NOT SUPPORTED")
            log("RESULT: PASS")
            return True

        else:
            log("Unexpected response!")
            log("RESULT: FAIL")
            return False

    except Exception as e:
        log("RESULT: FAIL")
        log(f"{type(e).__name__}: {e}")
        return False


def test_plain_postgres_connection():
    log("")
    log("=" * 60)
    log("STEP 4: PLAIN POSTGRESQL STARTUP CONNECTION")
    log("=" * 60)

    sock = None

    try:
        log("Creating fresh TCP connection...")

        sock = socket.create_connection(
            (HOST, PORT),
            timeout=10
        )

        log("TCP connection established!")

        # PostgreSQL protocol 3.0
        protocol_version = struct.pack(
            "!I",
            196608
        )

        startup_params = (
            b"user\x00" +
            USER.encode() +
            b"\x00" +

            b"database\x00" +
            DATABASE.encode() +
            b"\x00" +

            b"application_name\x00" +
            b"connection_diagnostic\x00" +

            b"\x00"
        )

        body = protocol_version + startup_params

        packet = struct.pack(
            "!I",
            len(body) + 4
        ) + body

        log("Sending PostgreSQL StartupMessage...")
        log(f"Bytes sent: {hex_dump(packet)}")

        sock.sendall(packet)

        log("Waiting for server response...")

        response = sock.recv(4096)

        if not response:
            log("Server closed connection!")
            log("RESULT: FAIL")
            return False

        log(f"Received {len(response)} bytes")
        log(f"Raw bytes: {hex_dump(response)}")

        log(f"PostgreSQL response type: {decode_postgres_response(response)}")

        if response[0:1] == b"R":
            log("Server reached authentication stage!")
            log("RESULT: PASS")

        elif response[0:1] == b"E":
            log("Server returned a PostgreSQL error.")
            log("This means the PostgreSQL protocol is working.")
            log("RESULT: PASS (protocol reached server)")

        else:
            log("Server responded, but response was unexpected.")
            log("RESULT: UNKNOWN")

        return True

    except ConnectionResetError as e:
        log("CONNECTION RESET BY REMOTE HOST")
        log(f"{type(e).__name__}: {e}")
        log("RESULT: FAIL")

        return False

    except Exception as e:
        log("RESULT: FAIL")
        log(f"{type(e).__name__}: {e}")

        return False

    finally:
        if sock:
            sock.close()


def test_psycopg2():
    log("")
    log("=" * 60)
    log("STEP 5: PSYCOPG2 CONNECTION")
    log("=" * 60)

    try:
        import psycopg2

        log(f"psycopg2 version: {psycopg2.__version__}")
        log(f"libpq version   : {psycopg2.__libpq_version__}")

        log("Attempting database connection...")

        start = time.perf_counter()

        connection = psycopg2.connect(
            host=HOST,
            port=PORT,
            database=DATABASE,
            user=USER,
            password=PASSWORD,
            connect_timeout=10,
            application_name="connection_diagnostic"
        )

        elapsed = time.perf_counter() - start

        log("DATABASE CONNECTION SUCCESSFUL!")
        log(f"Connection time: {elapsed:.4f} seconds")

        cursor = connection.cursor()

        log("Running test query...")

        cursor.execute(
            """
            SELECT
                current_database(),
                current_user,
                inet_server_addr(),
                inet_server_port(),
                version();
            """
        )

        result = cursor.fetchone()

        log("Query successful!")

        log(f"Database     : {result[0]}")
        log(f"User         : {result[1]}")
        log(f"Server IP    : {result[2]}")
        log(f"Server port  : {result[3]}")
        log(f"PostgreSQL   : {result[4]}")

        cursor.close()
        connection.close()

        log("RESULT: PASS")

        return True

    except Exception as e:
        log("RESULT: FAIL")
        log(f"Exception type: {type(e).__name__}")
        log(f"Exception: {e}")

        return False


def main():

    print()
    print("=" * 60)
    print("POSTGRESQL CONNECTION DIAGNOSTIC")
    print("=" * 60)
    print()

    log(f"Python version: {sys.version}")
    log(f"Target host  : {HOST}")
    log(f"Target port  : {PORT}")
    log(f"Database     : {DATABASE}")
    log(f"User         : {USER}")

    print()

    # Step 1
    test_dns()

    # Step 2
    sock = test_tcp()

    if sock:
        # Step 3
        test_ssl_request(sock)

        sock.close()

    # Step 4
    test_plain_postgres_connection()

    # Step 5
    test_psycopg2()

    print()
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()