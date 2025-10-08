// ======================= main.js (XAI explanations + Auto Carousel + Ratings) =======================

// ⭐ Cuisine-based image mapping
function getCuisineImage(cuisine) {
  if (!cuisine) return null;
  const c = cuisine.toLowerCase();

  if (c.includes("pizza")) return "/static/images/pizza.jpg";
  if (c.includes("indian")) return "/static/images/curry.jpg";
  if (c.includes("chinese") || c.includes("dimsum")) return "/static/images/noodles.jpg";
  if (c.includes("mexican") || c.includes("tacos")) return "/static/images/tacos.jpg";
  if (c.includes("burger") || c.includes("american")) return "/static/images/burger.jpg";
  if (c.includes("italian") || c.includes("pasta") || c.includes("lasagna")) return "/static/images/pasta.jpg";
  if (c.includes("japanese") || c.includes("sushi") || c.includes("ramen")) return "/static/images/sushi.jpg";
  if (c.includes("ice cream") || c.includes("dessert")) return "/static/images/icecream.jpg";
  if (c.includes("cafe") || c.includes("coffee")) return "/static/images/coffee.jpg";
  if (c.includes("bbq") || c.includes("grill") || c.includes("steak")) return "/static/images/bbq.jpg";
  if (c.includes("bakery") || c.includes("cake") || c.includes("pastry")) return "/static/images/cake.jpg";

  if (c.includes("beverages") || c.includes("juices")) return "/static/images/drinks.jpg";
  if (c.includes("international") || c.includes("fusion")) return "/static/images/worldfood.jpg";
  if (c.includes("french") || c.includes("european")) return "/static/images/french.jpg";
  if (c.includes("brazilian") || c.includes("latin")) return "/static/images/brazil.jpg";
  if (c.includes("seafood") || c.includes("prawn")) return "/static/images/seafood.jpg";
  if (c.includes("shawarma") || c.includes("lebanese") || c.includes("arabian")) return "/static/images/arabian.jpg";
  if (c.includes("african") || c.includes("ethiopian")) return "/static/images/african.jpg";
  if (c.includes("vegan") || c.includes("salad") || c.includes("healthy")) return "/static/images/vegan.jpg";
  if (c.includes("breakfast") || c.includes("pancake") || c.includes("brunch")) return "/static/images/breakfast.jpg";

  if (c.includes("street food") || c.includes("snacks")) return "/static/images/food1.jpg";
  if (c.includes("diet") || c.includes("protein")) return "/static/images/food2.jpg";
  if (c.includes("thai") || c.includes("asian") || c.includes("korean")) return "/static/images/food3.jpg";
  if (c.includes("spanish") || c.includes("greek") || c.includes("mediterranean")) return "/static/images/worldfood.jpg";

  return null;
}

// ⭐ City-based background mapping
function getCityImage(city) {
  if (!city) return null;
  const c = city.toLowerCase();

  if (c.includes("hyderabad")) return "/static/images/hyderabad.jpg";
  if (c.includes("mumbai")) return "/static/images/mumbai.jpg";
  if (c.includes("delhi")) return "/static/images/delhi.jpg";
  if (c.includes("kolkata")) return "/static/images/kolkata.jpg";
  if (c.includes("chennai")) return "/static/images/chennai.jpg";
  if (c.includes("bengaluru") || c.includes("bangalore")) return "/static/images/banglore.jpg";
  if (c.includes("sao paulo")) return "/static/images/brazil.jpg";

  return null;
}

// ⭐ Stock fallback images
const stockImages = [
  "/static/images/food1.jpg",
  "/static/images/food2.jpg",
  "/static/images/food3.jpg"
];

// ⭐ Choose best image
function getRestaurantImage(r) {
  if (r.Image_URL && r.Image_URL.trim() !== "") return r.Image_URL;
  const cityImg = getCityImage(r.City);
  if (cityImg) return cityImg;
  const cuisineImg = getCuisineImage(r.Cuisines);
  if (cuisineImg) return cuisineImg;
  return stockImages[Math.floor(Math.random() * stockImages.length)];
}

