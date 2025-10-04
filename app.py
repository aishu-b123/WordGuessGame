from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
import random
import pymysql
import config  
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host=config.DB_CONFIG['host'],
            user=config.DB_CONFIG['user'],
            password=config.DB_CONFIG['password'],
            database=config.DB_CONFIG['database'],
            cursorclass=pymysql.cursors.DictCursor
        )
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()

def check_user_limit(user_id):
    """Check if user already tried 3 words today"""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT word_id) AS cnt FROM game_records
        WHERE user_id=%s AND DATE(guess_date)=CURDATE()
    """, (user_id,))
    count = cur.fetchone()['cnt']
    cur.close()
    return count

def get_random_word():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT word_id, word FROM words ORDER BY RAND() LIMIT 1")
    row = cur.fetchone()
    cur.close()
    return row 

def evaluate_guess(word, guess):
    """Return colored tiles: green=correct, orange=wrong position, grey=not in word"""
    colored = []
    word_letters = list(word)
    guess_letters = list(guess)
   
    for i in range(5):
        if guess_letters[i] == word_letters[i]:
            colored.append({'letter': guess_letters[i], 'color': 'green'})
            word_letters[i] = None
        else:
            colored.append({'letter': guess_letters[i], 'color': None})

    for i in range(5):
        if colored[i]['color'] is None:
            if guess_letters[i] in word_letters:
                colored[i]['color'] = 'orange'
                word_letters[word_letters.index(guess_letters[i])] = None
            else:
                colored[i]['color'] = 'grey'
    return colored

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    username_error = None
    password_error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        username_msg = "Username must have at least 5 letters (both upper and lower case)"
        password_msg = "Password must be at least 5 characters, with letters, digits, and one special character ($ % * @)"

        if len(username) < 5 or not any(c.isalpha() for c in username):
            username_error = username_msg

        if len(password) < 5 or not any(c.isdigit() for c in password) \
           or not any(c.isalpha() for c in password) \
           or not any(c in '$%*@' for c in password):
            password_error = password_msg

        if not username_error:
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                username_error = "Username already exists"
            cur.close()

        if not username_error and not password_error:
            hashed = generate_password_hash(password)
            db = get_db()
            cur = db.cursor()
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
                        (username, hashed, 'user'))
            db.commit()
            cur.close()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))

    return render_template('register.html', username_error=username_error, password_error=password_error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT user_id, username, password, role FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            if user['role'] == 'admin' and password == user['password']:
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']
                return redirect(url_for('dashboard'))

            elif check_password_hash(user['password'], password):
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']
                return redirect(url_for('dashboard'))

        flash('Invalid username or password')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

from flask import request

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    selected_date = request.form.get('selected_date')
    if not selected_date:
        cur.execute("SELECT CURDATE() as today")
        selected_date = cur.fetchone()['today']

    cur.execute("""
        SELECT gr.word_id, w.word, gr.guess_word, DATE(gr.guess_date) as guess_date
        FROM game_records gr
        JOIN words w ON gr.word_id = w.word_id
        WHERE gr.user_id=%s 
          AND DATE(gr.guess_date) = %s
          AND gr.word_id IN (
              SELECT word_id
              FROM game_records
              WHERE user_id=%s AND DATE(guess_date) = %s
              GROUP BY word_id
              HAVING SUM(is_correct) > 0 OR COUNT(*) >= 5
          )
        ORDER BY gr.word_id ASC, gr.record_id ASC
    """, (session['user_id'], selected_date, session['user_id'], selected_date))
    rows = cur.fetchall()
    cur.close()

    dashboard_data = {}
    for row in rows:
        word_id = row['word_id']
        if word_id not in dashboard_data:
            dashboard_data[word_id] = {
                'word': row['word'],
                'guesses': []
            }
        dashboard_data[word_id]['guesses'].append(
            evaluate_guess(row['word'], row['guess_word'])
        )

    return render_template('dashboard.html', dashboard_data=dashboard_data, selected_date=selected_date)


@app.route('/play', methods=['GET', 'POST'])
def play():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if 'current_word' not in session:
        words_tried = check_user_limit(user_id)
        if words_tried >= 3:
            return render_template('play_locked.html', words_tried=words_tried)

        word_data = get_random_word()
        session['current_word'] = word_data['word']
        session['current_word_id'] = word_data['word_id']
        session['attempts'] = 0
        session['past_guesses'] = []

    word = session['current_word']
    word_id = session['current_word_id']
    past = session['past_guesses']

    if request.method == 'POST':
        guess = request.form['guess'].upper()
        if len(guess) != 5:
            flash('Guess must be 5 letters')
            return redirect(url_for('play'))

        session['attempts'] += 1
        colored = evaluate_guess(word, guess)
        past.append({'guess_word': guess, 'colored': colored, 'is_correct': guess==word})
        session['past_guesses'] = past

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO game_records(user_id, word_id, guess_word, guess_date, guess_number, is_correct)
            VALUES (%s,%s,%s,CURDATE(),%s,%s)
        """, (user_id, word_id, guess, session['attempts'], guess==word))
        db.commit()
        cur.close()

        if guess == word or session['attempts'] >= 5:
            session.pop('current_word')
            session.pop('current_word_id')
            session.pop('attempts')
            session.pop('past_guesses')
            return render_template('result.html', won=(guess==word), word=word)

    return render_template('game.html', past=past)

