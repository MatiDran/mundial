import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from app import app, db, User, Bet, wyznacz_wynik, rozlicz

def mecz(id, status, score_home=None, score_away=None, delta_hours=3):
    return {
        'id': id,
        'home': 'Polska', 'away': 'Niemcy',
        'home_flaga': 'pl', 'away_flaga': 'de',
        'date': datetime.now() + timedelta(hours=delta_hours),
        'status': status,
        'score_home': score_home,
        'score_away': score_away,
    }

@pytest.fixture
def client(tmp_path):
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/test.db'
    with app.app_context():
        db.create_all()
        db.session.add(User(username='Tomek'))
        db.session.add(User(username='Michal'))
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

# --- wyznacz_wynik ---
def test_wyznacz_wynik_domowy():
    assert wyznacz_wynik(2, 1) == '1'

def test_wyznacz_wynik_goscinny():
    assert wyznacz_wynik(0, 1) == '2'

def test_wyznacz_wynik_remis():
    assert wyznacz_wynik(1, 1) == 'X'

def test_wyznacz_wynik_0_0():
    assert wyznacz_wynik(0, 0) == 'X'

# --- rozlicz ---
def test_rozlicz_trafiony_typ(client):
    with app.app_context():
        user = User.query.filter_by(username='Tomek').first()
        user.points = 0
        db.session.add(Bet(user_id=user.id, match_id=99, predicted='1', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'FINISHED', 2, 0)]):
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 1

def test_rozlicz_pudlo(client):
    with app.app_context():
        user = User.query.filter_by(username='Tomek').first()
        user.points = 0
        db.session.add(Bet(user_id=user.id, match_id=99, predicted='2', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'FINISHED', 2, 0)]):
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 0

def test_rozlicz_nie_dodaje_punktow_dwa_razy(client):
    with app.app_context():
        user = User.query.filter_by(username='Tomek').first()
        user.points = 0
        db.session.add(Bet(user_id=user.id, match_id=99, predicted='1', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'FINISHED', 2, 0)]):
            rozlicz()
            rozlicz()
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 1

def test_rozlicz_nie_rozlicza_nieukonczonego(client):
    with app.app_context():
        user = User.query.filter_by(username='Tomek').first()
        user.points = 0
        db.session.add(Bet(user_id=user.id, match_id=99, predicted='1', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'IN_PLAY')]):
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 0

def test_rozlicz_nie_rozlicza_gdy_brak_wyniku(client):
    with app.app_context():
        user = User.query.filter_by(username='Tomek').first()
        user.points = 0
        db.session.add(Bet(user_id=user.id, match_id=99, predicted='1', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'FINISHED', None, None)]):
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 0

def test_rozlicz_wielu_graczy(client):
    with app.app_context():
        tomek = User.query.filter_by(username='Tomek').first()
        michal = User.query.filter_by(username='Michal').first()
        tomek.points = 0
        michal.points = 0
        db.session.add(Bet(user_id=tomek.id, match_id=99, predicted='1', processed=False))
        db.session.add(Bet(user_id=michal.id, match_id=99, predicted='X', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'FINISHED', 1, 0)]):
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 1
        assert User.query.filter_by(username='Michal').first().points == 0

def test_rozlicz_remis(client):
    with app.app_context():
        user = User.query.filter_by(username='Tomek').first()
        user.points = 0
        db.session.add(Bet(user_id=user.id, match_id=99, predicted='X', processed=False))
        db.session.commit()
        with patch('app.pobierz_mecze', return_value=[mecz(99, 'FINISHED', 1, 1)]):
            rozlicz()
        db.session.expire_all()
        assert User.query.filter_by(username='Tomek').first().points == 1

# --- /obstaw ---
def test_obstaw_zapisuje_typ(client):
    with patch('app.pobierz_mecze', return_value=[mecz(99, 'TIMED', delta_hours=3)]):
        resp = client.post('/obstaw', data={'match_id': 99, 'predicted': '1'})
    assert resp.status_code == 302
    with app.app_context():
        bet = Bet.query.filter_by(match_id=99).first()
        assert bet is not None
        assert bet.predicted == '1'

def test_obstaw_aktualizuje_istniejacy_typ(client):
    with patch('app.pobierz_mecze', return_value=[mecz(99, 'TIMED', delta_hours=3)]):
        client.post('/obstaw', data={'match_id': 99, 'predicted': '1'})
        client.post('/obstaw', data={'match_id': 99, 'predicted': 'X'})
    with app.app_context():
        bety = Bet.query.filter_by(match_id=99).all()
        assert len(bety) == 1
        assert bety[0].predicted == 'X'

def test_obstaw_blokada_godzinowa(client):
    with patch('app.pobierz_mecze', return_value=[mecz(99, 'TIMED', delta_hours=0.5)]):
        resp = client.post('/obstaw', data={'match_id': 99, 'predicted': '1'})
    assert resp.status_code == 400

def test_obstaw_nieistniejacy_mecz(client):
    with patch('app.pobierz_mecze', return_value=[]):
        resp = client.post('/obstaw', data={'match_id': 999, 'predicted': '1'})
    assert resp.status_code == 404

# --- strona główna ---
def test_index_domyslna_zakladka_mecze(client):
    with patch('app.pobierz_mecze', return_value=[]):
        resp = client.get('/')
    assert resp.status_code == 200

def test_index_zakladka_tabela(client):
    with patch('app.pobierz_mecze', return_value=[]):
        resp = client.get('/?tab=tabela')
    assert resp.status_code == 200
    assert b'Tomek' in resp.data

def test_index_zakladka_historia(client):
    with patch('app.pobierz_mecze', return_value=[]):
        resp = client.get('/?tab=historia')
    assert resp.status_code == 200