// =================== Wishlist ===================
function toggleWishlist(name) {
  let wishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
  if (wishlist.includes(name)) {
    wishlist = wishlist.filter(r => r !== name);
  } else {
    wishlist.push(name);
  }
  localStorage.setItem("wishlist", JSON.stringify(wishlist));
  renderWishlist();
}

function renderWishlist() {
  const wishlistDiv = document.getElementById("wishlist");
  let wishlist = JSON.parse(localStorage.getItem("wishlist")) || [];
  if (!wishlistDiv) return;
  wishlistDiv.innerHTML =
    wishlist.length === 0
      ? "<p>No restaurants in wishlist yet ❤️</p>"
      : "<h2>My Wishlist ❤️</h2>" + wishlist.map(n => `<p>⭐ ${n}</p>`).join("");
}

// =================== XAI Explanation Renderer ===================
function renderExplanations(explanation) {
  if (!explanation) return "";
  const parts = explanation.split("|").map(e => e.trim());
  return parts
    .map(reason => {
      let cls = "badge-default";
      if (reason.toLowerCase().includes("city")) cls = "badge-city";
      else if (reason.toLowerCase().includes("cuisine")) cls = "badge-cuisine";
      else if (reason.toLowerCase().includes("mood")) cls = "badge-mood";
      else if (reason.toLowerCase().includes("time")) cls = "badge-time";
      else if (reason.toLowerCase().includes("budget")) cls = "badge-budget";
      else if (reason.toLowerCase().includes("group")) cls = "badge-group";
      else if (reason.toLowerCase().includes("rating")) cls = "badge-rating";
      else if (reason.toLowerCase().includes("highly rated")) cls = "badge-rating";
      else if (reason.toLowerCase().includes("good rating")) cls = "badge-rating";
      else if (reason.toLowerCase().includes("similar cuisine")) cls = "badge-cuisine";
      else if (reason.toLowerCase().includes("similar restaurant")) cls = "badge-default";

      return `<span class="badge ${cls}">${escapeHtml(reason)}</span>`;
    })
    .join(" ");
}

// =================== Restaurants (fetch & render) ===================
function loadRestaurants(page = 1) {
  const search = (document.getElementById("search")?.value || "").trim();
  const city = document.getElementById("cityFilter")?.value || "";
  const cuisine = document.getElementById("cuisineFilter")?.value || "";
  const mood = document.getElementById("moodFilter")?.value || "";
  const time = document.getElementById("timeFilter")?.value || "";
  const budget = document.getElementById("budgetFilter")?.value || "";
  const group = document.getElementById("groupFilter")?.value || "";
  const rating = document.getElementById("ratingFilter")?.value || "";
  const sort = document.getElementById("sortFilter")?.value || "";

  const params = new URLSearchParams();
  if (search) params.append("search", search);
  if (city) params.append("city", city);
  if (cuisine) params.append("cuisine", cuisine);
  if (mood) params.append("mood", mood);
  if (time) params.append("time", time);
  if (budget) params.append("budget", budget);
  if (group) params.append("group", group);
  if (rating) params.append("rating", rating);
  if (sort) params.append("sort", sort);
  params.append("page", page);

  const loadingEl = document.getElementById("loading");
  if (loadingEl) loadingEl.style.display = "block";

  fetch(`/api/restaurants?${params.toString()}`)
    .then(res => res.json())
    .then(data => {
      if (loadingEl) loadingEl.style.display = "none";
      const list = document.getElementById("restaurantGrid");
      const pagination = document.getElementById("pagination");
      if (list) list.innerHTML = "";
      if (pagination) pagination.innerHTML = "";

      if (!data || !data.restaurants || data.restaurants.length === 0) {
        if (list) list.innerHTML = "<p>No restaurants found.</p>";
        return;
      }

      data.restaurants.forEach(r => {
        const image = getRestaurantImage(r);
        const explanationHTML = renderExplanations(r.explanation);

        const html = `
          <div class="card">
            <img src="${image}" alt="${escapeHtml(r["Restaurant Name"] || "")}">
            <div class="card-content">
              <h3>${escapeHtml(r["Restaurant Name"] || "")}</h3>
              <p><b>City:</b> ${escapeHtml(r.City || "")}</p>
              <p><b>Cuisine:</b> ${escapeHtml(r.Cuisines || "")}</p>
              <p><b>Rating:</b> ⭐ ${escapeHtml(r["Aggregate rating"] || "")} ${escapeHtml(r["Rating text"] || "")}</p>
              <p><b>Cost for two:</b> ${escapeHtml(String(r["Average Cost for two"] || ""))} ${escapeHtml(r.Currency || "")}</p>
              <p><b>Votes:</b> ${escapeHtml(String(r.Votes || ""))}</p>
              <div class="explanation">💡 ${explanationHTML}</div>
              <div class="rating-stars" data-restaurant="${escapeJsString(r["Restaurant Name"] || "")}">
                ${[1,2,3,4,5].map(i => `<span class="star" data-value="${i}">☆</span>`).join("")}
              </div>
              <button onclick="toggleWishlist('${escapeJsString(r["Restaurant Name"] || "")}')">❤️ Wishlist</button>
            </div>
          </div>`;
        list.insertAdjacentHTML("beforeend", html);
      });

      attachRatingEvents();
      renderPagination(Math.ceil((data.total || data.restaurants.length) / (data.per_page || data.restaurants.length)), data.page || 1);
    })
    .catch(err => {
      console.error("Error loading restaurants:", err);
      const list = document.getElementById("restaurantGrid");
      if (list) list.innerHTML = "<p>Error loading restaurants.</p>";
      if (loadingEl) loadingEl.style.display = "none";
    });
}

