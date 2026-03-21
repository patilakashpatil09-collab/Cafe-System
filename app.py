# app.py
import os
import json
import base64
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, abort
)

# Optional QR code support
try:
    import qrcode
    QR_AVAILABLE = True
except Exception:
    QR_AVAILABLE = False

# --------------------
# Configuration
# --------------------
app = Flask(__name__)
app.secret_key = os.environ.get("ROYAL_CAFE_SECRET", "change_this_secret_for_prod")

# Paths
BASE_DIR = os.path.dirname(__file__)
MENU_FILE = os.path.join(BASE_DIR, "menu.json")
CUSTOMERS_FILE = os.path.join(BASE_DIR, "customers.json")
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback.json")

# Demo image location (developer note)
DEMO_IMAGE_PATH = "/mnt/data/Screenshot 2025-11-28 185144.png"

# --------------------
# Helpers: JSON read/write
# --------------------
def ensure_json_file(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)

def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# --------------------
# Utility functions
# --------------------
def now_ist():
    """Return current IST as string 'YYYY-MM-DD HH:MM:SS'"""
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Admin login required.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def get_orders():
    return load_json(ORDERS_FILE)

def save_orders(orders):
    save_json(ORDERS_FILE, orders)

# --------------------
# Ensure files exist with defaults
# --------------------
ensure_json_file(MENU_FILE, {
    "1": {"name": "Pasta", "price": 150, "images": "/static/images/pasta.jpg"},
    "3": {"name": "Veg Sandwich", "price": 120, "images": "/static/images/sandwich.jpg"},
    "4": {"name": "Pizza", "price": 79, "images": "/static/images/pizza.jpg"},
    "5": {"name": "Milk Shake", "price": 35, "images": "/static/images/milkshake.jpg"},
    "6": {"name": "Coffee", "price": 25, "images": "/static/images/coffee.jpg"},
    "7": {"name": "Burger", "price": 147, "images": "/static/images/burger.jpg"},
    "8": {"name": "Cold Drink", "price": 20, "images": "/static/images/cold_drinks.png"}
})
ensure_json_file(CUSTOMERS_FILE, {})
ensure_json_file(ORDERS_FILE, {})
ensure_json_file(FEEDBACK_FILE, {})

# --------------------
# Routes
# --------------------
@app.route("/")
def index():
    menu = load_json(MENU_FILE)
    return render_template("index.html", menu=menu, cafe_name="Royal Cafe")

# --------------------
# Customer: signup/login/logout/dashboard
# --------------------
@app.route("/customer/signup", methods=["GET", "POST"])
def customer_signup():
    if request.method == "POST":
        users = load_json(CUSTOMERS_FILE)
        email = request.form.get("email", "").strip().lower()
        if not email:
            email = request.form.get("customer_id", "").strip().lower()
        if not email:
            flash("Please provide email or ID.", "warning")
            return redirect(url_for("customer_signup"))
        if email in users:
            flash("Email/ID already registered.", "danger")
            return redirect(url_for("customer_signup"))
        users[email] = {
            "name": request.form.get("name", "") or request.form.get("customer_name", ""),
            "password": request.form.get("password", "")
        }
        save_json(CUSTOMERS_FILE, users)
        flash("Signup successful. Please login.", "success")
        return redirect(url_for("customer_login"))
    return render_template("customer_signup.html", cafe_name="Royal Cafe")

