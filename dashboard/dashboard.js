console.log("dashboard.js loaded");

const API_BASE = "https://legion-is-here.tail208289.ts.net";
const currentUserID = localStorage.getItem("userID");

let allItems = []; // cache of the last /items fetch, used for count/sort/detail lookups

// ---------- TAB SWITCHING ----------
const buttons = document.querySelectorAll(".tab-btn");
const sections = document.querySelectorAll(".tab-section");

buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
        buttons.forEach(function (b) { b.classList.remove("active"); });
        sections.forEach(function (s) { s.classList.remove("active"); });

        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");

        if (btn.dataset.tab === "browse") loadItems();
        if (btn.dataset.tab === "myClaims") loadMyClaims();
    });
});

// ---------- FORM VALIDATION HELPERS ----------
// Returns true if the date is valid (not empty, not in the future), false otherwise.
// Writes a message into the given error <p> element either way.
function validateNotFutureDate(dateValue, errorElementId) {
    const errorEl = document.getElementById(errorElementId);
    errorEl.textContent = "";

    if (!dateValue) {
        errorEl.textContent = "Date is required.";
        return false;
    }

    const today = new Date().toISOString().split("T")[0];
    if (dateValue > today) {
        errorEl.textContent = "Date cannot be in the future.";
        return false;
    }

    return true;
}

// ---------- REPORT LOST ITEM (with optional image) ----------
document.getElementById("lostForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const itemCategory = document.getElementById("lostItemCategory").value;
    const lostDate = document.getElementById("lostDate").value;

    if (!validateNotFutureDate(lostDate, "lostDateError")) return;

    if (!confirm("Submit this lost item report?")) return;

    const formData = new FormData();
    formData.append("category", itemCategory);
    formData.append("status", "Lost");
    formData.append("date", lostDate);
    formData.append("reportedbyuserid", currentUserID);

    const imageFile = document.getElementById("lostImage").files[0];
    if (imageFile) formData.append("image", imageFile);

    fetch(`${API_BASE}/add/lost`, {
        method: "POST",
        body: formData // no Content-Type header — browser sets multipart boundary automatically
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        document.getElementById("lostForm").reset();
    })
    .catch(function (error) {
        console.error("Error reporting lost item:", error);
        alert("Couldn't reach the server. Please check your connection and try again.");
    });
});

// ---------- REPORT FOUND ITEM (with image upload) ----------
document.getElementById("foundForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const foundDate = document.getElementById("foundDate").value;
    if (!validateNotFutureDate(foundDate, "foundDateError")) return;

    if (!confirm("Submit this found item report?")) return;

    const formData = new FormData();
    formData.append("category", document.getElementById("foundItemCategory").value);
    formData.append("location", document.getElementById("foundLocation").value);
    formData.append("date", foundDate);
    formData.append("status", "Found");
    formData.append("reportedbyuserid", currentUserID);

    const imageFile = document.getElementById("foundImage").files[0];
    if (imageFile) formData.append("image", imageFile);

    fetch(`${API_BASE}/add/found`, {
        method: "POST",
        body: formData
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        document.getElementById("foundForm").reset();
    })
    .catch(function (error) {
        console.error("Error reporting found item:", error);
        alert("Couldn't reach the server. Please check your connection and try again.");
    });
});

// ---------- BROWSE / SEARCH / SORT / COUNT ----------
function loadItems() {
    fetch(`${API_BASE}/items`)
        .then(function (response) { return response.json(); })
        .then(function (items) {
            allItems = items;
            applyFilters();
        })
        .catch(function (error) {
            console.error("Error loading items:", error);
            alert("Couldn't reach the server. Please check your connection and try again.");
        });
}

function applyFilters() {
    const search = document.getElementById("searchInput").value.toLowerCase();
    const status = document.getElementById("statusFilter").value;
    const sort = document.getElementById("sortFilter").value;

    let filtered = allItems.filter(function (item) {
        const matchesSearch = !search || (item.category && item.category.toLowerCase().includes(search));
        const matchesStatus = !status || item.status === status;
        return matchesSearch && matchesStatus;
    });

    filtered.sort(function (a, b) {
        const dateA = new Date(a.date);
        const dateB = new Date(b.date);
        return sort === "oldest" ? dateA - dateB : dateB - dateA;
    });

    renderItemCount(filtered);
    renderItems(filtered);
}

function renderItemCount(items) {
    const lostCount = items.filter(function (i) { return i.status === "Lost"; }).length;
    const foundCount = items.filter(function (i) { return i.status === "Found"; }).length;
    document.getElementById("itemCount").textContent =
        `${items.length} item(s) shown — ${lostCount} Lost, ${foundCount} Found`;
}