// =================== Rating Stars ===================
function attachRatingEvents() {
  document.querySelectorAll(".rating-stars .star").forEach(star => {
    star.addEventListener("click", function () {
      const container = this.parentElement;
      const restaurant = container.getAttribute("data-restaurant");
      const rating = this.getAttribute("data-value");

      saveRating(restaurant, rating);

      container.querySelectorAll(".star").forEach(s => {
        s.textContent = parseInt(s.getAttribute("data-value")) <= rating ? "★" : "☆";
      });
    });
  });
}

function saveRating(restaurant, rating) {
  fetch("/api/rate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ restaurant, rating: parseFloat(rating) })
  })
    .then(res => res.json())
    .then(data => {
      console.log("Rating saved:", data);
    })
    .catch(err => console.error("Error saving rating:", err));
}

// =================== Helpers ===================
function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function escapeJsString(str) {
  return String(str || "").replace(/'/g, "\\'").replace(/\n/g, "\\n");
}

// =================== Pagination ===================
function renderPagination(totalPages, currentPage) {
  const pagination = document.getElementById("pagination");
  if (!pagination) return;
  pagination.innerHTML = "";

  if (currentPage > 1) {
    const prev = document.createElement("button");
    prev.textContent = "« Prev";
    prev.onclick = () => loadRestaurants(currentPage - 1);
    pagination.appendChild(prev);
  }

  for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
    addPageButton(i, currentPage, pagination);
  }

  if (currentPage < totalPages) {
    const next = document.createElement("button");
    next.textContent = "Next »";
    next.onclick = () => loadRestaurants(currentPage + 1);
    pagination.appendChild(next);
  }
}
function addPageButton(page, currentPage, container) {
  const btn = document.createElement("button");
  btn.textContent = page;
  if (page === currentPage) btn.classList.add("active");
  btn.onclick = () => loadRestaurants(page);
  container.appendChild(btn);
}

// =================== Recommendations ===================
function loadRecommendations() {
  fetch("/api/recommendations")
    .then(res => res.json())
    .then(data => {
      const slider = document.getElementById("recSlider");
      if (!slider) return;
      slider.innerHTML = "";

      if (!data || data.length === 0) {
        slider.innerHTML = "<p>No recommendations available.</p>";
        return;
      }

      data.forEach(r => {
        const image = getRestaurantImage(r);
        const safeName = escapeHtml(r["Restaurant Name"] || "");
        const html = `
          <div class="rec-card" data-name="${escapeJsString(r["Restaurant Name"] || "")}" 
               onclick="openRecommendation('${escapeJsString(r["Restaurant Name"] || "")}')">
            <img src="${image}" alt="${safeName}">
            <h4>${safeName}</h4>
            <p><b>City:</b> ${escapeHtml(r.City || "")}</p>
            <p><b>Cuisine:</b> ${escapeHtml(r.Cuisines || "")}</p>
            <p><b>Rating:</b> ⭐ ${escapeHtml(r["Aggregate rating"] || "")}</p>
          </div>`;
        slider.insertAdjacentHTML("beforeend", html);
      });

      startRecAutoScroll();
    })
    .catch(err => {
      console.error("Error loading recommendations:", err);
      const slider = document.getElementById("recSlider");
      if (slider) slider.innerHTML = "<p>Error loading recommendations.</p>";
    });
}