@app.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        # This project uses a simple non-password login for quick cafe usage
        customer_id = request.form.get("customer_id", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        place = request.form.get("place", "").strip()
        contact = request.form.get("contact", "").strip()

        if all([customer_id, customer_name, place, contact]):
            session["customer"] = {
                "id": customer_id,
                "name": customer_name,
                "place": place,
                "contact": contact,
                "email": customer_id
            }
            flash(f"Welcome, {customer_name}!", "success")
            return redirect(url_for("customer_dashboard"))
        else:
            flash("Please fill all the fields.", "warning")

    return render_template("customer_login.html", cafe_name="Royal Cafe")

@app.route("/customer/logout")
def customer_logout():
    session.pop("customer", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/customer/dashboard")
def customer_dashboard():
    if not session.get("customer"):
        flash("Please login first.", "warning")
        return redirect(url_for("customer_login"))

    menu = load_json(MENU_FILE)
    orders = get_orders()
    customer_email = session["customer"].get("email") or session["customer"].get("id")
    session["customer"]["email"] = customer_email
    my_orders = {oid: o for oid, o in orders.items() if o.get("customer") == customer_email}
    return render_template("customer_dashboard.html", menu=menu, orders=my_orders, cafe_name="Royal Cafe")

# --------------------
# Admin: login/logout/dashboard/menu management
# --------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == "admin" and password == "1234":
            session["admin_logged_in"] = True
            flash("Admin logged in.", "success")
            return redirect(url_for("admin"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html", cafe_name="Royal Cafe")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    menu = load_json(MENU_FILE)
    return render_template("admin.html", menu=menu, cafe_name="Royal Cafe")

@app.route("/admin/menu/add", methods=["POST"])
@admin_required
def add_menu_item():
    menu = load_json(MENU_FILE)
    item_id = str(int(datetime.utcnow().timestamp() * 1000))
    try:
        price = float(request.form.get("price", 0) or 0)
    except ValueError:
        price = 0.0
    menu[item_id] = {
        "name": request.form.get("name", ""),
        "price": price,
        "images": request.form.get("images", ""),
        "added_at": now_ist()
    }
    save_json(MENU_FILE, menu)
    flash("Item added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/menu/delete/<item_id>")
@admin_required
def delete_menu_item(item_id):
    menu = load_json(MENU_FILE)
    if item_id in menu:
        menu.pop(item_id)
        save_json(MENU_FILE, menu)
        flash("Item deleted.", "info")
    return redirect(url_for("admin"))

# --------------------
# Place order
# --------------------
@app.route("/order", methods=["POST"])
def place_order():
    if not session.get("customer"):
        flash("Please login first.", "warning")
        return redirect(url_for("customer_login"))

    menu = load_json(MENU_FILE)
    orders = get_orders()
    order_items = []
    total = 0.0

    for key, val in request.form.items():
        if key.startswith("qty_"):
            item_id = key.split("_", 1)[1]
            try:
                qty = int(val or 0)
            except ValueError:
                qty = 0
            if qty > 0 and item_id in menu:
                item = menu[item_id]
                subtotal = float(item.get("price", 0)) * qty
                order_items.append({
                    "item_id": item_id,
                    "name": item.get("name", ""),
                    "price": float(item.get("price", 0)),
                    "qty": qty,
                    "subtotal": round(subtotal, 2)
                })
                total += subtotal

    if not order_items:
        flash("No items selected.", "warning")
        return redirect(url_for("index"))

    customer_email = session["customer"].get("email") or session["customer"].get("id")
    session["customer"]["email"] = customer_email

    order_id = str(int(datetime.utcnow().timestamp() * 1000))
    order = {
        "id": order_id,
        "customer": customer_email,
        "name": session["customer"].get("name", ""),
        "place": session["customer"].get("place", ""),
        "contact": session["customer"].get("contact", ""),
        "items": order_items,
        "total": round(total, 2),
        "status": "placed",
        "payment_status": "pending",
        "created_at": now_ist(),
        "start_time": None,
        "completed_at": None,
        "wait_time": None
    }
    orders[order_id] = order
    save_orders(orders)
    flash("Order placed successfully!", "success")
    return redirect(url_for("customer_dashboard"))

# --------------------
# View orders (generic)
# --------------------
@app.route("/orders")
def view_orders():
    orders = get_orders()
    return render_template("orders.html", orders=orders, cafe_name="Royal Cafe")

# --------------------
# Edit / Cancel order
# --------------------
@app.route("/order/edit/<order_id>", methods=["GET", "POST"])
def edit_order(order_id):
    orders = get_orders()
    menu = load_json(MENU_FILE)
    order = orders.get(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer_dashboard") if session.get("customer") else url_for("view_orders"))

    # Only admin or the ordering customer can edit
    if not session.get("admin_logged_in"):
        if not session.get("customer") or session["customer"].get("email") != order.get("customer"):
            flash("You can only edit your own orders.", "danger")
            return redirect(url_for("customer_dashboard"))

    if request.method == "POST":
        new_items = []
        total = 0.0
        for key, val in request.form.items():
            if key.startswith("qty_"):
                item_id = key.split("_", 1)[1]
                try:
                    qty = int(val or 0)
                except ValueError:
                    qty = 0
                if qty > 0 and item_id in menu:
                    item = menu[item_id]
                    subtotal = float(item.get("price", 0)) * qty
                    new_items.append({
                        "item_id": item_id,
                        "name": item.get("name", ""),
                        "price": float(item.get("price", 0)),
                        "qty": qty,
                        "subtotal": round(subtotal, 2)
                    })
                    total += subtotal
        order["items"] = new_items
        order["total"] = round(total, 2)
        order["status"] = "edited"
        order["edited_at"] = now_ist()
        orders[order_id] = order
        save_orders(orders)
        flash("Order updated successfully!", "success")
        if session.get("admin_logged_in"):
            return redirect(url_for("view_orders"))
        return redirect(url_for("customer_dashboard"))

    return render_template("edit_order.html", order=order, menu=menu, cafe_name="Royal Cafe")

@app.route("/order/cancel/<order_id>")
def cancel_order(order_id):
    orders = get_orders()
    if order_id in orders:
        orders[order_id]["status"] = "cancelled"
        orders[order_id]["cancelled_at"] = now_ist()
        save_orders(orders)
        flash("Order cancelled.", "info")
    if session.get("admin_logged_in"):
        return redirect(url_for("view_orders"))
    if session.get("customer"):
        return redirect(url_for("customer_dashboard"))
    return redirect(url_for("view_orders"))

# --------------------
# Payment / Final bill
# --------------------
@app.route("/payment_success/<order_id>", methods=["POST"])
def payment_success(order_id):
    orders = get_orders()
    order = orders.get(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("view_orders"))
    order["payment_status"] = "paid"
    order["paid_at"] = now_ist()
    orders[order_id] = order
    save_orders(orders)
    flash("Payment received!", "success")
    return redirect(url_for("final_bill", order_id=order_id))

@app.route("/final_bill/<order_id>")
def final_bill(order_id):
    orders = get_orders()
    order = orders.get(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("view_orders"))

    qr_b64 = None
    if QR_AVAILABLE:
        upi_id = os.environ.get("ROYAL_CAFE_UPI", "yourupiid@okaxis")
        amount = "{:.2f}".format(float(order.get("total", 0) or 0))
        # Simple UPI payment string (could be improved)
        payment_link = f"upi://pay?pa={upi_id}&pn=Royal%20Cafe&am={amount}&cu=INR"
        qr = qrcode.make(payment_link)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template("final_bill.html", order=order, qr_code=qr_b64, cafe_name="Royal Cafe")

# --------------------
# Feedback
# --------------------
@app.route("/feedback/<order_id>", methods=["GET", "POST"])
def feedback(order_id):
    orders = get_orders()
    feedbacks = load_json(FEEDBACK_FILE)
    order = orders.get(order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("index"))

    # Allow feedback only after paid or completed
    if order.get("payment_status") != "paid" and order.get("status") != "completed":
        flash("Please complete payment before giving feedback.", "warning")
        return redirect(url_for("final_bill", order_id=order_id))

    # Customer check
    if not session.get("customer") or session["customer"].get("email") != order.get("customer"):
        flash("Please login with the account that placed this order to give feedback.", "warning")
        return redirect(url_for("customer_login"))

    if request.method == "POST":
        feedback_id = str(int(datetime.utcnow().timestamp() * 1000))
        feedback_data = {
            "id": feedback_id,
            "order_id": order_id,
            "customer": order.get("customer"),
            "name": order.get("name"),
            "rating": request.form.get("rating", ""),
            "comment": request.form.get("comment", ""),
            "submitted_at": now_ist()
        }
        feedbacks[feedback_id] = feedback_data
        save_json(FEEDBACK_FILE, feedbacks)
        flash("Thank you for your feedback!", "success")
        return redirect(url_for("index"))

    return render_template("feedback.html", order=order, cafe_name="Royal Cafe")

# Admin feedback dashboard
@app.route("/admin/feedbacks")
@admin_required
def admin_feedbacks():
    feedbacks = load_json(FEEDBACK_FILE)
    return render_template("feedback_dashboard.html", feedbacks=feedbacks, cafe_name="Royal Cafe")

@app.route("/admin/feedback/delete/<fid>")
@admin_required
def delete_feedback(fid):
    feedbacks = load_json(FEEDBACK_FILE)
    if fid in feedbacks:
        feedbacks.pop(fid)
        save_json(FEEDBACK_FILE, feedbacks)
        flash("Feedback deleted successfully.", "info")
    return redirect(url_for("admin_feedbacks"))

# --------------------
# Staff: view / start / complete
# --------------------
@app.route("/staff")
def staff_dashboard():
    orders = get_orders()
    active_orders = {oid: o for oid, o in orders.items() if o.get("status") in ["placed", "preparing"]}
    return render_template("staff.html", orders=active_orders, cafe_name="Royal Cafe")

@app.route("/staff/start/<order_id>", methods=["GET"])
def mark_order_preparing(order_id):
    orders = get_orders()
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    order["status"] = "preparing"
    order["start_time"] = now_ist()
    orders[order_id] = order
    save_orders(orders)
    return jsonify({"status": "ok", "order_id": order_id, "new_status": "preparing"})

@app.route("/staff/complete/<order_id>", methods=["GET"])
def mark_order_complete(order_id):
    orders = get_orders()
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    order["status"] = "completed"
    order["completed_at"] = now_ist()
    try:
        if order.get("start_time"):
            fmt = "%Y-%m-%d %H:%M:%S"
            start_dt = datetime.strptime(order["start_time"], fmt)
            end_dt = datetime.strptime(order["completed_at"], fmt)
            order["wait_time"] = str(int((end_dt - start_dt).total_seconds() // 60)) + " mins"
    except Exception:
        order["wait_time"] = "N/A"
    orders[order_id] = order
    save_orders(orders)
    return jsonify({"status": "ok", "order_id": order_id, "new_status": "completed"})

# --------------------
# Reports (original)
# --------------------
@app.route("/report")
@admin_required
def report():
    orders = get_orders()
    total_orders = len(orders)
    total_revenue = sum(float(o.get("total", 0) or 0) for o in orders.values() if o.get("payment_status") == "paid")
    paid_orders = sum(1 for o in orders.values() if o.get("payment_status") == "paid")
    cancelled_orders = sum(1 for o in orders.values() if o.get("status") == "cancelled")
    return render_template("report.html",
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           paid_orders=paid_orders,
                           cancelled_orders=cancelled_orders,
                           orders=orders,
                           cafe_name="Royal Cafe")

# --------------------
# Advanced Reports: daily / weekly / monthly + popular items
# --------------------
@app.route("/report/advanced")
@admin_required
def report_advanced():
    orders = get_orders()

    # helper to convert order created_at to datetime (IST)
    def to_dt(order):
        try:
            return datetime.strptime(order.get("created_at", ""), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_day - timedelta(days=now.weekday())  # Monday as start
    start_of_month = start_of_day.replace(day=1)

    daily_orders = {}
    weekly_orders = {}
    monthly_orders = {}

    item_count = {}  # name -> total qty

    for oid, o in orders.items():
        dt = to_dt(o)
        if not dt:
            continue

        # Consider dt in IST already (we store created_at as IST)
        if dt >= start_of_day:
            daily_orders[oid] = o
        if dt >= start_of_week:
            weekly_orders[oid] = o
        if dt >= start_of_month:
            monthly_orders[oid] = o

        for item in o.get("items", []):
            name = item.get("name", "").strip()
            qty = int(item.get("qty", 0) or 0)
            if name:
                item_count[name] = item_count.get(name, 0) + qty

    popular_items_sorted = sorted(item_count.items(), key=lambda x: x[1], reverse=True)

    return render_template("report_advanced.html",
                           daily_orders=daily_orders,
                           weekly_orders=weekly_orders,
                           monthly_orders=monthly_orders,
                           popular_items=popular_items_sorted,
                           cafe_name="Royal Cafe")

# --------------------
# API endpoints
# --------------------
@app.route("/api/order/<order_id>")
def api_order(order_id):
    orders = get_orders()
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": order.get("id"),
        "status": order.get("status"),
        "payment_status": order.get("payment_status"),
        "total": order.get("total"),
        "items": order.get("items"),
        "start_time": order.get("start_time"),
        "completed_at": order.get("completed_at"),
        "wait_time": order.get("wait_time", ""),
        "place": order.get("place", ""),
        "contact": order.get("contact", "")
    })

@app.route("/api/orders")
def api_orders():
    return jsonify(get_orders())

@app.route("/api/menu")
def api_menu():
    return jsonify(load_json(MENU_FILE))

# --------------------
# Demo image route
# --------------------
@app.route("/demo_image")
def demo_image():
    if os.path.exists(DEMO_IMAGE_PATH):
        return send_file(DEMO_IMAGE_PATH)
    return "Demo image not found on server.", 404

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    # debug True for development, set to False for production
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
