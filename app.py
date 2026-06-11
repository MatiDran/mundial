import os
os.environ['TZ'] = 'Europe/Warsaw'
import time
time.tzset()

from flask import Flask, render_template_string, request, redirect, url_for, session, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import requests
from datetime import timezone

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///typer.db'
app.config['SECRET_KEY'] = 'super-tajne-haslo-kumpli'
db = SQLAlchemy(app)

# --- MODELE ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    pin_hash = db.Column(db.String(200), nullable=False)
    points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_id = db.Column(db.Integer, nullable=False)
    predicted = db.Column(db.String(1), nullable=False)
    processed = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('bets', lazy=True))

# --- DEKORATORY ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin: return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# --- TŁUMACZENIA I FLAGI ---
TLUMACZENIA = {
    'Algeria': 'Algieria', 'Argentina': 'Argentyna', 'Australia': 'Australia',
    'Austria': 'Austria', 'Belgium': 'Belgia', 'Bosnia-Herzegovina': 'Bośnia i Hercegowina',
    'Brazil': 'Brazylia', 'Canada': 'Kanada', 'Cape Verde Islands': 'Wyspy Zielonego Przylądka',
    'Colombia': 'Kolumbia', 'Congo DR': 'Kongo DR', 'Croatia': 'Chorwacja',
    'Curaçao': 'Curacao', 'Czechia': 'Czechy', 'Ecuador': 'Ekwador',
    'Egypt': 'Egipt', 'England': 'Anglia', 'France': 'Francja',
    'Germany': 'Niemcy', 'Ghana': 'Ghana', 'Haiti': 'Haiti',
    'Iran': 'Iran', 'Iraq': 'Irak', 'Ivory Coast': 'Wybrzeże Kości Słoniowej',
    'Japan': 'Japonia', 'Jordan': 'Jordania', 'Mexico': 'Meksyk',
    'Morocco': 'Maroko', 'Netherlands': 'Holandia', 'New Zealand': 'Nowa Zelandia',
    'Norway': 'Norwegia', 'Panama': 'Panama', 'Paraguay': 'Paragwaj',
    'Portugal': 'Portugalia', 'Qatar': 'Katar', 'Saudi Arabia': 'Arabia Saudyjska',
    'Scotland': 'Szkocja', 'Senegal': 'Senegal', 'South Africa': 'RPA',
    'South Korea': 'Korea Płd.', 'Spain': 'Hiszpania', 'Sweden': 'Szwecja',
    'Switzerland': 'Szwajcaria', 'Tunisia': 'Tunezja', 'Turkey': 'Turcja',
    'United States': 'USA', 'Uruguay': 'Urugwaj', 'Uzbekistan': 'Uzbekistan',
}

FLAGI = {
    'Algeria': 'dz', 'Argentina': 'ar', 'Australia': 'au', 'Austria': 'at',
    'Belgium': 'be', 'Bosnia-Herzegovina': 'ba', 'Brazil': 'br', 'Canada': 'ca',
    'Cape Verde Islands': 'cv', 'Colombia': 'co', 'Congo DR': 'cd', 'Croatia': 'hr',
    'Curaçao': 'cw', 'Czechia': 'cz', 'Ecuador': 'ec', 'Egypt': 'eg',
    'England': 'gb', 'France': 'fr', 'Germany': 'de', 'Ghana': 'gh',
    'Haiti': 'ht', 'Iran': 'ir', 'Iraq': 'iq', 'Ivory Coast': 'ci',
    'Japan': 'jp', 'Jordan': 'jo', 'Mexico': 'mx', 'Morocco': 'ma',
    'Netherlands': 'nl', 'New Zealand': 'nz', 'Norway': 'no', 'Panama': 'pa',
    'Paraguay': 'py', 'Portugal': 'pt', 'Qatar': 'qa', 'Saudi Arabia': 'sa',
    'Scotland': 'gb', 'Senegal': 'sn', 'South Africa': 'za', 'South Korea': 'kr',
    'Spain': 'es', 'Sweden': 'se', 'Switzerland': 'ch', 'Tunisia': 'tn',
    'Turkey': 'tr', 'United States': 'us', 'Uruguay': 'uy', 'Uzbekistan': 'uz',
}

# --- API + CACHE ---
API_KEY = 'a102ac2d806a4d1ab16ec7bdffdeb4ae'
API_URL = 'https://api.football-data.org/v4/competitions/WC/matches'
_cache = {'data': None, 'ts': None}

