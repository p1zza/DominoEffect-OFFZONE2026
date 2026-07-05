from flask import Flask, request, render_template_string, redirect, url_for, session
import os, sqlite3, hashlib, subprocess, json
from datetime import datetime

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
BACKUP_LOG_PATH = '/tmp/backup_log.json'

# Роли: 0 = user, 1 = manager, 2 = admin
ROLE_NAMES = {0: 'user', 1: 'manager', 2: 'admin'}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT,
        role INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY, user_id INTEGER, client_name TEXT,
        product TEXT, amount REAL, status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY, filename TEXT, target_host TEXT,
        status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    admin_pass = hashlib.sha256('admin123'.encode()).hexdigest()
    manager_pass = hashlib.sha256('manager123'.encode()).hexdigest()
    user_pass = hashlib.sha256('user123'.encode()).hexdigest()
    
    c.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (1, 'admin', ?, 2)", (admin_pass,))
    c.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (2, 'manager', ?, 1)", (manager_pass,))
    c.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (3, 'user', ?, 0)", (user_pass,))
    
    c.execute("INSERT OR IGNORE INTO orders (id, user_id, client_name, product, amount, status) VALUES (1, 2, 'Client A', 'Product X', 1500.00, 'completed')")
    c.execute("INSERT OR IGNORE INTO orders (id, user_id, client_name, product, amount, status) VALUES (2, 3, 'Client B', 'Product Y', 2300.50, 'processing')")
    c.execute("INSERT OR IGNORE INTO orders (id, user_id, client_name, product, amount, status) VALUES (3, 3, 'Client C', 'Product Z', 899.99, 'new')")
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_role_name(role_id):
    return ROLE_NAMES.get(role_id, 'unknown')

def get_last_backup():
    """Получить время последнего бэкапа"""
    try:
        conn = get_db()
        last = conn.execute("SELECT created_at FROM backups ORDER BY created_at DESC LIMIT 1").fetchone()
        conn.close()
        if last:
            return last['created_at']
    except:
        pass
    return None

def backup_flags_to_internal():
    """Бэкап флагов на internal сервер через SSH"""
    try:
        # УЯЗВИМОСТЬ: используем os.popen для выполнения команды — можно эксплуатировать через SSTI
        cmd = f'sshpass -p {INTERNAL_PASS} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {INTERNAL_USER}@{INTERNAL_HOST} "sqlite3 /data/ctf.db \\".dump\\" > /data/backup_flags.sql && echo \\"Backup completed at $(date)\\""'
        result = os.popen(cmd).read()
        
        # Логируем в локальную БД
        conn = get_db()
        conn.execute("INSERT INTO backups (filename, target_host, status) VALUES (?, ?, ?)",
                     ('backup_flags.sql', INTERNAL_HOST, 'success'))
        conn.commit()
        conn.close()
        
        return True, result
    except Exception as e:
        return False, str(e)

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
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
    
    template = open(os.path.join(TEMPLATES_DIR, 'login.html')).read()
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
                conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 0)", (username, password_hash))
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
    
    # SSTI уязвимость
    name = request.args.get('name', session.get('username', 'User'))
    
    # Данные для бэкапа (только для admin)
    last_backup = None
    backup_status = None
    if session.get('role', 0) >= 2:
        last_backup = get_last_backup()
        backup_status = request.args.get('backup_status', '')
    
    base_template = open(os.path.join(TEMPLATES_DIR, 'dashboard.html')).read()
    welcome_html = f'<h1>Welcome, {name}!</h1><p>Role: {get_role_name(session.get("role", 0))}</p>'
    full_template = base_template.replace('{{ welcome_message }}', welcome_html)
    
    return render_template_string(full_template, session=session,
                                  total_orders=total_orders,
                                  my_orders=my_orders,
                                  recent_orders=recent,
                                  role_name=get_role_name(session.get('role', 0)),
                                  last_backup=last_backup,
                                  backup_status=backup_status,
                                  os=os)

@app.route('/backup', methods=['POST'])
def backup():
    """Создание бэкапа флагов на internal сервер — только admin"""
    if 'user_id' not in session or session.get('role', 0) < 2:
        return redirect(url_for('dashboard'))
    
    success, result = backup_flags_to_internal()
    status = 'success' if success else 'error'
    
    # УЯЗВИМОСТЬ: результат бэкапа можно увидеть через SSTI на dashboard
    return redirect(url_for('dashboard', backup_status=status))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    role = session.get('role', 0)
    
    if role >= 2:  # admin
        all_orders = conn.execute("""
            SELECT o.*, u.username as manager, u.role as user_role
            FROM orders o LEFT JOIN users u ON o.user_id = u.id
        """).fetchall()
    elif role >= 1:  # manager
        all_orders = conn.execute("""
            SELECT o.*, u.username as manager
            FROM orders o LEFT JOIN users u ON o.user_id = u.id
        """).fetchall()
    else:  # user
        all_orders = conn.execute("""
            SELECT o.*, u.username as manager
            FROM orders o LEFT JOIN users u ON o.user_id = u.id
            WHERE o.user_id = ?
        """, (session['user_id'],)).fetchall()
    
    conn.close()
    
    template = open(os.path.join(TEMPLATES_DIR, 'orders.html')).read()
    return render_template_string(template, session=session,
                                  all_orders=all_orders,
                                  role=role,
                                  role_name=get_role_name(role),
                                  os=os)

@app.route('/users')
def users():
    if 'user_id' not in session or session.get('role', 0) < 2:
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    all_users = conn.execute("SELECT id, username, role, created_at FROM users").fetchall()
    conn.close()
    
    template = open(os.path.join(TEMPLATES_DIR, 'users.html')).read()
    return render_template_string(template, session=session,
                                  all_users=all_users,
                                  role_names=ROLE_NAMES,
                                  os=os)

@app.route('/new_order', methods=['GET', 'POST'])
def new_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        client = request.form.get('client_name', '')
        product = request.form.get('product', '')
        amount = float(request.form.get('amount', 0))
        
        if session.get('role', 0) >= 2:
            user_id = request.form.get('user_id', session['user_id'])
        else:
            user_id = session['user_id']
        
        conn = get_db()
        conn.execute("INSERT INTO orders (user_id, client_name, product, amount) VALUES (?, ?, ?, ?)",
                     (user_id, client, product, amount))
        conn.commit()
        conn.close()
        return redirect(url_for('orders'))
    
    users_list = []
    if session.get('role', 0) >= 2:
        conn = get_db()
        users_list = conn.execute("SELECT id, username, role FROM users").fetchall()
        conn.close()
    
    template = open(os.path.join(TEMPLATES_DIR, 'new_order.html')).read()
    return render_template_string(template, session=session,
                                  users=users_list,
                                  role_names=ROLE_NAMES,
                                  os=os)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)