console.log("dashboard.js loaded");

const API_BASE = "https://legion-is-here.tail208289.ts.net";
const currentUserID = localStorage.getItem("userID");
const authToken = localStorage.getItem("token");
const claimVideo = document.getElementById("claimCamera");
const claimCanvas = document.getElementById("claimCanvas");
const claimPreview = document.getElementById("claimPhotoPreview");
const captureBtn = document.getElementById("capturePhotoBtn");
const retakeBtn = document.getElementById("retakePhotoBtn");
const claimModal = document.getElementById("claimModal");
const claimPhotoModal = document.getElementById("claimPhotoModal");

// Toggle both the class AND inline display, so hide/show works even if a
// stylesheet rule elsewhere ends up overriding the ".hidden" class.
function showEl(el) {
    el.classList.remove("hidden");
    el.style.removeProperty("display");
}
function hideEl(el) {
    el.classList.add("hidden");
    el.style.display = "none";
}

let claimStream = null;
let capturedPhotoBlob = null;

if (!currentUserID || !authToken) {
    alert("Please log in.");
    window.location.href = "../login/";
}

function authHeaders(extra) {
    return Object.assign({ "Authorization": `Bearer ${authToken}` }, extra || {});
}

// The API sometimes returns image URLs as http://, but the Tailscale tunnel
// only serves https (port 443), so those requests get refused. Upgrade them.
function toSecureUrl(url) {
    return url ? url.replace(/^http:\/\//i, "https://") : url;
}

function dateWithCurrentTime(dateStr) {
    const now = new Date();
    const [year, month, day] = dateStr.split("-").map(Number);
    const combined = new Date(year, month - 1, day, now.getHours(), now.getMinutes(), now.getSeconds());
    return combined.toISOString();
}

function handleApiResponse(response) {
    if (response.status === 401) {
        alert("Your session has expired. Please log in again.");
        localStorage.removeItem("userID");
        localStorage.removeItem("token");
        window.location.href = "../login/";
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

let allItems = [];

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

(function setDefaultDates() {
    const todayStr = new Date().toISOString().split("T")[0];

    const lostDateInput = document.getElementById("lostDate");
    lostDateInput.value = todayStr;
    lostDateInput.max = todayStr;

    const foundDateInput = document.getElementById("foundDate");
    foundDateInput.value = todayStr;
    foundDateInput.max = todayStr;
})();

document.getElementById("lostForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const itemCategory = document.getElementById("lostItemCategory").value;
    const lostDate = document.getElementById("lostDate").value;

    if (!validateNotFutureDate(lostDate, "lostDateError")) return;

    if (!confirm("Submit this lost item report?")) return;

    const formData = new FormData();
    formData.append("category", itemCategory);
    formData.append("status", "Lost");
    formData.append("date", dateWithCurrentTime(lostDate));
    formData.append("location", document.getElementById("lostLocation").value);

    const imageFile = document.getElementById("lostImage").files[0];
    if (imageFile) formData.append("image", imageFile);

    fetch(`${API_BASE}/add/lost`, {
        method: "POST",
        headers: authHeaders(),
        body: formData
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        document.getElementById("lostForm").reset();
        document.getElementById("lostDate").value = new Date().toISOString().split("T")[0];
    })
    .catch(function (error) {
        console.error("Error reporting lost item:", error);
        alert("Couldn't reach the server. Please check your connection and try again.");
    });
});

document.getElementById("foundForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const foundDate = document.getElementById("foundDate").value;
    if (!validateNotFutureDate(foundDate, "foundDateError")) return;

    if (!confirm("Submit this found item report?")) return;

    const formData = new FormData();
    formData.append("category", document.getElementById("foundItemCategory").value);
    formData.append("location", document.getElementById("foundLocation").value);
    formData.append("date", dateWithCurrentTime(foundDate));
    formData.append("status", "Found");

    const imageFile = document.getElementById("foundImage").files[0];
    if (imageFile) formData.append("image", imageFile);

    fetch(`${API_BASE}/add/found`, {
        method: "POST",
        headers: authHeaders(),
        body: formData
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        document.getElementById("foundForm").reset();
        document.getElementById("foundDate").value = new Date().toISOString().split("T")[0];
    })
    .catch(function (error) {
        console.error("Error reporting found item:", error);
        alert("Couldn't reach the server. Please check your connection and try again.");
    });
});

function loadItems() {
    fetch(`${API_BASE}/items`)
        .then(handleApiResponse)
        .then(function (items) {
            allItems = items;
            applyFilters();
        })
        .catch(function (error) {
            if (error.handled) return;
            console.error("Error loading items:", error);
            alert(error.message || "Couldn't reach the server. Please check your connection and try again.");
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
            <img src="${toSecureUrl(item.image) || ''}" alt="${item.category}"
                 onerror="this.style.display='none'">
            <span class="status-badge">${item.status}</span>
            <h4>${item.category}</h4>
            ${item.location ? `<p>${item.status === 'Lost' ? 'Last seen near' : 'Found at'}: ${item.location}</p>` : ''}
            <p>${item.date ? new Date(item.date).toLocaleDateString() : ''}</p>
        `;

        card.addEventListener("click", function () {
            openDetailModal(item);
        });

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

function openDetailModal(item) {
    document.getElementById("detailImage").src = toSecureUrl(item.image) || "";
    document.getElementById("detailStatus").textContent = item.status;
    document.getElementById("detailCategory").textContent = item.category;
    document.getElementById("detailLocation").textContent = item.location
        ? `${item.status === 'Lost' ? 'Last seen near' : 'Found at'}: ${item.location}`
        : "";
    document.getElementById("detailDate").textContent = item.date ? `Date: ${new Date(item.date).toLocaleDateString()}` : "";
    document.getElementById("detailReportedBy").textContent =
        `Reported by ${item.reportedByUsername ? item.reportedByUsername + " " : ""}(user #${item.reportedByUserID || ""})`;

    const ownerActions = document.getElementById("detailOwnerActions");
    ownerActions.innerHTML = "";

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
        headers: authHeaders()
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


async function startClaimCamera() {
    try {
        claimStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" },
            audio: false
        });
        claimVideo.srcObject = claimStream;
    } catch (error) {
        console.error("Camera error:", error);
        alert("Unable to access camera: " + error.message);
    }
}

function stopClaimCamera() {
    if (claimStream) {
        claimStream.getTracks().forEach(function (track) { track.stop(); });
        claimVideo.srcObject = null;
        claimStream = null;
    }
}

function resetClaimPhotoUI() {
    capturedPhotoBlob = null;
    claimPreview.src = "";
    hideEl(claimPreview);
    hideEl(retakeBtn);
    hideEl(claimCanvas);
    showEl(claimVideo);
    showEl(captureBtn);
}

captureBtn.addEventListener("click", function () {
    claimCanvas.width = claimVideo.videoWidth;
    claimCanvas.height = claimVideo.videoHeight;
    claimCanvas.getContext("2d").drawImage(claimVideo, 0, 0);

    claimCanvas.toBlob(function (blob) {
        capturedPhotoBlob = blob;
        claimPreview.src = URL.createObjectURL(blob);

        hideEl(claimVideo);
        hideEl(captureBtn);
        hideEl(claimCanvas);
        showEl(claimPreview);
        showEl(retakeBtn);
    }, "image/jpeg", 0.9);
});

retakeBtn.addEventListener("click", function () {
    resetClaimPhotoUI();
});

function openClaimModal(itemID) {
    document.getElementById("claimItemID").value = itemID;
    document.getElementById("claimNotes").value = "";
    document.getElementById("claimIDCard").value = "";
    claimModal.classList.remove("hidden");
}

document.getElementById("cancelClaimBtn").addEventListener("click", function () {
    claimModal.classList.add("hidden");
});

document.getElementById("claimNextBtn").addEventListener("click", function () {
    const notes = document.getElementById("claimNotes").value.trim();
    if (!notes) {
        alert("Please describe why this item is yours.");
        return;
    }

    const idCardFile = document.getElementById("claimIDCard").files[0];
    if (!idCardFile) {
        alert("Please upload a photo of your student ID card.");
        return;
    }

    claimModal.classList.add("hidden");
    resetClaimPhotoUI();
    claimPhotoModal.classList.remove("hidden");
    startClaimCamera();
});

function closeClaimPhotoModal() {
    stopClaimCamera();
    claimPhotoModal.classList.add("hidden");
}

document.getElementById("cancelClaimPhotoBtn").addEventListener("click", closeClaimPhotoModal);

document.getElementById("submitClaimBtn").addEventListener("click", function () {
    if (!capturedPhotoBlob) {
        alert("Please capture a photo before submitting your claim.");
        return;
    }

    const idCardFile = document.getElementById("claimIDCard").files[0];
    if (!idCardFile) {
        alert("Please upload a photo of your student ID card.");
        return;
    }

    if (!confirm("Submit this claim?")) return;

    const formData = new FormData();
    formData.append("itemid", document.getElementById("claimItemID").value);
    formData.append("verificationnotes", document.getElementById("claimNotes").value);
    formData.append("claimdate", new Date().toISOString());
    formData.append("claimstatus", "Pending");
    formData.append("image", capturedPhotoBlob, "claim_photo.jpg");
    formData.append("idcard", idCardFile);

    fetch(`${API_BASE}/claims`, {
        method: "POST",
        headers: authHeaders(),
        body: formData
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        alert(data.message || data.error);
        closeClaimPhotoModal();
        loadItems();
    })
    .catch(function (error) {
        console.error("Error submitting claim:", error);
        alert("Couldn't reach the server, so your claim was NOT submitted. Please check your connection and try again.");
    });
});

function loadMyClaims() {
    fetch(`${API_BASE}/claims/me`, { headers: authHeaders() })
        .then(handleApiResponse)
        .then(function (claims) { renderClaims(claims); })
        .catch(function (error) {
            if (error.handled) return;
            console.error("Error loading claims:", error);
            alert(error.message || "Couldn't reach the server. Please check your connection and try again.");
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
            <p>${claim.verificationnotes || ''}</p>
        `;
        container.appendChild(card);
    });
}

loadItems();