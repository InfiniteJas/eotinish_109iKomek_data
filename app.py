import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = 'coffee.db'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# ---------- Database ----------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        db.commit()

# ---------- User model ----------

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

def get_user_by_id(user_id):
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if row:
        return User(row['id'], row['username'], row['email'])
    return None

def get_user_by_username(username):
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if row:
        return User(row['id'], row['username'], row['email'])
    return None

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))

# ---------- Routes ----------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if row and check_password_hash(row['password_hash'], password):
            user = User(row['id'], row['username'], row['email'])
            login_user(user)
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('dashboard'))
        flash('Неверное имя пользователя или пароль.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not username or not email or not password:
            flash('Все поля обязательны для заполнения.', 'warning')
            return render_template('register.html')
        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if existing:
            flash('Пользователь с таким именем или email уже существует.', 'warning')
            return render_template('register.html')
        password_hash = generate_password_hash(password)
        db.execute(
            'INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)',
            (username, email, password_hash, datetime.now().isoformat())
        )
        db.commit()
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# ---------- Init ----------

def create_test_user():
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT id FROM users WHERE username = 'test'").fetchone()
        if not row:
            db.execute(
                'INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)',
                ('test', 'test@coffee.kz', generate_password_hash('test123'), datetime.now().isoformat())
            )
            db.commit()

if __name__ == '__main__':
    init_db()
    create_test_user()
    app.run(host='0.0.0.0', port=5001, debug=False)
