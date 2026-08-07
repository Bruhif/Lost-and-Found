document.getElementById("registerForm").addEventListener("submit", function(event) {
    event.preventDefault();
    
    const userData = {
        username: document.getElementById("name").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
        phone_number: document.getElementById("phone").value,
        department: document.getElementById("role").value,
        usertype: "community"
    };

    fetch("https://legion-is-here.tail208289.ts.net/add/community", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(userData)
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
    })
    .catch(error => {
        console.error("Error:", error);
    });
});