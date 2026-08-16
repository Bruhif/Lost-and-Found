document.getElementById("loginForm").addEventListener("submit", function(event) {
    event.preventDefault();

    const loginData = {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value
    };
    fetch("https://bruhif.github.io/Lost-and-Found/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(loginData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            localStorage.setItem("userID", data.user.id);
            localStorage.setItem("usertype", data.user.usertype);
            alert("Login successful!");
            window.location.href = "../dashboard/";
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
});

function testFlask() {
    fetch("https://bruhif.github.io/Lost-and-Found/test")
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