def pobierz_mecze():
    now = datetime.now()
    if _cache['data'] and _cache['ts'] and (now - _cache['ts']).seconds < 120: return _cache['data']
    try:
        resp = requests.get(API_URL, headers={'X-Auth-Token': API_KEY}, timeout=5)
        mecze = []
        for m in resp.json().get('matches', []):
            score = m['score']['fullTime']
            # Zmieniony sposób parsowania - teraz serwer operuje na czasie lokalnym
            dt = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
            dt_polski = dt.astimezone(timezone(timedelta(hours=2)))
            mecze.append({
                'id': m['id'],
                'home': TLUMACZENIA.get(m['homeTeam']['name'], m['homeTeam']['name']),
                'away': TLUMACZENIA.get(m['awayTeam']['name'], m['awayTeam']['name']),
                'home_flaga': FLAGI.get(m['homeTeam']['name'], ''),
                'away_flaga': FLAGI.get(m['awayTeam']['name'], ''),
                'date': dt_polski.replace(tzinfo=None),
                'status': m['status'],
                'score_home': score['home'],
                'score_away': score['away'],
            })
        _cache['data'] = mecze
        _cache['ts'] = now
        return mecze
    except: return _cache['data'] or []

# --- LOGIKA PUNKTÓW ---
def wyznacz_wynik(score_home, score_away):
    if score_home > score_away:
        return '1'
    elif score_home < score_away:
        return '2'
    return 'X'

def rozlicz():
    mecze = pobierz_mecze()
    for mecz in mecze:
        if mecz['status'] == 'FINISHED' and mecz['score_home'] is not None:
            res = '1' if mecz['score_home'] > mecz['score_away'] else ('2' if mecz['score_home'] < mecz['score_away'] else 'X')
            for t in Bet.query.filter_by(match_id=mecz['id'], processed=False).all():
                u = db.session.get(User, t.user_id)
                if u and t.predicted == res: u.points += 1
                t.processed = True
    db.session.commit()

