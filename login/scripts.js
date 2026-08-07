document.getElementById("loginForm").addEventListener("submit", function(event) {
    event.preventDefault();
        
    const loginData = {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value
    };

    fetch("https://legion-is-here.tail208289.ts.net/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(loginData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            // Redirect to the appropriate dashboard based on user type
            if (data.usertype === "student") {
                window.location.href = "https://legion-is-here.tail208289.ts.net/dashboard/student";
            } else if (data.usertype === "lecturer") {
                window.location.href = "https://legion-is-here.tail208289.ts.net/dashboard/lecturer";
            } else if (data.usertype === "community") {
                window.location.href = "https://legion-is-here.tail208289.ts.net/dashboard/community";
            }
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
});

    function testFlask() {
        fetch("https://legion-is-here.tail208289.ts.net/test")
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