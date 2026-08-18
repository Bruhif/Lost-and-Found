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
        return response.json();
    })
    .then(function (data) {
        if (data.success) {
            localStorage.setItem("userID", data.user.id);
            localStorage.setItem("usertype", data.user.usertype);
            localStorage.setItem("token", data.token);
            alert("Login successful!");
            window.location.href = "../dashboard/";
            return;
        }

        fetch(`${API_BASE}/admin/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: username,
                password: password
            })
        })
        .then(function (adminResponse) {
            return adminResponse.json();
        })
        .then(function (adminData) {
            if (adminData.success) {
                localStorage.setItem("adminID", adminData.admin.id);
                localStorage.setItem("adminToken", adminData.token);
                alert("Admin login successful!");
                window.location.href = "../admin/";
            } else {
                alert(adminData.error || data.error || "Invalid username or password.");
            }
        })
        .catch(function (error) {
            console.error("Admin login error:", error);
            alert("Unable to reach the admin login service.");
        });
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