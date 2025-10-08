from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import json
import os
import datetime
from collections import Counter

# keep these since you use them elsewhere (hybrid CF)
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# ---------- App ----------
app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # change to a secure random key in production

# ---------- Config ----------
# Turn off TF-IDF in tight-memory environments (Render free) via env var
DISABLE_HEAVY_ML = os.getenv("DISABLE_HEAVY_ML", "0") == "1"

# ---------- File paths ----------
DATA_PATH = os.path.join("data", "restaurants.json")
WISHLIST_PATH = os.path.join("data", "wishlist.json")
USERS_PATH = os.path.join("data", "users.json")
FEEDBACK_PATH = os.path.join("data", "feedback.json")
RATINGS_PATH = os.path.join("data", "ratings.json")  # collaborative filtering storage

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

def load_wishlist(): return load_json(WISHLIST_PATH, [])
def save_wishlist(wishlist): save_json(WISHLIST_PATH, wishlist)
def load_users(): return load_json(USERS_PATH, [])
def save_users(users): save_json(USERS_PATH, users)
def load_feedback(): return load_json(FEEDBACK_PATH, [])
def save_feedback(feedback): save_json(FEEDBACK_PATH, feedback)

def load_ratings():
    """Ratings format: [{user, restaurant, rating, date}]"""
    return load_json(RATINGS_PATH, [])

def save_ratings(ratings): save_json(RATINGS_PATH, ratings)

# If ratings file missing/empty, seed a tiny sample (won't overwrite real data)
if not os.path.exists(RATINGS_PATH) or not load_ratings():
    sample_ratings = [
        {"user": "alice", "restaurant": "Domino's Pizza", "rating": 4.5, "date": "2025-09-19T10:00:00"},
        {"user": "alice", "restaurant": "KFC", "rating": 4.0, "date": "2025-09-19T10:05:00"},
        {"user": "alice", "restaurant": "Burger King", "rating": 3.5, "date": "2025-09-19T10:10:00"},
        {"user": "bob", "restaurant": "KFC", "rating": 5.0, "date": "2025-09-19T11:00:00"},
        {"user": "bob", "restaurant": "McDonald's", "rating": 4.2, "date": "2025-09-19T11:05:00"},
        {"user": "bob", "restaurant": "Subway", "rating": 3.8, "date": "2025-09-19T11:10:00"},
        {"user": "carol", "restaurant": "Domino's Pizza", "rating": 4.8, "date": "2025-09-19T12:00:00"},
        {"user": "carol", "restaurant": "Pizza Hut", "rating": 4.6, "date": "2025-09-19T12:05:00"},
        {"user": "carol", "restaurant": "Subway", "rating": 4.1, "date": "2025-09-19T12:10:00"},
        {"user": "david", "restaurant": "Burger King", "rating": 4.0, "date": "2025-09-19T13:00:00"},
        {"user": "david", "restaurant": "McDonald's", "rating": 4.3, "date": "2025-09-19T13:05:00"},
        {"user": "david", "restaurant": "Pizza Hut", "rating": 3.9, "date": "2025-09-19T13:10:00"},
    ]
    save_ratings(sample_ratings)

# ---------- Load restaurants ----------
restaurants = load_json(DATA_PATH, [])
if not isinstance(restaurants, list):
    restaurants = []

# ---------- ML (content-based) — memory-safe lazy init ----------
# We avoid building an N×N cosine matrix. We only build the TF-IDF matrix once,
# and compute similarities for the requested item on the fly.
df = None
tfidf_matrix = None

def init_ml():
    """Lazily build dataframe + TF-IDF matrix (skips if disabled)."""
    global df, tfidf_matrix
    if DISABLE_HEAVY_ML:
        print("⚠️ TF-IDF disabled via DISABLE_HEAVY_ML=1")
        return
    if df is not None and tfidf_matrix is not None:
        return
    try:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer

        _df = pd.DataFrame(restaurants)
        if "Cuisines" not in _df.columns: _df["Cuisines"] = ""
        if "City" not in _df.columns: _df["City"] = ""
        if "Restaurant Name" not in _df.columns: _df["Restaurant Name"] = _df.index.astype(str)

        text = (_df["Cuisines"].fillna("") + " " + _df["City"].fillna("")).astype(str)

        vectorizer = TfidfVectorizer(stop_words="english", max_features=20000, dtype=np.float32)
        _tfidf = vectorizer.fit_transform(text)

        df = _df
        tfidf_matrix = _tfidf
        print(f"✅ TF-IDF ready (rows={len(df)}, features≤20000)")
    except Exception as e:
        # If anything goes wrong (memory, etc.), keep them None so we fall back later
        df, tfidf_matrix = None, None
        print("⚠️ TF-IDF init failed:", e)

