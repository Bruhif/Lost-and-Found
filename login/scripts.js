const API_BASE = "https://legion-is-here.tail208289.ts.net";

document.getElementById("loginForm").addEventListener("submit", function(event) {
    event.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password })
    })
    .then(function (response) {
        // Rate limiting returns 429 with a JSON body — still parse it below
        // rather than treating it as a hard network failure, so the real
        // "please wait a minute" message actually reaches the user.
        return response.json();
    })
    .then(function (data) {
        if (!data.success) {
            alert(data.error || "Invalid username or password.");
            return;
        }

        // /login returns either a "user" or an "admin" object depending on
        // which table matched — route based on whichever one is present.
        if (data.user) {
            localStorage.setItem("userID", data.user.id);
            localStorage.setItem("usertype", data.user.usertype);
            localStorage.setItem("token", data.token);
            alert("Login successful!");
            window.location.href = "../dashboard/";
        } else if (data.admin) {
            localStorage.setItem("adminID", data.admin.id);
            localStorage.setItem("adminToken", data.token);
            alert("Admin login successful!");
            window.location.href = "../admin/";
        }
    })
    .catch(function (error) {
        console.error("Login error:", error);
        alert("Unable to reach the server. Please try again.");
    });
});

function testFlask() {
    fetch(`${API_BASE}/test`)
    .then(response => response.json())
    .then(data => {
        document.getElementById("result").textContent = data.message;
    })
    .catch(error => {
        console.error(error);
        document.getElementById("result").textContent =
            "Failed to connect to Flask";
    });
}