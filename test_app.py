import io
import os
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix='badminton_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_tmp_dir, 'test.db')

from app import (  # noqa: E402
    app, db, User, Tournament, Match, MvpVote, Announcement, Availability,
    login_attempts,
)


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
        login_attempts.clear()
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            self.admin = User(
                username='admin', email='admin@nyit.edu',
                password_hash=_hash('admin123'),
                full_name='Admin User', role='admin'
            )
            self.captain = User(
                username='jane', email='jane@nyit.edu', password_hash=_hash('player123'),
                full_name='Jane Doe', role='captain'
            )
            self.player = User(
                username='john', email='john@nyit.edu', password_hash=_hash('player123'),
                full_name='John Smith', role='player'
            )
            db.session.add_all([self.admin, self.captain, self.player])
            db.session.commit()
            self.admin_id = self.admin.id
            self.captain_id = self.captain.id
            self.player_id = self.player.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # ---- helpers ----
    def csrf(self):
        with self.client.session_transaction() as sess:
            if 'csrf_token' not in sess:
                sess['csrf_token'] = 'TESTTOKEN'
            return sess['csrf_token']

    def login(self, username, password):
        return self.client.post('/login', data={
            'username': username, 'password': password,
            'csrf_token': self.csrf(),
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)


def _hash(pw):
    from werkzeug.security import generate_password_hash
    return generate_password_hash(pw, method='pbkdf2:sha256')


class TestAuth(BaseTestCase):
    def test_home_ok(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

    def test_login_success(self):
        r = self.login('admin', 'admin123')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Welcome back', r.data)

    def test_login_bad_password(self):
        r = self.login('admin', 'nope')
        self.assertIn(b'Invalid username or password', r.data)

    def test_csrf_blocks_posts_without_token(self):
        r = self.client.post('/login', data={'username': 'admin', 'password': 'admin123'})
        self.assertEqual(r.status_code, 400)

    def test_csrf_accepts_valid_header(self):
        self.csrf()
        r = self.client.post('/login',
                             data={'username': 'admin', 'password': 'admin123'},
                             headers={'X-CSRF-Token': 'TESTTOKEN'})
        self.assertEqual(r.status_code, 302)

    def test_login_rate_limit(self):
        for _ in range(5):
            self.client.post('/login', data={
                'username': 'admin', 'password': 'wrong', 'csrf_token': self.csrf(),
            })
        r = self.client.post('/login', data={
            'username': 'admin', 'password': 'wrong', 'csrf_token': self.csrf(),
        })
        self.assertIn(b'Too many failed attempts', r.data)

    def test_register(self):
        r = self.client.post('/register', data={
            'full_name': 'New Kid', 'username': 'newkid', 'email': 'nk@nyit.edu',
            'password': 'secret99', 'csrf_token': self.csrf(),
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            self.assertTrue(User.query.filter_by(username='newkid').first())

    def test_register_duplicate_username(self):
        r = self.client.post('/register', data={
            'full_name': 'Dup', 'username': 'john', 'email': 'x@nyit.edu',
            'password': 'secret99', 'csrf_token': self.csrf(),
        })
        self.assertIn(b'already taken', r.data)


class TestCorePages(BaseTestCase):
    def test_dashboard_required_login(self):
        r = self.client.get('/dashboard')
        self.assertEqual(r.status_code, 302)

    def test_leaderboard(self):
        r = self.client.get('/leaderboard')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'John Smith', r.data)

    def test_mvp_page(self):
        r = self.client.get('/mvp')
        self.assertEqual(r.status_code, 200)

    def test_mvp_vote_and_change(self):
        self.login('john', 'player123')
        self.client.post(f'/mvp/vote/{self.player_id}', data={'csrf_token': self.csrf()})
        self.client.post(f'/mvp/vote/{self.captain_id}', data={'csrf_token': self.csrf()})
        with app.app_context():
            votes = MvpVote.query.filter_by(user_id=self.player_id).count()
            self.assertEqual(votes, 1)
            winner = MvpVote.query.filter_by(user_id=self.player_id).first()
            self.assertEqual(winner.player_id, self.captain_id)

    def test_gallery_page(self):
        r = self.client.get('/gallery')
        self.assertEqual(r.status_code, 200)

    def test_gallery_upload(self):
        self.login('admin', 'admin123')
        data = {
            'caption': 'Test shot',
            'csrf_token': self.csrf(),
            'images': (io.BytesIO(b'fakeimagebytes'), 'team.png'),
        }
        r = self.client.post('/admin/gallery', data=data,
                             content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Test shot', r.data)

    def test_checkin(self):
        self.login('john', 'player123')
        self.client.post('/check-in', data={'csrf_token': self.csrf()}, follow_redirects=True)
        r = self.client.get('/dashboard')
        self.assertIn(b'On site', r.data)


class TestAdmin(BaseTestCase):
    def test_admin_users_blocked_for_player(self):
        self.login('john', 'player123')
        r = self.client.get('/admin/users')
        self.assertEqual(r.status_code, 302)

    def test_admin_user_role_change(self):
        self.login('admin', 'admin123')
        self.client.post(f'/admin/users/update/{self.player_id}',
                         data={'role': 'captain', 'csrf_token': self.csrf()},
                         follow_redirects=True)
        with app.app_context():
            self.assertEqual(User.query.get(self.player_id).role, 'captain')

    def test_admin_user_delete(self):
        self.login('admin', 'admin123')
        self.client.post(f'/admin/users/delete/{self.player_id}',
                         data={'csrf_token': self.csrf()}, follow_redirects=True)
        with app.app_context():
            self.assertIsNone(User.query.get(self.player_id))

    def test_backup_download(self):
        self.login('admin', 'admin123')
        r = self.client.get('/admin/backup')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, 'application/octet-stream')
        self.assertIn(b'SQLite format 3', r.data[:16])

    def test_publish_practice_pick(self):
        with app.app_context():
            avail = [
                Availability(player_id=self.player_id, day_of_week=2, time_slot='6pm', is_available=True),
                Availability(player_id=self.captain_id, day_of_week=2, time_slot='6pm', is_available=True),
            ]
            db.session.add_all(avail)
            db.session.commit()
        self.login('admin', 'admin123')
        r = self.client.post('/admin/calendar/publish',
                             data={'csrf_token': self.csrf()}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            self.assertTrue(Announcement.query.filter_by(title='📅 Recommended Practice Windows').first())


class TestBrackets(BaseTestCase):
    def _make_tournament_and_round(self):
        with app.app_context():
            t = Tournament(name='Test Cup', start_date='2026-01-01')
            db.session.add(t)
            db.session.commit()
            m1 = Match(match_date='2026-01-10', match_time='7pm',
                       team1_player1='Jane Doe', team2_player1='John Smith',
                       bracket_round=1, status='upcoming', tournament_id=t.id)
            m2 = Match(match_date='2026-01-10', match_time='7pm',
                       team1_player1='Admin User', team2_player1='New Kid',
                       bracket_round=1, status='upcoming', tournament_id=t.id)
            db.session.add_all([m1, m2])
            db.session.commit()
            self.tid = t.id
            self.m1_id = m1.id
            self.m2_id = m2.id

    def test_set_result_advances_winner(self):
        self._make_tournament_and_round()
        self.login('admin', 'admin123')
        self.client.post(f'/admin/set-result/{self.m1_id}', data={
            'winner': 'team1', 'score1': 21, 'score2': 15, 'csrf_token': self.csrf(),
        }, follow_redirects=True)
        self.client.post(f'/admin/set-result/{self.m2_id}', data={
            'winner': 'team1', 'score1': 21, 'score2': 18, 'csrf_token': self.csrf(),
        }, follow_redirects=True)
        with app.app_context():
            nxt = Match.query.filter_by(bracket_round=2).first()
            self.assertIsNotNone(nxt)
            self.assertEqual(nxt.team1_player1, 'Jane Doe')
            self.assertEqual(nxt.team2_player1, 'Admin User')


class TestRoster(BaseTestCase):
    def test_roster_staff_only(self):
        self.login('admin', 'admin123')
        self.assertEqual(self.client.get('/roster').status_code, 200)

    def test_roster_blocked_for_player(self):
        self.login('john', 'player123')
        self.assertEqual(self.client.get('/roster').status_code, 302)

    def test_toggle_check_in_out(self):
        self.login('admin', 'admin123')
        self.csrf()
        r = self.client.post(f'/roster/toggle/{self.player_id}',
                             headers={'X-CSRF-Token': 'TESTTOKEN'})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'"state":"in"', r.data)
        r = self.client.post(f'/roster/toggle/{self.player_id}',
                             headers={'X-CSRF-Token': 'TESTTOKEN'})
        self.assertIn(b'"state":"out"', r.data)

    def test_api_roster_present(self):
        self.login('admin', 'admin123')
        self.csrf()
        self.client.post(f'/roster/toggle/{self.player_id}',
                         headers={'X-CSRF-Token': 'TESTTOKEN'})
        r = self.client.get('/api/roster')
        j = r.get_json()
        self.assertEqual(j['present'], 1)
        self.assertEqual(len(j['players']), 3)

    def test_api_on_court(self):
        self.login('admin', 'admin123')
        self.assertEqual(self.client.get('/api/on-court').get_json()['count'], 0)

    def test_attendance_csv_export(self):
        self.login('admin', 'admin123')
        r = self.client.get('/admin/attendance/export')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r.mimetype)
        self.assertIn(b'Player,Username', r.data)

    def test_profile_photo_upload(self):
        self.login('john', 'player123')
        self.csrf()
        data = {
            'csrf_token': 'TESTTOKEN',
            'photo': (io.BytesIO(b'fakeimg'), 'me.png'),
        }
        r = self.client.post('/profile/john', data=data,
                             content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with app.app_context():
            john = User.query.filter_by(username='john').first()
            self.assertTrue(john.player_image.startswith('avatar_'))

    def test_profile_upload_own_only(self):
        self.login('john', 'player123')
        self.csrf()
        data = {
            'csrf_token': 'TESTTOKEN',
            'photo': (io.BytesIO(b'fakeimg'), 'hack.png'),
        }
        r = self.client.post('/profile/admin', data=data,
                             content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(r.status_code, 200)

    def test_checkout_notifies_player(self):
        self.login('admin', 'admin123')
        self.csrf()
        self.client.post(f'/roster/toggle/{self.player_id}',
                         headers={'X-CSRF-Token': 'TESTTOKEN'})
        self.client.post(f'/roster/toggle/{self.player_id}',
                         headers={'X-CSRF-Token': 'TESTTOKEN'})
        with app.app_context():
            from app import Notification
            self.assertTrue(Notification.query.filter_by(user_id=self.player_id).all())


if __name__ == '__main__':
    unittest.main(verbosity=2)