def recommend_restaurants(name, n=5):
    """Content-based recommendations using per-request cosine similarity."""
    if tfidf_matrix is None or df is None:
        init_ml()
    if tfidf_matrix is None or df is None:
        return []  # will fall back in API

    try:
        mask = df["Restaurant Name"].astype(str) == str(name)
        if not mask.any():
            return []
        idx = int(df[mask].index[0])
    except Exception:
        return []

    # similarity = (vector of the restaurant) dot (all vectors)^T
    sim_row = (tfidf_matrix[idx] @ tfidf_matrix.T).toarray().ravel()
    # rank, skip self at 0
    order = sim_row.argsort()[::-1]
    order = [i for i in order if i != idx][:n]

    recs = df.iloc[order][
        ["Restaurant Name", "City", "Cuisines", "Aggregate rating", "Votes"]
    ].to_dict(orient="records")
    return recs

# ---------- Helpers ----------
def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def safe_int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default

# ---------- Explainable AI helper ----------
def explain_recommendation(user_preferences, restaurant):
    reasons = []
    rating_class = "why-neutral"

    for c in user_preferences.get("cuisines", []):
        try:
            if c and c.lower() in str(restaurant.get("Cuisines", "")).lower():
                reasons.append(f"because you like {c} cuisine")
        except Exception:
            pass

    ar = safe_float(restaurant.get("Aggregate rating", restaurant.get("Aggregate rating", 0)))
    if ar >= 4.5:
        reasons.append(f"it has a high rating of {ar}★")
        rating_class = "why-high"
    elif ar >= 3.5:
        reasons.append(f"it has a decent rating of {ar}★")
        rating_class = "why-medium"
    else:
        reasons.append(f"rating is {ar}★")
        rating_class = "why-low"

    if "budget" in user_preferences:
        try:
            cost = safe_int(restaurant.get("Average Cost for two", restaurant.get("Cost for two", 0)))
            if cost and cost <= int(user_preferences.get("budget")):
                reasons.append(f"fits your budget under ₹{user_preferences.get('budget')}")
        except Exception:
            pass

    if user_preferences.get("city"):
        try:
            if str(restaurant.get("City", "")).strip().lower() == str(user_preferences.get("city")).strip().lower():
                reasons.append(f"it's located in your city ({restaurant.get('City')})")
        except Exception:
            pass

    if not reasons:
        reasons = ["matches your preferences"]
        rating_class = "why-neutral"

    return {"text": "Recommended " + ", ".join(reasons), "class": rating_class}

# ---------- Routes ----------
@app.route("/")
def homepage():
    return render_template("home.html")