// ⭐ Auto-scroll carousel for Recommendations ⭐
let recScrollInterval;
function startRecAutoScroll() {
  const slider = document.getElementById("recSlider");
  if (!slider) return;

  if (recScrollInterval) clearInterval(recScrollInterval);

  recScrollInterval = setInterval(() => {
    slider.scrollBy({ left: 250, behavior: "smooth" });
    if (slider.scrollLeft + slider.clientWidth >= slider.scrollWidth) {
      setTimeout(() => {
        slider.scrollTo({ left: 0, behavior: "smooth" });
      }, 1000);
    }
  }, 4000);
}

// =================== Modal for Recommendations ===================
function openRecommendation(name) {
  fetch(`/api/recommend?name=${encodeURIComponent(name)}`)
    .then(res => res.json())
    .then(data => {
      const modal = document.getElementById("recModal");
      const title = document.getElementById("modalTitle");
      const results = document.getElementById("modalResults");

      if (!modal || !title || !results) return;

      title.textContent = `Similar restaurants to "${name}"`;
      results.innerHTML = "";

      (data || []).forEach(r => {
        const image = getRestaurantImage(r);
        const explanationHTML = renderExplanations(r.explanation);
        const html = `
          <div class="rec-card">
            <img src="${image}" alt="${escapeHtml(r["Restaurant Name"] || "")}">
            <h4>${escapeHtml(r["Restaurant Name"] || "")}</h4>
            <p><b>City:</b> ${escapeHtml(r.City || "")}</p>
            <p><b>Cuisine:</b> ${escapeHtml(r.Cuisines || "")}</p>
            <p><b>Rating:</b> ⭐ ${escapeHtml(r["Aggregate rating"] || "")}</p>
            <div class="explanation">💡 ${explanationHTML}</div>
          </div>`;
        results.insertAdjacentHTML("beforeend", html);
      });

      modal.style.display = "block";
    })
    .catch(err => console.error("Error loading recommendations modal:", err));
}

function closeModal() {
  const modal = document.getElementById("recModal");
  if (modal) modal.style.display = "none";
}

// =================== On page load ===================
window.onload = function () {
  loadFilters();
  loadRestaurants();
  loadRecommendations();
  renderWishlist();
};

// =================== Load Filters (Cities & Cuisines) ===================
function loadFilters() {
  fetch("/api/filters")
    .then(res => res.json())
    .then(data => {
      const cityFilter = document.getElementById("cityFilter");
      if (cityFilter && data.cities) {
        cityFilter.innerHTML = `<option value="">-- Select City --</option>`;
        data.cities.forEach(city => {
          cityFilter.innerHTML += `<option value="${escapeHtml(city)}">${escapeHtml(city)}</option>`;
        });
      }

      const cuisineFilter = document.getElementById("cuisineFilter");
      if (cuisineFilter && data.cuisines) {
        cuisineFilter.innerHTML = `<option value="">-- Select Cuisine --</option>`;
        data.cuisines.forEach(cuisine => {
          cuisineFilter.innerHTML += `<option value="${escapeHtml(cuisine)}">${escapeHtml(cuisine)}</option>`;
        });
      }
    })
    .catch(err => console.error("Error loading filters:", err));
}

function scrollCarousel(direction) {
  const slider = document.getElementById("recSlider");
  if (!slider) return;
  const cardWidth = slider.querySelector(".rec-card")?.offsetWidth || 220;
  slider.scrollBy({ left: direction * (cardWidth + 16), behavior: "smooth" });
}
