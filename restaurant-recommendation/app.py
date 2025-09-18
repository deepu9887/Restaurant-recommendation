from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import json
import os
import pandas as pd
import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # change to a secure random key in production

# ---------- File paths ----------
DATA_PATH = os.path.join("data", "restaurants.json")
WISHLIST_PATH = os.path.join("data", "wishlist.json")
USERS_PATH = os.path.join("data", "users.json")
FEEDBACK_PATH = os.path.join("data", "feedback.json")


# ---------- Safe JSON helpers ----------
def load_json(path, default=None):
    if default is None:
        default = []
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_wishlist():
    return load_json(WISHLIST_PATH, [])


def save_wishlist(wishlist):
    save_json(WISHLIST_PATH, wishlist)


def load_users():
    return load_json(USERS_PATH, [])


def save_users(users):
    save_json(USERS_PATH, users)


def load_feedback():
    return load_json(FEEDBACK_PATH, [])


def save_feedback(feedback):
    save_json(FEEDBACK_PATH, feedback)


# ---------- Load restaurants dataset ----------
restaurants = load_json(DATA_PATH, [])

# Defensive: ensure restaurants is a list of dicts
if not isinstance(restaurants, list):
    restaurants = []

# ---------- ML Recommendations setup (if dataset large, consider lazy init) ----------
try:
    df = pd.DataFrame(restaurants)
    if "Cuisines" not in df.columns:
        df["Cuisines"] = ""
    df["Cuisines"] = df["Cuisines"].fillna("")
    if "City" not in df.columns:
        df["City"] = ""
    tfidf = TfidfVectorizer(stop_words="english")
    # combine cuisines + city for basic similarity
    tfidf_matrix = tfidf.fit_transform(df["Cuisines"].astype(str) + " " + df["City"].astype(str))
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
except Exception:
    # If something goes wrong with pandas or ML setup, provide safe defaults
    df = pd.DataFrame(columns=["Restaurant Name", "City", "Cuisines", "Aggregate rating", "Votes"])
    cosine_sim = None