@app.route('/admin/report', methods=['GET', 'POST'])
def admin_report():
    if 'role' not in session or session['role'] != 'admin':
        flash('Access denied')
        return redirect(url_for('dashboard'))

    selected_date = None
    if request.method == 'POST':
        selected_date = request.form.get('selected_date')

    db = get_db()
    cur = db.cursor()

    daily_query = """
        SELECT DATE(guess_date) as guess_date,
               COUNT(DISTINCT user_id) as users,
               SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct_guesses
        FROM game_records
    """
    params = []
    if selected_date:
        daily_query += " WHERE DATE(guess_date) = %s"
        params.append(selected_date)
    daily_query += " GROUP BY DATE(guess_date) ORDER BY DATE(guess_date) DESC"
    cur.execute(daily_query, params)
    daily = cur.fetchall()

    if selected_date:
        user_query = """
            SELECT u.user_id, u.username,
                   COUNT(DISTINCT gr.word_id) as words_tried,
                   COUNT(gr.record_id) as total_guesses,
                   SUM(CASE WHEN gr.is_correct=1 THEN 1 ELSE 0 END) as total_correct
            FROM users u
            JOIN game_records gr ON u.user_id = gr.user_id
            WHERE DATE(gr.guess_date) = %s
            GROUP BY u.user_id, u.username
        """
        params = [selected_date]
    else:
        user_query = """
            SELECT u.user_id, u.username,
                   COUNT(DISTINCT gr.word_id) as words_tried,
                   COUNT(gr.record_id) as total_guesses,
                   SUM(CASE WHEN gr.is_correct=1 THEN 1 ELSE 0 END) as total_correct
            FROM users u
            LEFT JOIN game_records gr ON u.user_id = gr.user_id
            GROUP BY u.user_id, u.username
        """
        params = []

    cur.execute(user_query, params)
    users = cur.fetchall()
    cur.close()

    return render_template('admin_report.html', daily=daily, users=users, selected_date=selected_date)

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
def admin_user_report(user_id):
    if 'role' not in session or session['role'] != 'admin':
        flash('Access denied')
        return redirect(url_for('dashboard'))

    selected_date = None
    if request.method == 'POST':
        selected_date = request.form.get('selected_date')

    db = get_db()
    cur = db.cursor()

    summary_query = """
        SELECT COUNT(DISTINCT word_id) as words_tried,
               COUNT(*) as total_guesses,
               SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as total_correct
        FROM game_records
        WHERE user_id=%s
    """
    params = [user_id]
    if selected_date:
        summary_query += " AND DATE(guess_date) = %s"
        params.append(selected_date)
    cur.execute(summary_query, params)
    summary = cur.fetchone()

    detail_query = """
        SELECT gr.record_id, gr.guess_date, gr.word_id, w.word, gr.guess_word, gr.is_correct
        FROM game_records gr
        JOIN words w ON gr.word_id = w.word_id
        WHERE gr.user_id=%s
    """
    params = [user_id]
    if selected_date:
        detail_query += " AND DATE(gr.guess_date) = %s"
        params.append(selected_date)
    detail_query += " ORDER BY gr.guess_date DESC, gr.word_id ASC, gr.record_id ASC"
    cur.execute(detail_query, params)
    rows = cur.fetchall()
    cur.close()

    user_report = {}
    for row in rows:
        date = row['guess_date']
        word_id = row['word_id']
        if date not in user_report:
            user_report[date] = {}
        if word_id not in user_report[date]:
            user_report[date][word_id] = {
                'word': row['word'],
                'guesses': []
            }
        user_report[date][word_id]['guesses'].append({
            'guess': row['guess_word'],
            'is_correct': row['is_correct']
        })

    return render_template('admin_user_report.html', summary=summary, user_report=user_report, selected_date=selected_date)


if __name__ == '__main__':
    app.run(debug=True)