@app.route("/restaurants")
def restaurants_page():
    """
    Render the main 'All Restaurants' page.
    Adds explanation badges and computes simple insights for charts.
    """
    user_prefs = session.get("user_prefs", {"cuisines": [], "budget": None, "city": None})

    # Add explanation + normalize keys used in templates
    updated_restaurants = []
    for r in restaurants:
        expl = explain_recommendation(user_prefs, r)
        r_copy = dict(r)
        r_copy["explanation"] = expl["text"]
        r_copy["explain_class"] = expl["class"]

        if "Restaurant Name" not in r_copy and "name" in r_copy:
            r_copy["Restaurant Name"] = r_copy.get("name")
        if "Aggregate rating" not in r_copy:
            r_copy["Aggregate rating"] = r_copy.get("rating") or r_copy.get("Aggregate rating", 0)
        if "Votes" not in r_copy:
            r_copy["Votes"] = r_copy.get("votes", 0)
        if "Average Cost for two" not in r_copy:
            r_copy["Average Cost for two"] = r_copy.get("cost", r_copy.get("Average Cost for two", 0))

        updated_restaurants.append(r_copy)

    # Insights
    cuisines_counter = Counter()
    for r in restaurants:
        c_field = r.get("Cuisines") or r.get("cuisine") or ""
        for part in str(c_field).split(","):
            cs = part.strip()
            if cs:
                cuisines_counter[cs] += 1
    top_cuisines = cuisines_counter.most_common(5)

    cities_counter = Counter()
    for r in restaurants:
        city = r.get("City") or r.get("city") or ""
        if city:
            cities_counter[str(city).strip()] += 1
    top_cities = cities_counter.most_common(5)

    top_rated = sorted(
        restaurants,
        key=lambda x: safe_float(x.get("Aggregate rating", x.get("rating", 0))),
        reverse=True
    )[:5]

    top_rated_normalized = [{
        "name": r.get("Restaurant Name") or r.get("name") or r.get("Restaurant_name") or str(r.get("Restaurant Name", "")),
        "rating": safe_float(r.get("Aggregate rating", r.get("rating", 0)))
    } for r in top_rated]

    return render_template(
        "restaurant.html",
        restaurants=updated_restaurants,
        cuisines=top_cuisines,
        cities=top_cities,
        top_rated=top_rated_normalized
    )

@app.route("/wishlist")
def wishlist_page():
    return render_template("wishlist.html")

@app.route("/about")
def about_page():
    return render_template("about.html")

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

    feedback_list = [f for f in load_feedback() if f.get("type") == "feedback"]
    feedback_list = sorted(feedback_list, key=lambda x: x.get("date", ""), reverse=True)
    return render_template("contact_feedback.html", feedback=feedback_list)

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
    search = request.args.get("search", "").strip().lower()
    cities_raw = request.args.get("city", "").strip()
    cuisines_raw = request.args.get("cuisine", "").strip()
    rating = request.args.get("rating", "").strip()
    sort = request.args.get("sort", "").strip()

    mood = request.args.get("mood", "").strip().lower()
    time = request.args.get("time", "").strip().lower()
    budget = request.args.get("budget", "").strip().lower()
    group = request.args.get("group", "").strip().lower()

    page = int(request.args.get("page", 1) or 1)
    per_page = 20

    city_list = [c.strip() for c in cities_raw.split(",") if c.strip()] if cities_raw else []
    cuisine_list = [c.strip().lower() for c in cuisines_raw.split(",") if c.strip()] if cuisines_raw else []

    filtered = restaurants

    if search:
        filtered = [r for r in filtered if search in str(r.get("Restaurant Name", "")).lower()]
    if city_list:
        filtered = [r for r in filtered if str(r.get("City", "")).strip() in city_list]
    if cuisine_list:
        def cuisine_matches(rr):
            cuisines_field = str(rr.get("Cuisines", "")).lower()
            return any(c in cuisines_field for c in cuisine_list)
        filtered = [r for r in filtered if cuisine_matches(r)]
    if rating:
        try:
            min_rating = float(rating)
            filtered = [r for r in filtered if safe_float(r.get("Aggregate rating", 0)) >= min_rating]
        except Exception:
            pass

    # richer explanations
    for r in filtered:
        reasons = []
        if mood and mood in str(r.get("Mood", "")).lower():
            reasons.append(f"Mood={mood.title()}")
        if time and time in str(r.get("Time", "")).lower():
            reasons.append(f"Time={time.title()}")
        if budget and budget in str(r.get("Budget", "")).lower():
            reasons.append(f"Budget={budget.title()}")
        if group and group in str(r.get("Group", "")).lower():
            reasons.append(f"Group={group}")

        ar = safe_float(r.get("Aggregate rating", 0))
        if ar >= 4.5:
            reasons.append(f"Highly rated ⭐ {ar}")
        elif ar >= 4.0:
            reasons.append(f"Good rating ⭐ {ar}")

        v = safe_int(r.get("Votes", 0))
        if v >= 500:
            reasons.append(f"Popular (votes: {v})")
        elif v >= 200:
            reasons.append(f"Well-reviewed (votes: {v})")

        cuisines = str(r.get("Cuisines", "")).strip()
        if cuisines:
            first_cuisine = cuisines.split(",")[0].strip()
            if first_cuisine:
                reasons.append(f"Cuisine: {first_cuisine}")

        if r.get("City"):
            reasons.append(f"City: {r.get('City')}")

        if not reasons:
            reasons = ["General match"]

        r["explanation"] = " | ".join(reasons)

    # sorting
    try:
        if sort == "rating":
            filtered = sorted(filtered, key=lambda rr: safe_float(rr.get("Aggregate rating", 0)), reverse=True)
        elif sort == "votes":
            filtered = sorted(filtered, key=lambda rr: safe_int(rr.get("Votes", 0)), reverse=True)
        elif sort == "cost_low":
            filtered = sorted(filtered, key=lambda rr: safe_int(rr.get("Average Cost for two", 0)))
        elif sort == "cost_high":
            filtered = sorted(filtered, key=lambda rr: safe_int(rr.get("Average Cost for two", 0)), reverse=True)
    except Exception:
        pass

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]

    return jsonify({"restaurants": paginated, "total": total, "page": page, "per_page": per_page})

