console.log("admin.js loaded");

const API_BASE = "https://legion-is-here.tail208289.ts.net";
const currentAdminID = localStorage.getItem("adminID");
const authToken = localStorage.getItem("adminToken");

if (!currentAdminID || !authToken) {
    alert("Please log in as an admin.");
    window.location.href = "../login/admin_login.html"; // adjust path to match your project structure
}

function authHeaders(extra) {
    return Object.assign({ "Authorization": `Bearer ${authToken}` }, extra || {});
}

// See scripts.js for why this exists: without it, an error response
// (e.g. an expired token) gets handed straight to a render function that
// expects an array, and silently displays as "nothing here" instead of
// surfacing the real problem.
function handleApiResponse(response) {
    if (response.status === 401 || response.status === 403) {
        alert("Your admin session has expired or is invalid. Please log in again.");
        localStorage.removeItem("adminID");
        localStorage.removeItem("adminToken");
        window.location.href = "../login/admin_login.html";
        const sessionError = new Error("Session expired");
        sessionError.handled = true;
        throw sessionError;
    }

    return response.json().then(function (data) {
        if (!response.ok || (data && data.success === false)) {
            throw new Error((data && data.error) || "Request failed");
        }
        return data;
    });
}

// ---------- TAB SWITCHING ----------
const buttons = document.querySelectorAll(".tab-btn");
const sections = document.querySelectorAll(".tab-section");

buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
        buttons.forEach(function (b) { b.classList.remove("active"); });
        sections.forEach(function (s) { s.classList.remove("active"); });

        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");

        if (btn.dataset.tab === "pendingClaims") loadPendingClaims();
        if (btn.dataset.tab === "allItems") loadAllItems();
    });
});

// ---------- PENDING CLAIMS ----------
function loadPendingClaims() {
    fetch(`${API_BASE}/claims/pending`, { headers: authHeaders() })
        .then(handleApiResponse)
        .then(function (claims) { renderClaimQueue(claims); })
        .catch(function (error) {
            if (error.handled) return;
            console.error("Error loading pending claims:", error);
            alert(error.message || "Couldn't reach the server. Please check your connection and try again.");
        });
}

// Groups claims by item so competing claims on the same Found item render
// together — that's the whole point of Option B: the admin needs to see
// every claimant on an item side by side to judge who's telling the truth.
function renderClaimQueue(claims) {
    const container = document.getElementById("claimQueue");
    container.innerHTML = "";

    if (!claims.length) {
        container.innerHTML = "<p>No claims are currently pending.</p>";
        return;
    }

    const byItem = {};
    claims.forEach(function (claim) {
        if (!byItem[claim.itemid]) byItem[claim.itemid] = [];
        byItem[claim.itemid].push(claim);
    });

    Object.keys(byItem).forEach(function (itemid) {
        const itemClaims = byItem[itemid];
        const itemImage = itemClaims[0].itemImage;
        const itemCategory = itemClaims[0].itemCategory;

        const group = document.createElement("div");
        group.className = "claim-group";
        group.innerHTML = `
            ${itemImage ? `<img src="${itemImage}" alt="${itemCategory || ''}" class="claim-group-image" onerror="this.style.display='none'">` : ''}
            <h4>Item #${itemid}${itemCategory ? ` — ${itemCategory}` : ''}${itemClaims.length > 1 ? ` — ${itemClaims.length} competing claims` : ''}</h4>
        `;

        itemClaims.forEach(function (claim) {
            const card = document.createElement("div");
            card.className = "item-card";
            card.innerHTML = `
                <span class="status-badge">${claim.claimstatus}</span>
                <p>Claimed by ${claim.claimantUsername ? claim.claimantUsername : ''} (user #${claim.claimuserid})</p>
                <p>Date: ${claim.claimdate}</p>
                <p>${claim.verificationnotes || 'No description provided'}</p>
            `;

            const actions = document.createElement("div");
            actions.className = "claim-actions";

            const approveBtn = document.createElement("button");
            approveBtn.textContent = "Approve";
            approveBtn.type = "button";
            approveBtn.className = "approve-btn";
            approveBtn.addEventListener("click", function () {
                reviewClaim(claim.claimid, "approve");
            });

            const rejectBtn = document.createElement("button");
            rejectBtn.textContent = "Reject";
            rejectBtn.type = "button";
            rejectBtn.className = "reject-btn";
            rejectBtn.addEventListener("click", function () {
                reviewClaim(claim.claimid, "reject");
            });

            actions.appendChild(approveBtn);
            actions.appendChild(rejectBtn);
            card.appendChild(actions);
            group.appendChild(card);
        });

        container.appendChild(group);
    });
}

// Approving one claim auto-rejects every other pending claim on the same
// item server-side (see _review_claim in connection.py) — that's also
// why we just reload the whole queue after either action, rather than
// only removing the one card that was acted on.
function reviewClaim(claimID, action) {
    const label = action === "approve" ? "approve" : "reject";
    if (!confirm(`Are you sure you want to ${label} this claim?`)) return;

    fetch(`${API_BASE}/claims/${claimID}/${action}`, {
        method: "POST",
        headers: authHeaders()
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        loadPendingClaims();
    })
    .catch(function (error) {
        console.error(`Error ${label}ing claim:`, error);
        alert("Couldn't reach the server. Please check your connection and try again.");
    });
}

// ---------- ALL ITEMS ----------
function loadAllItems() {
    fetch(`${API_BASE}/items`)
        .then(handleApiResponse)
        .then(function (items) { renderAllItems(items); })
        .catch(function (error) {
            if (error.handled) return;
            console.error("Error loading items:", error);
            alert(error.message || "Couldn't reach the server. Please check your connection and try again.");
        });
}

function renderAllItems(items) {
    const container = document.getElementById("adminItemList");
    container.innerHTML = "";

    if (!items.length) {
        container.innerHTML = "<p>No items reported yet.</p>";
        return;
    }

    items.forEach(function (item) {
        const card = document.createElement("div");
        card.className = "item-card";
        card.innerHTML = `
            <img src="${item.image || ''}" alt="${item.category}" onerror="this.style.display='none'">
            <span class="status-badge">${item.status}</span>
            <h4>${item.category}</h4>
            ${item.location ? `<p>Location: ${item.location}</p>` : ''}
            <p>${item.date ? new Date(item.date).toLocaleDateString() : ''}</p>
            <p>Reported by user #${item.reportedByUserID || ''}</p>
        `;
        container.appendChild(card);
    });
}

// Load pending claims on first page view
loadPendingClaims();