def recommend_restaurants(name, n=5):
    """
    Return up to `n` similar restaurants to `name`.
    If name not found or ML unavailable, return empty list.
    """
    if cosine_sim is None:
        return []
    if name not in df["Restaurant Name"].values:
        return []
    try:
        idx = int(df[df["Restaurant Name"] == name].index[0])
    except Exception:
        return []
    sim_scores = list(enumerate(cosine_sim[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[1:n + 1]  # skip itself
    restaurant_indices = [i[0] for i in sim_scores]
    return df.iloc[restaurant_indices][
        ["Restaurant Name", "City", "Cuisines", "Aggregate rating", "Votes"]
    ].to_dict(orient="records")


# ---------- Routes ----------
@app.route("/")
def homepage():
    return render_template("home.html")


@app.route("/restaurants")
def restaurants_page():
    return render_template("restaurant.html")


@app.route("/wishlist")
def wishlist_page():
    return render_template("wishlist.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


# ---------- Contact & Feedback ----------
@app.route("/contact-feedback", methods=["GET", "POST"])
def contact_feedback_page():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        feedback = load_feedback()

        entry = {
            "type": form_type or "contact",
            "name": name,
            "email": email,
            "message": message,
            "rating": None,
            "date": datetime.datetime.now().strftime("%b %d, %Y - %I:%M %p")
        }

        if form_type == "feedback":
            entry["rating"] = request.form.get("rating")

        feedback.append(entry)
        save_feedback(feedback)

        if form_type == "feedback":
            flash("✅ Thank you for your feedback!", "success")
        else:
            flash("📩 Your message has been sent! Thank you for contacting us.", "success")

        return redirect(url_for("contact_feedback_page"))

    # only show feedback entries (not contact messages)
    feedback_list = [f for f in load_feedback() if f.get("type") == "feedback"]
    feedback_list = sorted(feedback_list, key=lambda x: x.get("date", ""), reverse=True)
    return render_template("contact_feedback.html", feedback=feedback_list)


# ---------- Auth (merged login/signup) ----------
@app.route("/auth", methods=["GET", "POST"])
def auth_page():
    users = load_users()
    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "login":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = next((u for u in users if u.get("username") == username and u.get("password") == password), None)
            if user:
                session["user"] = username
                flash("✅ Login successful!", "success")
                return redirect(url_for("homepage"))
            else:
                flash("❌ Invalid username or password", "error")

        elif form_type == "signup":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")

            if not username or not password:
                flash("⚠️ Username and password are required", "error")
            elif any(u.get("username") == username for u in users):
                flash("⚠️ Username already taken!", "error")
            else:
                users.append({"username": username, "email": email, "password": password})
                save_users(users)
                flash("✅ Signup successful! Please login.", "success")

        return redirect(url_for("auth_page"))

    return render_template("auth.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("ℹ️ You have been logged out.", "info")
    return redirect(url_for("homepage"))


# ---------- API: Restaurants ----------
@app.route("/api/restaurants")
def get_restaurants():
    """
    Query string:
      - search (substring on Restaurant Name)
      - city (single value or comma-separated list)
      - cuisine (single value or comma-separated list; matching is case-insensitive substring)
      - rating (min aggregate rating as number)
      - sort (rating|votes|cost_low|cost_high)
      - page (pagination, 1-based)
    """
    search = request.args.get("search", "").strip().lower()
    cities_raw = request.args.get("city", "").strip()
    cuisines_raw = request.args.get("cuisine", "").strip()
    rating = request.args.get("rating", "").strip()
    sort = request.args.get("sort", "").strip()
    page = int(request.args.get("page", 1) or 1)
    per_page = 20

    # parse multi-values: allow both single value and comma-separated lists
    city_list = [c.strip() for c in cities_raw.split(",") if c.strip()] if cities_raw else []
    cuisine_list = [c.strip().lower() for c in cuisines_raw.split(",") if c.strip()] if cuisines_raw else []

    filtered = restaurants

    if search:
        filtered = [r for r in filtered if search in str(r.get("Restaurant Name", "")).lower()]

    if city_list:
        # exact match on City field (case-sensitive as stored); normalize both sides if you prefer
        filtered = [r for r in filtered if str(r.get("City", "")).strip() in city_list]

    if cuisine_list:
        def cuisine_matches(r):
            cuisines_field = str(r.get("Cuisines", "")).lower()
            return any(c in cuisines_field for c in cuisine_list)
        filtered = [r for r in filtered if cuisine_matches(r)]

    if rating:
        try:
            min_rating = float(rating)
            filtered = [r for r in filtered if float(r.get("Aggregate rating", 0) or 0) >= min_rating]
        except Exception:
            pass

    # Sorting (defensive numeric conversions)
    try:
        if sort == "rating":
            filtered = sorted(filtered, key=lambda r: float(r.get("Aggregate rating", 0) or 0), reverse=True)
        elif sort == "votes":
            filtered = sorted(filtered, key=lambda r: int(float(r.get("Votes", 0) or 0)), reverse=True)
        elif sort == "cost_low":
            filtered = sorted(filtered, key=lambda r: int(float(r.get("Average Cost for two", 0) or 0)))
        elif sort == "cost_high":
            filtered = sorted(filtered, key=lambda r: int(float(r.get("Average Cost for two", 0) or 0)), reverse=True)
    except Exception:
        # if conversion fails for any record, skip sort
        pass

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]

    return jsonify({
        "restaurants": paginated,
        "total": total,
        "page": page,
        "per_page": per_page
    })


# ---------- API: Filters (cities + cuisines) ----------
@app.route("/api/filters")
def get_filters():
    """
    Returns JSON:
      { "cities": [...], "cuisines": [...] }
    Cities and cuisines are cleaned strings (trimmed). Cuisines are split on comma.
    """
    # Unique cities (cleaned)
    cities_set = set()
    for r in restaurants:
        city_val = r.get("City")
        if city_val:
            city_str = str(city_val).strip()
            if city_str:
                cities_set.add(city_str)

    # Unique cuisines (split by comma, cleaned)
    cuisines_set = set()
    for r in restaurants:
        c_field = r.get("Cuisines")
        if c_field:
            for part in str(c_field).split(","):
                cs = part.strip()
                if cs:
                    cuisines_set.add(cs)

    cities = sorted(cities_set)
    cuisines = sorted(cuisines_set)

    return jsonify({"cities": cities, "cuisines": cuisines})


# ---------- API: Trending Recommendations ----------
@app.route("/api/recommendations")
def trending_recommendations():
    # sort by rating then votes (defensive conversions)
    def key_func(r):
        try:
            return (float(r.get("Aggregate rating", 0) or 0), int(float(r.get("Votes", 0) or 0)))
        except Exception:
            return (0, 0)

    trending = sorted(restaurants, key=key_func, reverse=True)
    return jsonify(trending[:10])


# ---------- API: ML-based Recommendations ----------
@app.route("/api/recommend")
def get_recommendations():
    name = request.args.get("name", "")
    results = recommend_restaurants(name)
    return jsonify(results)


# ---------- API: Wishlist ----------
@app.route("/api/wishlist", methods=["GET"])
def get_wishlist():
    return jsonify(load_wishlist())


@app.route("/api/wishlist", methods=["POST"])
def add_to_wishlist():
    data = request.json or {}
    wishlist = load_wishlist()
    name = data.get("name") or data.get("Restaurant Name") or ""
    if not name:
        return jsonify({"message": "Missing name"}), 400

    if any(item.get("name") == name or item.get("Restaurant Name") == name for item in wishlist):
        return jsonify({"message": "Already in wishlist"}), 400

    wishlist.append({"name": name})
    save_wishlist(wishlist)
    return jsonify({"message": "Added to wishlist"}), 201


@app.route("/api/wishlist/<name>", methods=["DELETE"])
def remove_from_wishlist(name):
    wishlist = load_wishlist()
    wishlist = [item for item in wishlist if item.get("name") != name and item.get("Restaurant Name") != name]
    save_wishlist(wishlist)
    return jsonify({"message": "Removed from wishlist"})


# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
