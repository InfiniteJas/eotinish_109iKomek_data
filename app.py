import os
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coffeehouse.db")

MENU_ITEMS = [
    {"name": "Эспрессо", "description": "Насыщенный классический эспрессо", "price": 350},
    {"name": "Капучино", "description": "Мягкий капучино с нежной пенкой", "price": 450},
    {"name": "Латте", "description": "Нежный латте с молочной пенкой", "price": 450},
    {"name": "Американо", "description": "Лёгкий американо для бодрого утра", "price": 400},
    {"name": "Флэт Уайт", "description": "Насыщенный флэт уайт из Австралии", "price": 500},
    {"name": "Раф", "description": "Сливочный раф с ванилью", "price": 550},
    {"name": "Мокко", "description": "Шоколадно-кофейное удовольствие", "price": 500},
    {"name": "Матча латте", "description": "Зелёный чай матча с молоком", "price": 600},
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    cursor = db.cursor()
    for item in MENU_ITEMS:
        cursor.execute(
            "INSERT OR IGNORE INTO menu (name, description, price) VALUES (?, ?, ?)",
            (item["name"], item["description"], item["price"]),
        )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view


@app.route("/")
def index():
    db = get_db()
    menu = db.execute("SELECT * FROM menu").fetchall()
    return render_template("index.html", menu=menu)


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        error = None
        if not username:
            error = "Введите имя пользователя."
        elif not password:
            error = "Введите пароль."
        elif len(password) < 6:
            error = "Пароль должен содержать минимум 6 символов."
        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = f"Пользователь {username} уже существует."
            else:
                return redirect(url_for("login"))
        flash(error)
    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()
        if user is None:
            error = "Неверное имя пользователя."
        elif not check_password_hash(user["password"], password):
            error = "Неверный пароль."
        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        flash(error)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/profile")
@login_required
def profile():
    db = get_db()
    orders = db.execute(
        "SELECT o.*, m.name AS item_name FROM orders o "
        "JOIN menu m ON o.menu_id = m.id WHERE o.user_id = ? ORDER BY o.created DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("profile.html", orders=orders)


@app.route("/order/<int:menu_id>", methods=("POST",))
@login_required
def order(menu_id):
    quantity = int(request.form.get("quantity", 1))
    db = get_db()
    item = db.execute("SELECT * FROM menu WHERE id = ?", (menu_id,)).fetchone()
    if item is None:
        flash("Товар не найден.")
        return redirect(url_for("index"))
    total = item["price"] * quantity
    db.execute(
        "INSERT INTO orders (user_id, menu_id, quantity, total) VALUES (?, ?, ?, ?)",
        (session["user_id"], menu_id, quantity, total),
    )
    db.commit()
    flash(f"Заказ оформлен: {item['name']} x{quantity}")
    return redirect(url_for("index"))


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("База данных инициализирована.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
