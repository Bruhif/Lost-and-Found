document.getElementById("adminLoginForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const errorEl = document.getElementById("adminLoginError");
    errorEl.textContent = "";

    const loginData = {
        email: document.getElementById("adminEmail").value,
        password: document.getElementById("adminPassword").value
    };

    fetch("https://legion-is-here.tail208289.ts.net/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginData)
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        if (data.success) {
            localStorage.setItem("adminID", data.admin.id);
            localStorage.setItem("adminToken", data.token);
            window.location.href = "../dashboard/admin.html"; // adjust path to match your project structure
        } else {
            errorEl.textContent = data.error || "Login failed. Please try again.";
        }
    })
    .catch(function (error) {
        console.error("Error logging in:", error);
        errorEl.textContent = "Couldn't reach the server. Please check your connection and try again.";
    });
});