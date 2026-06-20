from flask import Flask, request, render_template_string, redirect, url_for, session
import os, sqlite3, hashlib

app = Flask(__name__)
app.secret_key = os.urandom(32)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

FLAG_WEB = os.environ.get('FLAG_WEB', 'ctf{ssti_escape_master}')
INTERNAL_HOST = os.environ.get('INTERNAL_HOST', '172.20.0.5')
INTERNAL_USER = os.environ.get('INTERNAL_USER', 'ctfuser')
INTERNAL_PASS = os.environ.get('INTERNAL_PASS', 'SuperSecret123')

app.config['INTERNAL_CREDS'] = {
    'host': INTERNAL_HOST,
    'user': INTERNAL_USER,
    'pass': INTERNAL_PASS
}

DB_PATH = '/tmp/crm.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, is_admin INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY, user_id INTEGER, client_name TEXT, product TEXT,
        amount REAL, status TEXT DEFAULT 'new', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute("INSERT OR IGNORE INTO users (id, username, password, is_admin) VALUES (1, 'admin', ?, 1)",
              (hashlib.sha256('admin123'.encode()).hexdigest(),))
    c.execute("INSERT OR IGNORE INTO users (id, username, password, is_admin) VALUES (2, 'manager', ?, 0)",
              (hashlib.sha256('manager123'.encode()).hexdigest(),))
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = hashlib.sha256(request.form.get('password', '').encode()).hexdigest()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
    
    template = open(os.path.join(TEMPLATES_DIR, 'login.html')).read()
    # УЯЗВИМОСТЬ: error вставляется напрямую в строку шаблона
    template_with_error = template.replace('{{ error }}', error)
    return render_template_string(template_with_error, session=session, os=os)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = ''
    success = ''
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        if not username or not password:
            error = 'Username and password are required'
        elif password != password_confirm:
            error = 'Passwords do not match'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters'
        else:
            conn = get_db()
            existing = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                error = 'Username already exists'
            else:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                conn.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, 0)",
                             (username, password_hash))
                conn.commit()
                success = 'Registration successful! Please login.'
            conn.close()
    
    template = open(os.path.join(TEMPLATES_DIR, 'register.html')).read()
    template_with_error = template.replace('{{ error }}', error).replace('{{ success }}', success)
    return render_template_string(template_with_error, session=session, os=os)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    total_orders = conn.execute("SELECT COUNT(*) as count FROM orders").fetchone()['count']
    my_orders = conn.execute("SELECT COUNT(*) as count FROM orders WHERE user_id = ?", (session['user_id'],)).fetchone()['count']
    recent = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 5").fetchall()
    conn.close()
    
    # УЯЗВИМОСТЬ: name вставляется напрямую в строку шаблона через f-string
    # Это позволяет SSTI, потому что render_template_string выполняет Jinja2 в итоговой строке
    name = request.args.get('name', session.get('username', 'User'))
    
    # Читаем базовый шаблон
    base_template = open(os.path.join(TEMPLATES_DIR, 'dashboard.html')).read()
    
    # УЯЗВИМОСТЬ: f-string вставляет name напрямую в HTML-строку
    # Затем render_template_string выполняет Jinja2 в этой строке
    welcome_html = f'<h1>Welcome, {name}!</h1>'
    
    # Вставляем welcome_html в шаблон через replace (не через Jinja2 переменную!)
    # Это важно: replace вставляет сырую строку до обработки Jinja2
    full_template = base_template.replace('{{ welcome_message }}', welcome_html)
    
    # Теперь render_template_string выполняет Jinja2 в полной строке
    # Если name содержит {{7*7}}, оно будет выполнено как Jinja2!
    return render_template_string(full_template, session=session, total_orders=total_orders, my_orders=my_orders, recent_orders=recent, os=os)

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    if session.get('is_admin'):
        all_orders = conn.execute("SELECT o.*, u.username as manager FROM orders o LEFT JOIN users u ON o.user_id = u.id").fetchall()
    else:
        all_orders = conn.execute("SELECT o.*, u.username as manager FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.user_id = ?", (session['user_id'],)).fetchall()
    conn.close()
    
    template = open(os.path.join(TEMPLATES_DIR, 'orders.html')).read()
    return render_template_string(template, session=session, all_orders=all_orders, os=os)

@app.route('/new_order', methods=['GET', 'POST'])
def new_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        client = request.form.get('client_name', '')
        product = request.form.get('product', '')
        amount = float(request.form.get('amount', 0))
        conn = get_db()
        conn.execute("INSERT INTO orders (user_id, client_name, product, amount) VALUES (?, ?, ?, ?)",
                     (session['user_id'], client, product, amount))
        conn.commit()
        conn.close()
        return redirect(url_for('orders'))
    
    template = open(os.path.join(TEMPLATES_DIR, 'new_order.html')).read()
    return render_template_string(template, session=session, os=os)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)