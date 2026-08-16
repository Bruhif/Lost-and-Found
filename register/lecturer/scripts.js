let userData = {};
document.getElementById("registerForm").addEventListener("submit", function(event) {
    event.preventDefault();

    userData = {
        username: document.getElementById("name").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
        phone_number: document.getElementById("phone").value,
        department: document.getElementById("department").value,
        usertype: "lecturer"
    };
    fetch("https://legion-is-here.tail208289.ts.net/send-email", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email: userData.email
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("Verification code sent to your email. Please check your inbox.");
            document.getElementById("registerForm").style.display = "none";
            document.getElementById("verificationSection").style.display = "block";
        } else {
            alert(data.error || "Failed to send verification code. Please try again.");
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("Could not connect to the server")
    });
});
function verifyEmail() {
    const verificationCode = document.getElementById("verificationCode").value;
    if (!verificationCode) {
        alert("Please enter the verification code.");
        return;
    }
    fetch("https://legion-is-here.tail208289.ts.net/verify-email", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email: userData.email,
            code: verificationCode
        })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert(data.error || "Verification failed. Please try again.");
            return;
        }

        alert("Email verified successfully! Proceeding with registration.");
        return fetch("https://legion-is-here.tail208289.ts.net/add/lecturer", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(userData)
        });
    })
    .then(response => {
        if (!response) {
            return;
        }
        return response.json();
    })
    .then(data => {
        if (!data) {
            return;
        }
        if (data.success) {
            alert("Registration successful! Redirecting to login page.");
            window.location.href = "../../login/";
        } else {
            alert(data.error || "Registration failed. Please try again.");
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("Something went wrong while veryfying the email or registering. Please try again.");
    })}
