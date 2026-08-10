document.getElementById("registerForm").addEventListener("submit", function(event) {
    event.preventDefault();
    
    const userData = {
        username: document.getElementById("name").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
        phone_number: document.getElementById("phone").value,
        department: document.getElementById("department").value,
        usertype: "lecturer"
    };

    fetch("https://legion-is-here.tail208289.ts.net/add/lecturer", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(userData)
    })
    .then(response => response.json())
    .then(data => {
        alert("Registration successful! You can now log in.");
    })
    .catch(error => {
        console.error("Error:", error);
    });
    document.getElementById("registerForm").addEventListener("submit", function(event) {
    event.preventDefault();
    window.location.href = "../../login/";
    })
});