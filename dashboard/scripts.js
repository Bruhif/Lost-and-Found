const items = [
    {
        itemID: 1,
        category: "Electronics",
        status: "Found",
        image: "https://via.placeholder.com/400",
        location: "Library",
        date: "2026-08-07"
    },

    {
        itemID: 2,
        category: "Accessories",
        status: "Lost",
        image: "https://via.placeholder.com/400",
        location: "Cafeteria",
        date: "2026-08-06"
    }
];

function displayItems(items) {

    const itemList = document.getElementById("itemList");

    itemList.innerHTML = "";

    items.forEach(item => {

        const card = document.createElement("div");

        card.className = "item-card";

        card.innerHTML = `
            <img src="${item.image}" alt="Reported item">

            <div class="item-info">

                <h3>${item.category}</h3>

                <p class="status">
                    ${item.status}
                </p>

                <p>
                    📍 ${item.location}
                </p>

                <p>
                    📅 ${item.date}
                </p>

                <button onclick="viewItem(${item.itemID})">
                    View Details
                </button>

            </div>
        `;

        itemList.appendChild(card);
    });
}

displayItems(items);

document.querySelectorAll(".filter").forEach(button => {

    button.addEventListener("click", () => {

        const status = button.dataset.status;

        if (status === "all") {
            displayItems(items);
            return;
        }

        const filteredItems = items.filter(item =>
            item.status === status
        );

        displayItems(filteredItems);
    });

});