# --- STYLE WSPÓLNE ---
BASE_STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #0f1923; color: #e0e0e0; min-height: 100vh; }
a { color: inherit; text-decoration: none; }
input, select { background: #1a2a3a; border: 1px solid #1e3a5f; color: #e0e0e0; padding: 10px 14px; border-radius: 8px; font-size: 14px; width: 100%; outline: none; }
input:focus { border-color: #f0c040; }
.btn { display: inline-block; padding: 10px 24px; background: #f0c040; color: #0f1923; font-weight: 700; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; transition: opacity 0.2s; }
.btn:hover { opacity: 0.85; }
.btn-ghost { background: transparent; border: 1px solid #1e3a5f; color: #90caf9; }
.btn-ghost:hover { border-color: #90caf9; }
.btn-danger { background: #c62828; color: #fff; }
.flash { padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
.flash.error { background: rgba(198,40,40,0.2); border: 1px solid #c62828; color: #ef9a9a; }
.flash.success { background: rgba(46,125,50,0.2); border: 1px solid #388e3c; color: #a5d6a7; }
"""

# --- HTML TEMPLATES ---
DOZWOLONE_IMIONA = ['Antek', 'Kuba', 'Dawid', 'Mati M', 'Mati K', 'Franek']

LOGIN_TEMPLATE = """
<!DOCTYPE html><html lang="pl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Typer MŚ 2026 — Logowanie</title>
<style>""" + BASE_STYLE + """
.center { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
.card { background: #162032; border: 1px solid #1e3a5f; border-radius: 16px; padding: 40px; width: 100%; max-width: 380px; }
.logo { font-size: 28px; font-weight: 800; color: #f0c040; text-align: center; margin-bottom: 8px; }
.subtitle { text-align: center; color: #90caf9; font-size: 13px; margin-bottom: 32px; }
.form-group { margin-bottom: 16px; }
label { display: block; font-size: 12px; color: #90caf9; margin-bottom: 6px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
.names-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.name-option { display: flex; align-items: center; gap: 8px; background: #1a2a3a; border: 2px solid #1e3a5f; border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.2s; }
.name-option:hover { border-color: #f0c040; }
.name-option input[type=radio] { accent-color: #f0c040; width: 16px; height: 16px; }
.name-option span { font-weight: 600; font-size: 14px; }
.link { text-align: center; margin-top: 15px; font-size: 13px; color: #546e7a; }
.link a { color: #90caf9; }
</style></head><body>
<div class="center">
  <div class="card">
    <div class="logo">🏆 Typer MŚ</div>
    <div class="subtitle">Mistrzostwa Świata 2026</div>
    {% if error %}<div class="flash error">{{ error }}</div>{% endif %}
    {% set messages = get_flashed_messages(category_filter=['success']) %}
    {% for msg in messages %}<div class="flash success">{{ msg }}</div>{% endfor %}
    <form method="POST">
      <div class="form-group">
        <label>Wybierz swoje imię</label>
        <div class="names-grid">
          {% for imie in imiona %}
          <label class="name-option">
            <input type="radio" name="username" value="{{ imie }}">
            <span>{{ imie }}</span>
          </label>
          {% endfor %}
        </div>
      </div>
      <div class="form-group" style="margin-top:16px;">
        <label>Hasło</label>
        <input type="password" name="password" placeholder="••••••••" required>
      </div>
      <button type="submit" class="btn" style="width:100%; margin-top:8px;">Zaloguj się</button>
    </form>
    <div class="link">Nie masz konta? <a href="/register">Zarejestruj się</a></div>
    <div class="link" style="margin-top: 8px;"><a href="/odzyskaj" style="color: #f0c040;">Zapomniałem hasła (Reset PIN)</a></div>
  </div>
</div>
</body></html>
"""

REGISTER_TEMPLATE = """
<!DOCTYPE html><html lang="pl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Typer MŚ 2026 — Rejestracja</title>
<style>""" + BASE_STYLE + """
.center { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
.card { background: #162032; border: 1px solid #1e3a5f; border-radius: 16px; padding: 40px; width: 100%; max-width: 380px; }
.logo { font-size: 28px; font-weight: 800; color: #f0c040; text-align: center; margin-bottom: 8px; }
.subtitle { text-align: center; color: #90caf9; font-size: 13px; margin-bottom: 32px; }
.form-group { margin-bottom: 16px; }
label { display: block; font-size: 12px; color: #90caf9; margin-bottom: 6px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
.names-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.name-option { display: flex; align-items: center; gap: 8px; background: #1a2a3a; border: 2px solid #1e3a5f; border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.2s; }
.name-option:hover { border-color: #f0c040; }
.name-option input[type=radio] { accent-color: #f0c040; width: 16px; height: 16px; }
.name-option span { font-weight: 600; font-size: 14px; }
.name-option.zajete { opacity: 0.4; pointer-events: none; border-color: #c62828; }
.link { text-align: center; margin-top: 20px; font-size: 13px; color: #546e7a; }
.link a { color: #90caf9; }
</style></head><body>
<div class="center">
  <div class="card">
    <div class="logo">🏆 Typer MŚ</div>
    <div class="subtitle">Utwórz konto</div>
    {% if error %}<div class="flash error">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="form-group">
        <label>Wybierz swoje imię</label>
        <div class="names-grid">
          {% for imie in imiona %}
          <label class="name-option {% if imie in zajete %}zajete{% endif %}">
            <input type="radio" name="username" value="{{ imie }}" required {% if imie in zajete %}disabled{% endif %}>
            <span>{{ imie }} {% if imie in zajete %}✓{% endif %}</span>
          </label>
          {% endfor %}
        </div>
      </div>
      <div class="form-group" style="margin-top:16px;">
        <label>Hasło</label>
        <input type="password" name="password" placeholder="Min. 6 znaków" required minlength="6">
      </div>
      <div class="form-group" style="margin-top:16px;">
        <label style="color: #ffb74d;">Sekretny PIN awaryjny (do resetu)</label>
        <input type="password" name="pin" placeholder="Np. 4 cyfry" required minlength="4">
      </div>
      <button type="submit" class="btn" style="width:100%; margin-top:12px;">Zarejestruj się</button>
    </form>
    <div class="link">Masz już konto? <a href="/login">Zaloguj się</a></div>
  </div>
</div>
</body></html>
"""

ODZYSKAJ_TEMPLATE = """
<!DOCTYPE html><html lang="pl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Odzyskiwanie hasła</title>
<style>""" + BASE_STYLE + """
.center { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
.card { background: #162032; border: 1px solid #1e3a5f; border-radius: 16px; padding: 40px; width: 100%; max-width: 380px; }
.logo { font-size: 24px; font-weight: 800; color: #ffb74d; text-align: center; margin-bottom: 8px; }
.subtitle { text-align: center; color: #90caf9; font-size: 13px; margin-bottom: 24px; }
.form-group { margin-bottom: 16px; }
label { display: block; font-size: 12px; color: #90caf9; margin-bottom: 6px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
.link { text-align: center; margin-top: 20px; font-size: 13px; color: #546e7a; }
.link a { color: #90caf9; }
</style></head><body>
<div class="center">
  <div class="card">
    <div class="logo">🔐 Reset Hasła</div>
    <div class="subtitle">Użyj swojego PINu ratunkowego</div>
    {% if error %}<div class="flash error">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="form-group">
        <label>Wybierz swoje imię</label>
        <select name="username" required style="width:100%;">
            <option value="" disabled selected>-- Wybierz z listy --</option>
            {% for imie in imiona %}
            <option value="{{ imie }}">{{ imie }}</option>
            {% endfor %}
        </select>
      </div>
      <div class="form-group">
        <label>Twój PIN ratunkowy</label>
        <input type="password" name="pin" placeholder="Wpisz PIN podany przy rejestracji" required>
      </div>
      <div class="form-group">
        <label>Nowe Hasło</label>
        <input type="password" name="nowe_haslo" placeholder="Min. 6 znaków" required minlength="6">
      </div>
      <button type="submit" class="btn" style="width:100%; margin-top:8px; background: #ffb74d;">Zmień i zapisz hasło</button>
    </form>
    <div class="link"><a href="/login">← Wróć do logowania</a></div>
  </div>
</div>
</body></html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html><html lang="pl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel Admina</title>
<style>""" + BASE_STYLE + """
header { background: #162032; border-bottom: 1px solid #1e3a5f; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
.logo { font-size: 18px; font-weight: 700; color: #f0c040; }
main { max-width: 700px; margin: 32px auto; padding: 0 20px; }
h2 { color: #f0c040; margin-bottom: 20px; font-size: 18px; }
.user-row { background: #162032; border: 1px solid #1e3a5f; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; display: flex; align-items: center; gap: 12px; }
.user-name { flex: 1; font-weight: 600; }
.user-pts { color: #f0c040; font-weight: 700; min-width: 60px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.reset-form input { width: 140px; padding: 7px 10px; font-size: 13px; }
</style></head><body>
<header>
  <div class="logo">🔧 Panel Admina</div>
  <a href="/" class="btn btn-ghost" style="padding:6px 14px; font-size:13px;">← Główna</a>
</header>
<main>
  {% for cat, msg in messages %}
  <div class="flash {{ cat }}">{{ msg }}</div>
  {% endfor %}
  <h2>Zarządzanie graczami ({{ users|length }}/10)</h2>
  {% for u in users %}
  <div class="user-row">
    <div class="user-name">👤 {{ u.username }}</div>
    <div class="user-pts">{{ u.points }} pkt</div>
    <div class="actions">
      <form method="POST" action="/admin/reset/{{ u.id }}" class="reset-form" style="display:flex; gap:6px;">
        <input type="password" name="new_password" placeholder="Nowe hasło" minlength="6" required>
        <button type="submit" class="btn" style="padding:7px 12px; font-size:13px; white-space:nowrap;">Reset hasła</button>
      </form>
      <form method="POST" action="/admin/punkty/{{ u.id }}" style="display:flex; gap:6px;">
        <input type="number" name="punkty" placeholder="+1 lub -1" style="width:110px;" required>
        <button type="submit" class="btn btn-ghost" style="padding:7px 12px; font-size:13px; white-space:nowrap;">Zmień pkt</button>
      </form>
      <form method="POST" action="/admin/delete/{{ u.id }}" onsubmit="return confirm('Usunąć {{ u.username }}?')">
        <button type="submit" class="btn btn-danger" style="padding:7px 12px; font-size:13px;">Usuń</button>
      </form>
    </div>
  </div>
  {% endfor %}
</main>
</body></html>
"""

MAIN_TEMPLATE = """
<!DOCTYPE html><html lang="pl"><head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="120">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Typer MŚ 2026</title>
<style>""" + BASE_STYLE + """
header { background: linear-gradient(135deg, #1a2a3a, #0f1923); padding: 20px 0 0; border-bottom: 1px solid #1e3a5f; }
.header-top { max-width: 860px; margin: 0 auto; padding: 0 20px 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.logo { font-size: 20px; font-weight: 700; color: #f0c040; }
.header-right { display: flex; align-items: center; gap: 10px; }
.user-badge { background: #1e3a5f; padding: 6px 14px; border-radius: 20px; font-size: 13px; color: #90caf9; }
nav { max-width: 860px; margin: 0 auto; padding: 0 20px; display: flex; gap: 4px; }
nav a { padding: 10px 20px; border-radius: 8px 8px 0 0; font-weight: 600; font-size: 14px; color: #90caf9; background: #1a2a3a; transition: all 0.2s; }
nav a.active { background: #162032; color: #f0c040; border-bottom: 2px solid #f0c040; }
nav a:hover:not(.active) { background: #162032; color: #e0e0e0; }
main { max-width: 860px; margin: 0 auto; padding: 24px 20px; }

.match-card { background: #162032; border: 1px solid #1e3a5f; border-radius: 12px; padding: 20px; margin-bottom: 16px; text-align: center; }
.match-date { font-size: 12px; color: #90caf9; margin-bottom: 16px; }
.match-teams { display: flex; align-items: center; justify-content: center; gap: 20px; flex-wrap: wrap; }
.team { display: flex; flex-direction: column; align-items: center; gap: 8px; width: 140px; }
.team img { width: 52px; height: 39px; border-radius: 3px; box-shadow: 0 2px 6px rgba(0,0,0,0.4); }
.team-name { font-size: 15px; font-weight: 700; color: #fff; }
.vs { font-size: 26px; font-weight: 800; color: #1e3a5f; }
.bet-buttons { display: flex; justify-content: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.bet-btn { padding: 10px 28px; font-size: 15px; font-weight: 700; border: 2px solid #1e3a5f; border-radius: 8px; background: #1a2a3a; color: #90caf9; cursor: pointer; transition: all 0.2s; }
.bet-btn:hover { border-color: #f0c040; color: #f0c040; }
.bet-btn.selected { background: #f0c040; color: #0f1923; border-color: #f0c040; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-top: 8px; }
.open { background: rgba(76,175,80,0.15); color: #81c784; border: 1px solid #388e3c; }
.locked { background: rgba(244,67,54,0.15); color: #e57373; border: 1px solid #c62828; }
.live { background: rgba(255,152,0,0.15); color: #ffb74d; border: 1px solid #e65100; }
.user-tip { margin-top: 10px; font-size: 13px; color: #90caf9; }
.user-tip strong { color: #fff; }
.ekipa-typy { margin-top: 12px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
.ekipa-typ { background: #1a2a3a; border: 1px solid #1e3a5f; border-radius: 8px; padding: 5px 12px; font-size: 12px; color: #90caf9; }
.ekipa-typ .nick { color: #fff; font-weight: 600; }
.ekipa-typ .val { color: #f0c040; font-weight: 700; margin-left: 4px; }

.leaderboard { background: #162032; border: 1px solid #1e3a5f; border-radius: 12px; overflow: hidden; }
.leaderboard-row { display: flex; align-items: center; padding: 14px 20px; border-bottom: 1px solid #1a2a3a; gap: 16px; }
.leaderboard-row:last-child { border-bottom: none; }
.leaderboard-row.header { background: #1a2a3a; font-size: 12px; color: #90caf9; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
.rank { width: 30px; font-size: 18px; font-weight: 800; color: #1e3a5f; text-align: center; }
.rank.gold { color: #f0c040; } .rank.silver { color: #b0bec5; } .rank.bronze { color: #a1664a; }
.player-name { flex: 1; font-size: 16px; font-weight: 600; }
.points { font-size: 20px; font-weight: 800; color: #f0c040; }
.points span { font-size: 12px; color: #90caf9; font-weight: 400; }

.history-card { background: #162032; border: 1px solid #1e3a5f; border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.history-teams { flex: 1; min-width: 160px; }
.history-match { font-size: 15px; font-weight: 600; color: #fff; }
.history-date { font-size: 12px; color: #90caf9; margin-top: 2px; }
.history-score { font-size: 22px; font-weight: 800; color: #f0c040; text-align: center; min-width: 60px; }
.tip-result { text-align: center; min-width: 60px; }
.tip-value { font-size: 20px; font-weight: 800; }
.hit { color: #81c784; } .miss { color: #e57373; }
.no-tip { color: #546e7a; font-size: 13px; }
.empty { color: #546e7a; text-align: center; margin-top: 40px; }

@media(max-width: 500px) {
  .team { width: 100px; }
  .team-name { font-size: 13px; }
  nav a { padding: 8px 12px; font-size: 13px; }
}
</style></head><body>
<header>
  <div class="header-top">
    <div class="logo">🏆 Typer MŚ 2026</div>
    <div class="header-right">
      <div class="user-badge">👤 {{ current_user.username }}</div>
      {% if current_user.is_admin %}
      <a href="/admin" class="btn" style="padding:6px 12px; font-size:12px;">🔧 Admin</a>
      {% endif %}
      <a href="/logout" class="btn btn-ghost" style="padding:6px 12px; font-size:12px;">Wyloguj</a>
    </div>
  </div>
  <nav>
    <a href="/?tab=mecze" class="{% if tab == 'mecze' %}active{% endif %}">⚽ Mecze</a>
    <a href="/?tab=historia" class="{% if tab == 'historia' %}active{% endif %}">📋 Historia</a>
    <a href="/?tab=tabela" class="{% if tab == 'tabela' %}active{% endif %}">📊 Tabela</a>
    <a href="/?tab=mistrz" class="{% if tab == 'mistrz' %}active{% endif %}">🏆 Mistrz</a>
  </nav>
</header>
<main>

{% if tab == 'mecze' %}
  {% set nadchodzace = mecze | selectattr('status', 'in', ['TIMED', 'SCHEDULED', 'IN_PLAY', 'PAUSED', 'LIVE']) | list %}
  {% if not nadchodzace %}<p class="empty">Brak nadchodzących meczów.</p>{% endif %}
  {% for mecz in nadchodzace %}
  {% set czas_do_meczu = (mecz.date - teraz).total_seconds() / 60 %}
  {% set zablokowany = czas_do_meczu <= 60 or mecz.status in ('IN_PLAY', 'PAUSED', 'LIVE') %}
  <div class="match-card">
    <div class="match-date">{{ mecz.date.strftime('%d.%m.%Y  %H:%M') }}</div>
    <div class="match-teams">
      <div class="team">
        <img src="https://flagcdn.com/48x36/{{ mecz.home_flaga }}.png">
        <span class="team-name">{{ mecz.home }}</span>
      </div>
      <span class="vs">-</span>
      <div class="team">
        <img src="https://flagcdn.com/48x36/{{ mecz.away_flaga }}.png">
        <span class="team-name">{{ mecz.away }}</span>
      </div>
    </div>
    {% if mecz.status in ('IN_PLAY', 'PAUSED', 'LIVE') %}
      <span class="badge live">🔴 Na żywo</span>
      <div class="user-tip">Twój typ: <strong>{{ typy_user.get(mecz.id) or 'Brak' }}</strong></div>
    {% elif czas_do_meczu > 60 %}
      <span class="badge open">✅ Można obstawiać · zostało {{ (czas_do_meczu/60)|int }}h</span>
    <div id="mecz-{{ mecz.id }}">
      <form action="/obstaw" method="POST">
        <input type="hidden" name="match_id" value="{{ mecz.id }}">
        <div class="bet-buttons">
          <button type="submit" name="predicted" value="1" class="bet-btn {% if typy_user.get(mecz.id) == '1' %}selected{% endif %}">1</button>
          <button type="submit" name="predicted" value="X" class="bet-btn {% if typy_user.get(mecz.id) == 'X' %}selected{% endif %}">X</button>
          <button type="submit" name="predicted" value="2" class="bet-btn {% if typy_user.get(mecz.id) == '2' %}selected{% endif %}">2</button>
        </div>
      </form>
    </div>
    {% else %}
      <span class="badge locked">🔒 Zablokowane</span>
      <div class="user-tip">Twój typ: <strong>{{ typy_user.get(mecz.id) or 'Brak' }}</strong></div>
    {% endif %}
    {% if zablokowany and wszystkie_typy.get(mecz.id) %}
      <div class="ekipa-typy">
        {% for nick, val in wszystkie_typy[mecz.id].items() %}
        <div class="ekipa-typ"><span class="nick">{{ nick }}</span><span class="val">{{ val }}</span></div>
        {% endfor %}
      </div>
    {% endif %}
  </div>
  {% endfor %}

{% elif tab == 'historia' %}
  {% set zakonczone = mecze | selectattr('status', 'equalto', 'FINISHED') | list %}
  {% if not zakonczone %}<p class="empty">Brak zakończonych meczów.</p>{% endif %}
  {% for mecz in zakonczone %}
  {% set moj_typ = typy_user.get(mecz.id) %}
  {% if mecz.score_home > mecz.score_away %}{% set wynik = '1' %}
  {% elif mecz.score_home < mecz.score_away %}{% set wynik = '2' %}
  {% else %}{% set wynik = 'X' %}{% endif %}
  <div class="history-card">
    <div class="history-teams">
      <div class="history-match">
        <img src="https://flagcdn.com/20x15/{{ mecz.home_flaga }}.png"> {{ mecz.home }}
        &nbsp;vs&nbsp;
        <img src="https://flagcdn.com/20x15/{{ mecz.away_flaga }}.png"> {{ mecz.away }}
      </div>
      <div class="history-date">{{ mecz.date.strftime('%d.%m.%Y %H:%M') }}</div>
    </div>
    <div class="history-score">{{ mecz.score_home }}:{{ mecz.score_away }}</div>
    <div class="tip-result">
      {% if moj_typ %}
        {% if moj_typ == wynik %}<div class="tip-value hit">✓ {{ moj_typ }}</div>
        {% else %}<div class="tip-value miss">✗ {{ moj_typ }}</div>{% endif %}
      {% else %}<div class="no-tip">brak</div>{% endif %}
    </div>
    {% if wszystkie_typy.get(mecz.id) %}
    <div class="ekipa-typy" style="width:100%; justify-content:flex-start;">
      {% for nick, val in wszystkie_typy[mecz.id].items() %}
      <div class="ekipa-typ"><span class="nick">{{ nick }}</span><span class="val">{{ val }}</span></div>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  {% endfor %}

{% elif tab == 'tabela' %}
  <div class="leaderboard">
    <div class="leaderboard-row header">
      <div class="rank">#</div>
      <div style="flex:1">Gracz</div>
      <div>Punkty</div>
    </div>
    {% for u in users %}
    <div class="leaderboard-row">
      <div class="rank {% if loop.index == 1 %}gold{% elif loop.index == 2 %}silver{% elif loop.index == 3 %}bronze{% endif %}">{{ loop.index }}</div>
      <div class="player-name">{{ u.username }}</div>
      <div class="points">{{ u.points }} <span>pkt</span></div>
    </div>
    {% endfor %}
  </div>
{% elif tab == 'mistrz' %}
  <div class="leaderboard">
    <div class="leaderboard-row header">
      <div style="flex:1">Gracz</div>
      <div style="flex:1">Typ na mistrza</div>
    </div>
    {% set typy_mistrz = [
      ('Mati M', 'Anglia'),
      ('Mati K', 'Hiszpania'),
      ('Kuba', 'Francja'),
      ('Antek', 'Brazylia'),
      ('Dawid', 'Portugalia'),
      ('Franek', 'Argentyna')
    ] %}
    {% for gracz, druzyna in typy_mistrz %}
    <div class="leaderboard-row">
      <div class="player-name" style="flex:1">{{ gracz }}</div>
      <div style="flex:1">{{ druzyna }}</div>
    </div>
    {% endfor %}
  </div>
  <p style="text-align:center;color:#888;margin-top:16px;font-size:13px;">+5 punktów dla gracza, którego typ zostanie mistrzem turnieju</p>
{% endif %}

</main></body></html>
"""

# --- TRASY: AUTH ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        if not username:
            username = 'admin'
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        error = 'Nieprawidłowa nazwa lub hasło'
    return render_template_string(LOGIN_TEMPLATE, error=error, imiona=DOZWOLONE_IMIONA)

@app.route('/register', methods=['GET', 'POST'])
def register():
    zajete = [u.username for u in User.query.filter(User.username.in_(DOZWOLONE_IMIONA)).all()]
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        pin = request.form.get('pin', '').strip()
        
        if username not in DOZWOLONE_IMIONA:
            error = 'Wybierz imię z listy.'
        elif username in zajete:
            error = 'To imię jest już zajęte.'
        elif len(password) < 6:
            error = 'Hasło musi mieć min. 6 znaków.'
        elif len(pin) < 4:
            error = 'PIN ratunkowy musi mieć min. 4 znaki.'
        else:
            db.session.add(User(
                username=username, 
                password_hash=generate_password_hash(password),
                pin_hash=generate_password_hash(pin) # NOWE: Szyfrowanie i zapis PINu
            ))
            db.session.commit()
            flash('Konto utworzone! Możesz się zalogować.', 'success')
            return redirect(url_for('login'))
        zajete = [u.username for u in User.query.filter(User.username.in_(DOZWOLONE_IMIONA)).all()]
    return render_template_string(REGISTER_TEMPLATE, error=error, imiona=DOZWOLONE_IMIONA, zajete=zajete)

# NOWA TRASA: ODZYSKIWANIE HASŁA SAMODZIELNIE PRZEZ GRACZA
@app.route('/odzyskaj', methods=['GET', 'POST'])
def odzyskaj():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        pin = request.form.get('pin', '').strip()
        nowe_haslo = request.form.get('nowe_haslo', '')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.pin_hash, pin):
            if len(nowe_haslo) < 6:
                error = 'Nowe hasło musi mieć min. 6 znaków.'
            else:
                user.password_hash = generate_password_hash(nowe_haslo)
                db.session.commit()
                flash('Hasło pomyślnie zmienione! Możesz się zalogować.', 'success')
                return redirect(url_for('login'))
        else:
            error = 'Nieprawidłowe imię lub PIN ratunkowy!'
            
    return render_template_string(ODZYSKAJ_TEMPLATE, error=error, imiona=DOZWOLONE_IMIONA)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- TRASA: ADMIN ---
@app.route('/admin')
@admin_required
def admin():
    users = User.query.filter_by(is_admin=False).order_by(User.points.desc()).all()
    return render_template_string(ADMIN_TEMPLATE, users=users, messages=get_flashed_messages(with_categories=True))

@app.route('/admin/punkty/<int:user_id>', methods=['POST'])
@admin_required
def admin_punkty(user_id):
    user = db.session.get(User, user_id)
    if user and not user.is_admin:
        try:
            zmiana = int(request.form['punkty'])
            user.points = max(0, user.points + zmiana)
            db.session.commit()
            flash(f'{user.username}: punkty zmienione na {user.points}.', 'success')
        except ValueError:
            flash('Podaj liczbę całkowitą.', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/reset/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset(user_id):
    user = db.session.get(User, user_id)
    if user and not user.is_admin:
        user.password_hash = generate_password_hash(request.form['new_password'])
        db.session.commit()
        flash(f'Hasło gracza {user.username} zostało zresetowane.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete(user_id):
    user = db.session.get(User, user_id)
    if user and not user.is_admin:
        Bet.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        flash(f'Gracz {user.username} został usunięty.', 'success')
    return redirect(url_for('admin'))

# --- TRASA: GŁÓWNA ---
@app.route('/')
@login_required
def index():
    rozlicz()
    tab = request.args.get('tab', 'mecze')
    current_user = db.session.get(User, session['user_id'])
    users = User.query.filter_by(is_admin=False).order_by(User.points.desc()).all()
    mecze = pobierz_mecze()
    teraz = datetime.now().replace(tzinfo=None) # Dzięki ustawieniom na górze, teraz to czas lokalny (PL)

    typy_user = {b.match_id: b.predicted for b in Bet.query.filter_by(user_id=current_user.id).all()}

    wszystkie_typy = {}
    all_bets = Bet.query.join(User).filter(User.is_admin == False).all()
    
    for b in all_bets:
        czas = next((m['date'] for m in mecze if m['id'] == b.match_id), None)
        status = next((m['status'] for m in mecze if m['id'] == b.match_id), None)
        zablokowany = (czas and (czas - teraz).total_seconds() / 60 <= 60) or status in ('IN_PLAY', 'PAUSED', 'LIVE', 'FINISHED')
        if zablokowany:
            wszystkie_typy.setdefault(b.match_id, {})[b.user.username] = b.predicted

    return render_template_string(
        MAIN_TEMPLATE,
        tab=tab, users=users, mecze=mecze,
        typy_user=typy_user, wszystkie_typy=wszystkie_typy,
        current_user=current_user, teraz=teraz
    )

# --- TRASA: OBSTAW ---
@app.route('/obstaw', methods=['POST'])
@login_required
def obstaw():
    match_id = int(request.form.get('match_id'))
    predicted = request.form.get('predicted')
    user_id = session['user_id']
    mecz = next((m for m in pobierz_mecze() if m['id'] == match_id), None)
    if not mecz:
        return 'Mecz nie istnieje', 404
    if (mecz['date'] - datetime.now().replace(tzinfo=None)).total_seconds() / 60 <= 60:
        return 'BŁĄD: Czas na obstawianie minął!', 400
    istniejacy = Bet.query.filter_by(user_id=user_id, match_id=match_id).first()
    if istniejacy:
        istniejacy.predicted = predicted
    else:
        db.session.add(Bet(user_id=user_id, match_id=match_id, predicted=predicted))
    db.session.commit()
    return redirect(url_for('index') + f'#mecz-{match_id}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            db.session.add(User(username='admin', password_hash=generate_password_hash('admin123@'), pin_hash=generate_password_hash('0000'), is_admin=True))
            db.session.commit()
    app.run(debug=True, port=5001)