# ---------- API: Filters ----------
@app.route("/api/filters")
def get_filters():
    cities_set = set()
    cuisines_set = set()
    for r in restaurants:
        city_val = r.get("City")
        if city_val:
            cities_set.add(str(city_val).strip())
        c_field = r.get("Cuisines")
        if c_field:
            for part in str(c_field).split(","):
                cs = part.strip()
                if cs:
                    cuisines_set.add(cs)
    return jsonify({"cities": sorted(cities_set), "cuisines": sorted(cuisines_set)})

# ---------- API: Trending (context-aware) ----------
@app.route("/api/recommendations")
def trending_recommendations():
    weather = request.args.get("weather", "").strip().lower()
    time_of_day = request.args.get("time", "").strip().lower()

    def key_func(r):
        try:
            rating = safe_float(r.get("Aggregate rating", 0))
            votes = safe_int(r.get("Votes", 0))
            return (rating, votes)
        except Exception:
            return (0, 0)

    trending = [r for r in restaurants if safe_float(r.get("Aggregate rating", 0)) > 0]
    trending = sorted(trending, key=key_func, reverse=True)

    if weather or time_of_day:
        prioritized = []
        for r in trending:
            cuisines_text = str(r.get("Cuisines", "")).lower()
            score = 0.0
            if weather == "rainy":
                if any(k in cuisines_text for k in ["soup", "tea", "hot snack", "snack", "pakora", "chai"]):
                    score += 30
            elif weather == "sunny":
                if any(k in cuisines_text for k in ["ice cream", "juice", "cold", "smoothie", "beverage"]):
                    score += 20

            if time_of_day == "morning":
                if any(k in cuisines_text for k in ["breakfast", "brunch", "pancake", "coffee"]):
                    score += 40
            elif time_of_day == "evening":
                if any(k in cuisines_text for k in ["dinner", "snack", "street food"]):
                    score += 25

            score += safe_float(r.get("Aggregate rating", 0)) * 2
            score += safe_int(r.get("Votes", 0)) / 100.0
            prioritized.append((score, r))

        prioritized = sorted(prioritized, key=lambda x: x[0], reverse=True)
        return jsonify([r for _, r in prioritized][:10])

    return jsonify(trending[:10])