function renderItems(items) {
    const container = document.getElementById("itemList");
    container.innerHTML = "";

    if (!items.length) {
        container.innerHTML = "<p>No items found.</p>";
        return;
    }

    items.forEach(function (item) {
        const card = document.createElement("div");
        card.className = "item-card";
        card.innerHTML = `
            <img src="${item.image || ''}" alt="${item.category}"
                 onerror="this.style.display='none'">
            <span class="status-badge">${item.status}</span>
            <h4>${item.category}</h4>
            ${item.location ? `<p>Found at: ${item.location}</p>` : ''}
            <p>${item.date ? new Date(item.date).toLocaleDateString() : ''}</p>
        `;

        // Clicking the card opens the detail view
        card.addEventListener("click", function () {
            openDetailModal(item);
        });

        // Claim button, only for Found items, stops the card click from also firing
        if (item.status === "Found") {
            const claimBtn = document.createElement("button");
            claimBtn.textContent = "Claim This Item";
            claimBtn.type = "button";
            claimBtn.addEventListener("click", function (event) {
                event.stopPropagation();
                openClaimModal(item.itemID);
            });
            card.appendChild(claimBtn);
        }

        container.appendChild(card);
    });
}

document.getElementById("searchBtn").addEventListener("click", applyFilters);
document.getElementById("statusFilter").addEventListener("change", applyFilters);
document.getElementById("sortFilter").addEventListener("change", applyFilters);

// ---------- ITEM DETAIL MODAL (with Edit/Delete for the reporting user) ----------
function openDetailModal(item) {
    document.getElementById("detailImage").src = item.image || "";
    document.getElementById("detailStatus").textContent = item.status;
    document.getElementById("detailCategory").textContent = item.category;
    document.getElementById("detailLocation").textContent = item.location ? `Location: ${item.location}` : "";
    document.getElementById("detailDate").textContent = item.date ? `Date: ${new Date(item.date).toLocaleDateString()}` : "";
    document.getElementById("detailReportedBy").textContent = `Reported by user #${item.reportedByUserID || ""}`;

    const ownerActions = document.getElementById("detailOwnerActions");
    ownerActions.innerHTML = "";

    // Only the user who originally reported this item sees Edit/Delete
    if (String(item.reportedByUserID) === String(currentUserID)) {
        const actionsWrap = document.createElement("div");
        actionsWrap.className = "owner-actions";

        const deleteBtn = document.createElement("button");
        deleteBtn.textContent = "Delete Report";
        deleteBtn.type = "button";
        deleteBtn.addEventListener("click", function () {
            deleteItem(item.itemID);
        });

        actionsWrap.appendChild(deleteBtn);
        ownerActions.appendChild(actionsWrap);
    }

    document.getElementById("detailModal").classList.remove("hidden");
}

document.getElementById("closeDetailBtn").addEventListener("click", function () {
    document.getElementById("detailModal").classList.add("hidden");
});

function deleteItem(itemID) {
    if (!confirm("Are you sure you want to delete this report? This cannot be undone.")) return;

    fetch(`${API_BASE}/items/${itemID}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userid: currentUserID })
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        document.getElementById("detailModal").classList.add("hidden");
        loadItems();
    })
    .catch(function (error) {
        console.error("Error deleting item:", error);
        alert("Couldn't reach the server. Please check your connection and try again.");
    });
}

// ---------- CLAIM SUBMISSION ----------
function openClaimModal(itemID) {
    document.getElementById("claimItemID").value = itemID;
    document.getElementById("claimNotes").value = "";
    document.getElementById("claimModal").classList.remove("hidden");
}

function closeClaimModal() {
    document.getElementById("claimModal").classList.add("hidden");
}

document.getElementById("cancelClaimBtn").addEventListener("click", closeClaimModal);

document.getElementById("submitClaimBtn").addEventListener("click", function () {
    if (!confirm("Submit this claim?")) return;

    const claimData = {
        itemid: document.getElementById("claimItemID").value,
        claimuserid: currentUserID,
        claimdate: new Date().toISOString().split("T")[0],
        claimstatus: "Pending"
    };

    fetch(`${API_BASE}/claims`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(claimData)
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        closeClaimModal();
        loadItems();
    })
    .catch(function (error) {
        console.error("Error submitting claim:", error);
        alert("Couldn't reach the server, so your claim was NOT submitted. Please check your connection and try again.");
    });
});

// ---------- MY CLAIMS ----------
function loadMyClaims() {
    fetch(`${API_BASE}/claims/user/${currentUserID}`)
        .then(function (response) { return response.json(); })
        .then(function (claims) { renderClaims(claims); })
        .catch(function (error) {
            console.error("Error loading claims:", error);
            alert("Couldn't reach the server. Please check your connection and try again.");
        });
}

function renderClaims(claims) {
    const container = document.getElementById("claimList");
    container.innerHTML = "";

    if (!claims.length) {
        container.innerHTML = "<p>You haven't made any claims yet.</p>";
        return;
    }

    claims.forEach(function (claim) {
        const card = document.createElement("div");
        card.className = "item-card";
        card.innerHTML = `
            <span class="status-badge">${claim.claimstatus}</span>
            <h4>Item #${claim.itemid}</h4>
            <p>Claimed on: ${claim.claimdate}</p>
        `;
        container.appendChild(card);
    });
}

// Load items on first page view
loadItems();