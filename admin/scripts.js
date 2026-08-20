console.log("admin.js loaded");

const API_BASE = "https://legion-is-here.tail208289.ts.net";
const currentAdminID = localStorage.getItem("adminID");
const authToken = localStorage.getItem("adminToken");

if (!currentAdminID || !authToken) {
    alert("Please log in as an admin.");
    window.location.href = "../login/";
}

function authHeaders(extra) {
    return Object.assign({ "Authorization": `Bearer ${authToken}` }, extra || {});
}

function copyToClipboard(text, label) {
    if (!text) return;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
            .then(function () { alert(`${label} copied to clipboard.`); })
            .catch(function () { prompt(`Copy this ${label.toLowerCase()}:`, text); });
    } else {
        prompt(`Copy this ${label.toLowerCase()}:`, text);
    }
}

function handleApiResponse(response) {
    if (response.status === 401 || response.status === 403) {
        alert("Your admin session has expired or is invalid. Please log in again.");
        localStorage.removeItem("adminID");
        localStorage.removeItem("adminToken");
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

function openLightbox(imageUrl) {
    if (!imageUrl) return;
    const lightbox = document.getElementById("imageLightbox");
    document.getElementById("lightboxImage").src = imageUrl;
    lightbox.classList.remove("hidden");
}

document.getElementById("imageLightbox").addEventListener("click", function () {
    this.classList.add("hidden");
});

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
            ${itemImage ? `<img src="${itemImage}" alt="${itemCategory || ''}" class="claim-group-image clickable-image" onerror="this.style.display='none'">` : ''}
            <h4>Item #${itemid}${itemCategory ? ` — ${itemCategory}` : ''}${itemClaims.length > 1 ? ` — ${itemClaims.length} competing claims` : ''}</h4>
        `;

        const itemImgEl = group.querySelector(".claim-group-image");
        if (itemImgEl) {
            itemImgEl.addEventListener("click", function () {
                openLightbox(itemImage);
            });
        }

        itemClaims.forEach(function (claim) {
            const card = document.createElement("div");
            card.className = "item-card";

            const emailLink = claim.claimantEmail
                ? `<a href="mailto:${claim.claimantEmail}">${claim.claimantEmail}</a>`
                : "No email on file";
            const phoneText = claim.claimantPhone || "No phone on file";

            card.innerHTML = `
                <span class="status-badge">${claim.claimstatus}</span>
                <p>Claimed by ${claim.claimantUsername ? claim.claimantUsername : ''} (user #${claim.claimuserid})</p>
                <p class="contact-row">Phone: ${phoneText}
                    ${claim.claimantPhone ? `<button type="button" class="copy-btn" data-copy="${claim.claimantPhone}" data-label="Phone">Copy</button>` : ''}
                </p>
                <p class="contact-row">Email: ${emailLink}
                    ${claim.claimantEmail ? `<button type="button" class="copy-btn" data-copy="${claim.claimantEmail}" data-label="Email">Copy</button>` : ''}
                </p>
                <p>Date: ${claim.claimdate}</p>
                <p>${claim.verificationnotes || 'No description provided'}</p>
                ${claim.claimImage ? `<img src="${claim.claimImage}" alt="Claim evidence" class="claim-evidence-image clickable-image" onerror="this.style.display='none'">` : ''}
            `;

            card.querySelectorAll(".copy-btn").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    copyToClipboard(btn.dataset.copy, btn.dataset.label);
                });
            });

            const evidenceImgEl = card.querySelector(".claim-evidence-image");
            if (evidenceImgEl) {
                evidenceImgEl.addEventListener("click", function () {
                    openLightbox(claim.claimImage);
                });
            }

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

function loadAllItems() {
    fetch(`${API_BASE}/admin/items`, { headers: authHeaders() })
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

        const emailLink = item.reportedByEmail
            ? `<a href="mailto:${item.reportedByEmail}">${item.reportedByEmail}</a>`
            : "No email on file";
        const phoneText = item.reportedByPhone || "No phone on file";

        card.innerHTML = `
            <img src="${item.image || ''}" alt="${item.category}" class="clickable-image" onerror="this.style.display='none'">
            <span class="status-badge">${item.status}</span>
            <h4>${item.category} <span class="item-id-tag">#${item.itemID}</span></h4>
            ${item.location ? `<p>Location: ${item.location}</p>` : ''}
            <p>${item.date ? new Date(item.date).toLocaleDateString() : ''}</p>
            <p>Reported by ${item.reportedByUsername ? item.reportedByUsername : ''} (user #${item.reportedByUserID || ''})</p>
            <p class="contact-row">Phone: ${phoneText}
                ${item.reportedByPhone ? `<button type="button" class="copy-btn" data-copy="${item.reportedByPhone}" data-label="Phone">Copy</button>` : ''}
            </p>
            <p class="contact-row">Email: ${emailLink}
                ${item.reportedByEmail ? `<button type="button" class="copy-btn" data-copy="${item.reportedByEmail}" data-label="Email">Copy</button>` : ''}
            </p>
        `;

        card.querySelectorAll(".copy-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                copyToClipboard(btn.dataset.copy, btn.dataset.label);
            });
        });

        const imgEl = card.querySelector("img.clickable-image");
        if (imgEl && item.image) {
            imgEl.addEventListener("click", function () {
                openLightbox(item.image);
            });
        }

        container.appendChild(card);
    });
}

loadPendingClaims();