# ---------- API: ML-based Recommendations ----------
@app.route("/api/recommend")
def get_recommendations():
    name = request.args.get("name", "")
    results = recommend_restaurants(name)

    if not results:
        # fallback to trending when ML disabled or unavailable
        trending = sorted(
            restaurants,
            key=lambda r: (safe_float(r.get("Aggregate rating", 0)), safe_int(r.get("Votes", 0))),
            reverse=True
        )[:5]
        results = [{
            "Restaurant Name": r.get("Restaurant Name", ""),
            "City": r.get("City", ""),
            "Cuisines": r.get("Cuisines", ""),
            "Aggregate rating": safe_float(r.get("Aggregate rating", 0)),
            "Votes": safe_int(r.get("Votes", 0)),
            "explanation": "Trending pick ⭐"
        } for r in trending]
        return jsonify(results)

    # add explain text relative to the base restaurant
    base = next((x for x in restaurants if x.get("Restaurant Name") == name), None)
    for r in results:
        reasons = []
        if base:
            if r.get("Cuisines") and base.get("Cuisines") and r["Cuisines"].split(",")[0] in base["Cuisines"]:
                reasons.append(f"Similar cuisine 🍽 ({r['Cuisines']})")
            if r.get("City") == base.get("City"):
                reasons.append(f"Same city 🏙 ({r['City']})")
        rating = safe_float(r.get("Aggregate rating", 0))
        if rating >= 4.5:
            reasons.append(f"Highly rated ⭐ {rating}")
        elif rating >= 4.0:
            reasons.append(f"Good rating ⭐ {rating}")
        if not reasons:
            reasons.append("Similar restaurant by overall profile")
        r["explanation"] = " | ".join(reasons)
    return jsonify(results)

# ---------- API: Hybrid Recommender ----------
@app.route("/api/recommend/hybrid")
def get_hybrid_recommendations():
    name = request.args.get("name", "")
    user = session.get("user", None)
    content_recs = recommend_restaurants(name, n=6) if name else []

    ratings = load_ratings()
    collab_recs = []
    try:
        if ratings and user:
            df_r = pd.DataFrame(ratings)
            if {"user", "restaurant", "rating"}.issubset(df_r.columns) and len(df_r) > 0:
                pivot = df_r.pivot_table(index="user", columns="restaurant", values="rating").fillna(0)
                if user in pivot.index:
                    user_vectors = pivot.values
                    sim = cosine_similarity(user_vectors)
                    sim_df = pd.DataFrame(sim, index=pivot.index, columns=pivot.index)
                    sim_scores = sim_df.loc[user].sort_values(ascending=False)
                    top_users = sim_scores.index[1:4].tolist()
                    liked = df_r[df_r["user"].isin(top_users)].groupby("restaurant")["rating"].mean()
                    liked = liked[liked >= 4.0].sort_values(ascending=False)
                    top_restaurants = liked.index.tolist()[:6]
                    collab_recs = [r for r in restaurants if r.get("Restaurant Name") in top_restaurants]
    except Exception:
        collab_recs = []

    combined, seen = [], set()
    for r in content_recs + collab_recs:
        name_key = r.get("Restaurant Name")
        if not name_key or name_key in seen:
            continue
        seen.add(name_key)
        if "explanation" not in r:
            r["explanation"] = "Hybrid recommendation"
        combined.append(r)

    if not combined:
        combined = (restaurants[:10] if restaurants else [])
    return jsonify(combined[:10])

# ---------- API: Save rating ----------
@app.route("/api/rate", methods=["POST"])
def save_rating():
    data = request.json or {}
    restaurant = data.get("restaurant")
    rating = data.get("rating")
    if not restaurant or rating is None:
        return jsonify({"message": "restaurant and rating required"}), 400

    user = session.get("user", "guest")
    try:
        rating_val = float(rating)
    except Exception:
        return jsonify({"message": "invalid rating"}), 400

    ratings = load_ratings()
    updated = False
    for r in ratings:
        if r.get("user") == user and r.get("restaurant") == restaurant:
            r["rating"] = rating_val
            r["date"] = datetime.datetime.now().isoformat()
            updated = True
            break
    if not updated:
        ratings.append({
            "user": user,
            "restaurant": restaurant,
            "rating": rating_val,
            "date": datetime.datetime.now().isoformat()
        })
    save_ratings(ratings)
    return jsonify({"message": "rating saved"})

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

# ---------- Analytics (sample) ----------
@app.route("/api/analytics")
def analytics():
    cuisines = {"labels": ["Indian", "Chinese", "Japanese", "Italian"], "counts": [12, 8, 5, 7]}
    ratings = [15, 9, 4]  # Excellent, Good, Average
    return jsonify({"cuisines": cuisines, "ratings": ratings})

# ---------- Run ----------
if __name__ == "__main__":
    # For local dev; Render uses gunicorn per your Procfile
    app.run(debug=True, host="0.0.0.0", port=5000)
