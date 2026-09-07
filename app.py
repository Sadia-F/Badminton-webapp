from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session, send_file, abort, after_this_request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import secrets
import sqlite3
import smtplib
import io
import re
import csv
import tempfile
from email.message import EmailMessage

app = Flask(__name__)
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    # Persist a generated key so sessions survive between restarts.
    secret_key = os.environ.get('FLASK_SECRET_FILE') or 'dev-secret-5f3c9b1a7e4d2f8a0c6b';
app.secret_key = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///team.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ============ DATABASE MODELS ============

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='player') # 'player', 'captain', 'admin'
    player_image = db.Column(db.String(200), default='default.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    matches = db.relationship('Match', backref='tournament', lazy=True)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_date = db.Column(db.String(20), nullable=False)
    match_time = db.Column(db.String(10))
    team1_player1 = db.Column(db.String(100))
    team1_player2 = db.Column(db.String(100))
    team2_player1 = db.Column(db.String(100))
    team2_player2 = db.Column(db.String(100))
    bracket_round = db.Column(db.Integer, default=1)
    winner = db.Column(db.String(100))
    status = db.Column(db.String(20), default='upcoming')
    score_team1 = db.Column(db.Integer, default=0)
    score_team2 = db.Column(db.Integer, default=0)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)

class Performance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    rating_type = db.Column(db.String(20), default='self') # 'self' or 'admin'
    smash_accuracy = db.Column(db.Integer)
    net_play = db.Column(db.Integer)
    footwork = db.Column(db.Integer)
    consistency = db.Column(db.Integer)
    shot_variety = db.Column(db.Integer)
    comments = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    player = db.relationship('User', backref='performances')
    match = db.relationship('Match', backref='performances')

class PracticeSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    location = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date_achieved = db.Column(db.DateTime, default=datetime.utcnow)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    player = db.relationship('User', backref='achievements')

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) # 0=Monday, 6=Sunday
    time_slot = db.Column(db.String(20), nullable=False) # '6pm', '7pm', etc.
    is_available = db.Column(db.Boolean, default=False)
    player = db.relationship('User', backref='availabilities')

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.String(20), default=datetime.now().strftime('%Y-%m-%d'))
    player = db.relationship('User', backref='check_ins')

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    player_score = db.Column(db.Integer)
    opponent_score = db.Column(db.Integer)
    is_winner = db.Column(db.Boolean, default=False)
    match = db.relationship('Match', backref='scores')
    player = db.relationship('User', backref='scores')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='notifications')

class MvpNomination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.String(20), nullable=False)  # Monday date, YYYY-MM-DD
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nominated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    player = db.relationship('User', foreign_keys=[player_id], backref='mvp_nominations')
    db.UniqueConstraint('week_start', 'player_id', name='uq_mvp_week_player')

class MvpVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.String(20), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    db.UniqueConstraint('week_start', 'user_id', name='uq_mvp_week_user')
    player = db.relationship('User', foreign_keys=[player_id])

class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(300))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def all_players():
    return User.query.order_by(User.role, User.full_name).all()


# ============ SECURITY: CSRF + LOGIN RATE LIMITING ============

login_attempts = {}

def enforce_csrf():
    if request.method != 'POST':
        return
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not token or token != session.get('csrf_token'):
        abort(400, description="Invalid or missing CSRF token. Please refresh and try again.")

app.before_request(enforce_csrf)


@app.context_processor
def inject_globals():
    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return session['csrf_token']
    def active(*endpoints):
        try:
            return 'active' if request.endpoint in endpoints else ''
        except Exception:
            return ''
    def avatar_url(user):
        if isinstance(user, dict):
            return user.get('img')
        try:
            if user and getattr(user, 'player_image', None) and user.player_image != 'default.png':
                return url_for('static', filename='uploads/' + user.player_image)
        except Exception:
            pass
        return None
    return dict(active=active, csrf_token=csrf_token, all_players=all_players, avatar_url=avatar_url)


def rate_limit_login(username):
    now = datetime.now()
    ip = request.remote_addr or 'unknown'
    key = f"{ip}:{username}"
    attempts = login_attempts.setdefault(key, [])
    attempts[:] = [t for t in attempts if t > now - timedelta(minutes=15)]
    if len(attempts) >= 5:
        return False
    return True

def record_failed_login(username):
    login_attempts.setdefault(f"{request.remote_addr}:{username}", []).append(datetime.now())


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not rate_limit_login(username):
            flash('⛔ Too many failed attempts. Try again in 15 minutes.', 'danger')
            return render_template('login.html')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            login_attempts.pop(f"{request.remote_addr}:{username}", None)
            flash('✅ Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            record_failed_login(username)
            flash('❌ Invalid username or password', 'danger')
    return render_template('login.html')


# ============ EMAIL REMINDERS (optional SMTP) ============

EMAIL_CONFIG = {
    'host': os.environ.get('SMTP_HOST'),
    'port': int(os.environ.get('SMTP_PORT', '587')),
    'user': os.environ.get('SMTP_USER'),
    'password': os.environ.get('SMTP_PASSWORD'),
    'from': os.environ.get('SMTP_FROM', os.environ.get('SMTP_USER')),
}

def send_email(to_email, subject, body):
    if not EMAIL_CONFIG['host'] or not EMAIL_CONFIG['from']:
        return False
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_CONFIG['from']
        msg['To'] = to_email
        msg.set_content(body)
        with smtplib.SMTP(EMAIL_CONFIG['host'], EMAIL_CONFIG['port'], timeout=10) as server:
            server.starttls()
            if EMAIL_CONFIG['user'] and EMAIL_CONFIG['password']:
                server.login(EMAIL_CONFIG['user'], EMAIL_CONFIG['password'])
            server.send_message(msg)
        return True
    except Exception:
        print(f"[email] failed to send to {to_email}: subject={subject}")
        return False

# ============ CREATE DATABASE ============

with app.app_context():
    db.create_all()
    
    if not User.query.first():
        admin = User(
            username='admin',
            email='admin@nyit.edu',
            password_hash=generate_password_hash('admin123'),
            full_name='Admin User',
            role='admin'
        )
        db.session.add(admin)

        players = [
            User(username='john', email='john@nyit.edu', password_hash=generate_password_hash('player123'), full_name='John Doe', role='player'),
            User(username='jane', email='jane@nyit.edu', password_hash=generate_password_hash('player123'), full_name='Jane Smith', role='captain'),
            User(username='mike', email='mike@nyit.edu', password_hash=generate_password_hash('player123'), full_name='Mike Johnson', role='player'),
        ]
        db.session.add_all(players)
        db.session.commit()
        print("✅ Users created!")
    
    if not PracticeSchedule.query.first():
        schedules = [
            PracticeSchedule(day='Monday', start_time='6:00 PM', end_time='8:00 PM', location='Court A - Main Hall'),
            PracticeSchedule(day='Wednesday', start_time='6:00 PM', end_time='8:00 PM', location='Court B - East Wing'),
            PracticeSchedule(day='Friday', start_time='5:00 PM', end_time='7:00 PM', location='Court A - Main Hall'),
        ]
        db.session.add_all(schedules)
        db.session.commit()
        print("✅ Practice schedules created!")
    
    if not Announcement.query.first():
        announcements = [
            Announcement(title='🏸 Welcome to NYIT Badminton!', content='Season 2024-2025 starts now! Check the schedule for practice times.', is_public=True),
            Announcement(title='🏆 Tournament Coming Up', content='Inter-University Tournament next month. Start practicing!', is_public=True),
        ]
        db.session.add_all(announcements)
        db.session.commit()
        print("✅ Announcements created!")

# ============ PLAYER PROFILES ============

@app.route('/profile/<username>', methods=['GET', 'POST'])
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()

    if request.method == 'POST':
        if user.id != current_user.id:
            flash('⚠️ You can only edit your own profile.', 'danger')
            return redirect(url_for('profile', username=username))
        file = request.files.get('photo')
        if file and file.filename and allowed_image(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique = f"avatar_{user.id}_{secrets.token_hex(4)}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, unique))
            if user.player_image and user.player_image != 'default.png':
                old = os.path.join(UPLOAD_FOLDER, user.player_image)
                if os.path.exists(old):
                    os.remove(old)
            user.player_image = unique
            db.session.commit()
            flash('📸 Profile photo updated! Looking fresh.', 'success')
        else:
            flash('⚠️ Please choose a valid image (png, jpg, gif, webp).', 'warning')
        return redirect(url_for('profile', username=username))

    # Career Stats
    scores = Score.query.filter_by(player_id=user.id).all()
    total_matches = len(scores)
    wins = sum(1 for s in scores if s.is_winner)
    win_rate = (wins / total_matches * 100) if total_matches > 0 else 0

    # Performance Aggregation for Radar Chart
    performances = Performance.query.filter_by(player_id=user.id).all()
    count = len(performances)

    metrics = {
        "smash": sum(p.smash_accuracy or 0 for p in performances) / count if count > 0 else 0,
        "net": sum(p.net_play or 0 for p in performances) / count if count > 0 else 0,
        "footwork": sum(p.footwork or 0 for p in performances) / count if count > 0 else 0,
        "consistency": sum(p.consistency or 0 for p in performances) / count if count > 0 else 0,
        "variety": sum(p.shot_variety or 0 for p in performances) / count if count > 0 else 0,
    }

    achievements = Achievement.query.filter_by(player_id=user.id).all()
    today = datetime.now().strftime('%Y-%m-%d')
    on_court_today = bool(CheckIn.query.filter_by(player_id=user.id, date=today).first())

    return render_template('profile.html',
                         user=user,
                         can_edit=(current_user.is_authenticated and user.id == current_user.id),
                         on_court_today=on_court_today,
                         streak=attendance_streak(user.id),
                         total_matches=total_matches,
                         wins=wins,
                         win_rate=round(win_rate, 1),
                         metrics=metrics,
                         achievements=achievements)

# ============ HELPERS ============

@app.context_processor
def inject_notifications():
    unread_count = 0
    recent_notifs = []
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        recent_notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).limit(5).all()
    return dict(unread_notifs=unread_count, recent_notifs=recent_notifs)

def create_notification(user_id, message):
    notif = Notification(user_id=user_id, message=message)
    db.session.add(notif)
    db.session.commit()
    user = User.query.get(user_id)
    if user and user.email:
        send_email(user.email, "NYIT Badminton Update", message)

@app.route('/notifications/read/<int:id>')
@login_required
def mark_notification_read(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))


# ============ GAMIFICATION HELPERS ============

def attendance_streak(player_id):
    """Current consecutive-day check-in streak (ending today or yesterday)."""
    dates = sorted({c.date for c in CheckIn.query.filter_by(player_id=player_id).all()})
    if not dates:
        return 0
    try:
        date_set = {datetime.strptime(d, '%Y-%m-%d').date() for d in dates}
    except Exception:
        return 0
    start = datetime.now().date()
    if start not in date_set:
        start -= timedelta(days=1)
    if start not in date_set:
        return 0
    streak = 0
    while start in date_set:
        streak += 1
        start -= timedelta(days=1)
    return streak


def player_rating(user_id):
    perfs = Performance.query.filter_by(player_id=user_id).all()
    if not perfs:
        return 0.0
    total = sum(
        (p.smash_accuracy or 0) + (p.net_play or 0) + (p.footwork or 0) +
        (p.consistency or 0) + (p.shot_variety or 0) for p in perfs
    )
    return round(total / (len(perfs) * 5), 1)


def team_leaderboard():
    rows = []
    for u in User.query.all():
        scores = Score.query.filter_by(player_id=u.id).all()
        wins = sum(1 for s in scores if s.is_winner)
        rows.append({
            'id': u.id, 'name': u.full_name, 'username': u.username,
            'role': u.role, 'wins': wins, 'matches': len(scores),
            'win_rate': round(wins / len(scores) * 100, 1) if scores else 0.0,
            'rating': player_rating(u.id),
            'streak': attendance_streak(u.id),
            'checkins': CheckIn.query.filter_by(player_id=u.id).count(),
        })
    return sorted(rows, key=lambda r: (r['wins'], r['win_rate'], r['rating']), reverse=True)


def current_week_start():
    today = datetime.now().date()
    return (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')


def best_practice_slots(n=2):
    """Top (day, slot) pairs by team availability."""
    availabilities = Availability.query.filter_by(is_available=True).all()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    counts = {}
    for av in availabilities:
        if 0 <= av.day_of_week <= 6:
            key = (days[av.day_of_week], av.time_slot)
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    total_players = User.query.count()
    return [{'day': k[0], 'slot': k[1], 'count': v, 'total': total_players} for k, v in ranked[:n]]

# ============ CALENDAR SYNC ============

@app.route('/schedule/export')
@login_required
def export_schedule():
    schedules = PracticeSchedule.query.filter_by(is_active=True).all()

    # Basic iCalendar format
    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NYIT Badminton//Team Manager//EN"
    ]

    days_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    for s in schedules:
        # Note: For a real iCal we would need a specific date.
        # Since these are recurring weekly, we'll set them for the next occurrence.
        day_idx = days_map.get(s.day, 0)

        # Calculate next occurrence of this day
        today = datetime.utcnow().date()
        days_ahead = (day_idx - today.weekday()) % 7
        event_date = today + timedelta(days=days_ahead)
        date_str = event_date.strftime('%Y%m%d')

        # Normalize time (e.g., "6:00 PM" -> "180000")
        def normalize_time(t_str):
            t_str = t_str.strip().upper()
            if 'AM' in t_str:
                hour = int(t_str.split(':')[0])
                if hour == 12: hour = 0
            else:
                hour = int(t_str.split(':')[0])
                if hour != 12: hour += 12
                elif hour == 12: hour = 12
            minutes = t_str.split(':')[1].split(' ')[0].zfill(2)
            return f"{hour:02d}{minutes}00"

        start_time = normalize_time(s.start_time)
        end_time = normalize_time(s.end_time)

        ics_content.append("BEGIN:VEVENT")
        ics_content.append(f"SUMMARY:NYIT Badminton Practice ({s.day})")
        ics_content.append(f"DTSTART;TZID=America/New_York:{date_str}T{start_time}")
        ics_content.append(f"DTEND;TZID=America/New_York:{date_str}T{end_time}")
        ics_content.append(f"LOCATION:{s.location}")
        ics_content.append("RRULE:FREQ=WEEKLY")
        ics_content.append("END:VEVENT")

    ics_content.append("END:VCALENDAR")

    return Response(
        "\n".join(ics_content),
        mimetype="text/calendar",
        headers={"Content-disposition": "attachment; filename=badminton_schedule.ics"}
    )

# ============ PUBLIC ROUTES ============

@app.route('/')
def home():
    announcements = Announcement.query.filter_by(is_public=True).order_by(Announcement.date_posted.desc()).limit(3).all()
    stats = {
        'players': User.query.count(),
        'matches': Match.query.count(),
        'tournaments': Tournament.query.filter_by(is_active=True).count(),
        'practices': PracticeSchedule.query.filter_by(is_active=True).count(),
    }
    return render_template('home.html', announcements=announcements, stats=stats)

@app.route('/announcements')
def announcements_page():
    announcements = Announcement.query.filter_by(is_public=True).order_by(Announcement.date_posted.desc()).all()
    return render_template('announcements.html', announcements=announcements)

@app.route('/schedule')
def schedule():
    schedules = PracticeSchedule.query.filter_by(is_active=True).all()
    return render_template('schedule.html', schedules=schedules)

@app.route('/achievements')
def achievements_page():
    achievements = Achievement.query.all()
    return render_template('achievements.html', achievements=achievements)

@app.route('/team')
def team():
    players = all_players()
    return render_template('team.html', players=players)

# ============ AUTH ROUTES ============

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('👋 Logged out successfully', 'info')
    return redirect(url_for('home'))

# ============ REGISTRATION ============

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        full_name = (request.form.get('full_name') or '').strip()
        password = request.form.get('password')
        errors = []
        if not re.match(r'^[A-Za-z0-9_]{3,20}$', username):
            errors.append('Username must be 3-20 characters (letters, numbers, underscore).')
        if '@' not in email or '.' not in email.split('@')[-1]:
            errors.append('Please enter a valid email address.')
        if len(full_name) < 2:
            errors.append('Please enter your full name.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if User.query.filter_by(username=username).first():
            errors.append('That username is already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('That email is already registered.')
        if errors:
            for e in errors:
                flash(f'⚠️ {e}', 'danger')
            return render_template('register.html', values=request.form)
        user = User(
            username=username, email=email,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            full_name=full_name, role='player'
        )
        db.session.add(user)
        db.session.commit()
        flash('✅ Account created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', values={})

# ============ LEADERBOARD ============

@app.route('/leaderboard')
def leaderboard():
    rows = team_leaderboard()
    return render_template('leaderboard.html', rows=rows)

# ============ WEEKLY MVP ============

@app.route('/mvp', methods=['GET'])
def mvp():
    week = current_week_start()
    votes = MvpVote.query.filter_by(week_start=week).all()
    totals = {}
    for v in votes:
        player = User.query.get(v.player_id)
        if player:
            totals[player] = totals.get(player, 0) + 1
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    my_vote = None
    if current_user.is_authenticated:
        mine = MvpVote.query.filter_by(week_start=week, user_id=current_user.id).first()
        my_vote = mine.player_id if mine else None
    past = []
    for n in MvpNomination.query.filter(MvpNomination.week_start != week).all():
        votes_for = MvpVote.query.filter_by(week_start=n.week_start, player_id=n.player_id).count()
        player = User.query.get(n.player_id)
        if player and (player, votes_for) not in past:
            past.append((n.week_start, player, votes_for))
    past_weeks = {}
    for ws, player, vcount in past:
        past_weeks.setdefault(ws, []).append((player, vcount))
    past_weeks = dict(sorted(past_weeks.items(), reverse=True))
    return render_template('mvp.html', week=week, ranked=ranked, votes=votes, my_vote=my_vote, past_weeks=past_weeks)

@app.route('/mvp/vote/<int:player_id>', methods=['POST'])
@login_required
def mvp_vote(player_id):
    player = User.query.get_or_404(player_id)
    week = current_week_start()
    existing = MvpVote.query.filter_by(week_start=week, user_id=current_user.id).first()
    if existing:
        existing.player_id = player_id
    else:
        db.session.add(MvpVote(week_start=week, player_id=player_id, user_id=current_user.id))
    if not MvpNomination.query.filter_by(week_start=week, player_id=player_id).first():
        db.session.add(MvpNomination(week_start=week, player_id=player_id, nominated_by=current_user.id))
    db.session.commit()
    flash(f'⭐ You voted for {player.full_name}!', 'success')
    return redirect(url_for('mvp'))

# ============ GALLERY ============

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMG

@app.route('/gallery')
def gallery():
    images = GalleryImage.query.order_by(GalleryImage.uploaded_at.desc()).all()
    return render_template('gallery.html', images=images)

@app.route('/admin/gallery', methods=['GET', 'POST'])
@login_required
def admin_gallery():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        caption = request.form.get('caption', '').strip()
        files = request.files.getlist('images')
        added = 0
        for f in files:
            if f and allowed_image(f.filename):
                unique = f"{secrets.token_hex(4)}_{f.filename.replace(' ', '_')}"
                f.save(os.path.join(UPLOAD_FOLDER, unique))
                db.session.add(GalleryImage(filename=unique, caption=caption, uploaded_by=current_user.id))
                added += 1
        db.session.commit()
        flash(f'📸 {added} photo(s) uploaded!', 'success' if added else 'warning')
        return redirect(url_for('admin_gallery'))
    images = GalleryImage.query.order_by(GalleryImage.uploaded_at.desc()).all()
    return render_template('admin_gallery.html', images=images)

@app.route('/admin/gallery/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_gallery_delete(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    img = GalleryImage.query.get_or_404(id)
    path = os.path.join(UPLOAD_FOLDER, img.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(img)
    db.session.commit()
    flash('🗑️ Image deleted.', 'info')
    return redirect(url_for('admin_gallery'))

# ============ DASHBOARD ============

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().strftime('%Y-%m-%d')
    checkin_status = CheckIn.query.filter_by(player_id=current_user.id, date=today).first()
    matches = Match.query.order_by(Match.match_date).limit(5).all()
    performances = Performance.query.filter_by(player_id=current_user.id).order_by(Performance.date.desc()).limit(5).all()
    today_checkins = CheckIn.query.filter_by(date=today).count()
    total_players = User.query.count()
    week = current_week_start()
    mvp_votes = MvpVote.query.filter_by(week_start=week).all()
    mvp_totals = {}
    for v in mvp_votes:
        p = User.query.get(v.player_id)
        if p:
            mvp_totals[p.full_name] = mvp_totals.get(p.full_name, 0) + 1
    weekly_mvp = max(mvp_totals, key=mvp_totals.get) if mvp_totals else None
    return render_template('dashboard.html',
                         checkin_status=bool(checkin_status),
                         matches=matches,
                         performances=performances,
                         today_checkins=today_checkins,
                         total_players=total_players,
                         streak=attendance_streak(current_user.id),
                         weekly_mvp=weekly_mvp,
                         datetime=datetime)

# ============ CHECK-IN ============

@app.route('/check-in', methods=['POST'])
@login_required
def check_in():
    today = datetime.now().strftime('%Y-%m-%d')
    existing = CheckIn.query.filter_by(player_id=current_user.id, date=today).first()
    if existing:
        flash('You already checked in today!', 'warning')
    else:
        checkin = CheckIn(player_id=current_user.id)
        db.session.add(checkin)
        db.session.commit()
        flash('✅ Checked in successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin/bulk-checkin', methods=['GET', 'POST'])
@login_required
def admin_bulk_checkin():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        player_ids = request.form.getlist('player_ids')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

        count = 0
        for p_id in player_ids:
            existing = CheckIn.query.filter_by(player_id=p_id, date=date).first()
            if not existing:
                checkin = CheckIn(player_id=p_id, date=date)
                db.session.add(checkin)
                count += 1

        db.session.commit()
        flash(f'✅ Successfully checked in {count} players!', 'success')
        return redirect(url_for('admin_bulk_checkin'))

    players = all_players()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('admin_bulk_checkin.html', players=players, today=today)

# ============ AVAILABILITY ============

@app.route('/availability', methods=['GET', 'POST'])
@login_required
def availability():
    if request.method == 'POST':
        day = int(request.form.get('day'))
        slot = request.form.get('slot')
        available = 'available' in request.form or request.form.get('status') == 'available'

        # Upsert availability
        avail = Availability.query.filter_by(player_id=current_user.id, day_of_week=day, time_slot=slot).first()
        if avail:
            avail.is_available = available
        else:
            avail = Availability(
                player_id=current_user.id,
                day_of_week=day,
                time_slot=slot,
                is_available=available
            )
            db.session.add(avail)

        db.session.commit()
        flash('✅ Availability updated!', 'success')
        return redirect(url_for('availability'))

    availabilities = Availability.query.filter_by(player_id=current_user.id).all()
    return render_template('availability.html', availabilities=availabilities)

@app.route('/availability/delete/<int:id>')
@login_required
def delete_availability(id):
    avail = Availability.query.get_or_404(id)
    if avail.player_id == current_user.id or current_user.role in ['admin', 'captain']:
        db.session.delete(avail)
        db.session.commit()
        flash('Availability deleted.', 'info')
    return redirect(url_for('availability'))

# ============ MATCHES ============

@app.route('/matches')
@login_required
def matches():
    all_matches = Match.query.order_by(Match.match_date).all()
    return render_template('matches.html', matches=all_matches)

@app.route('/brackets')
@login_required
def brackets():
    matches = Match.query.order_by(Match.bracket_round, Match.match_date).all()
    rounds = {}
    for match in matches:
        if match.bracket_round not in rounds:
            rounds[match.bracket_round] = []
        rounds[match.bracket_round].append(match)
    return render_template('brackets.html', rounds=rounds)

# ============ SCORES ============

@app.route('/update-score', methods=['GET', 'POST'])
@login_required
def update_score():
    if request.method == 'POST':
        match_id = request.form.get('match_id')
        player_score = int(request.form.get('player_score'))
        opponent_score = int(request.form.get('opponent_score'))
        is_winner = player_score > opponent_score
        score = Score(
            match_id=match_id,
            player_id=current_user.id,
            player_score=player_score,
            opponent_score=opponent_score,
            is_winner=is_winner
        )
        db.session.add(score)
        db.session.commit()
        flash('✅ Score updated!', 'success')
        return redirect(url_for('update_score'))
    matches = Match.query.filter_by(status='completed').order_by(Match.match_date.desc()).all()
    scores = Score.query.filter_by(player_id=current_user.id).all()
    return render_template('update_score.html', matches=matches, scores=scores)

# ============ PERFORMANCE ============

@app.route('/performance', methods=['GET', 'POST'])
@login_required
def performance():
    if request.method == 'POST':
        match_id = request.form.get('match_id')
        rating_type = request.form.get('rating_type', 'self')
        smash = int(request.form.get('smash_accuracy', 0))
        net = int(request.form.get('net_play', 0))
        foot = int(request.form.get('footwork', 0))
        cons = int(request.form.get('consistency', 0))
        variety = int(request.form.get('shot_variety', 0))
        comments = request.form.get('comments', '')

        perf = Performance(
            player_id=current_user.id,
            match_id=int(match_id) if match_id else None,
            rating_type=rating_type,
            smash_accuracy=smash,
            net_play=net,
            footwork=foot,
            consistency=cons,
            shot_variety=variety,
            comments=comments
        )
        db.session.add(perf)
        db.session.commit()
        flash('⭐ Performance rated!', 'success')
        return redirect(url_for('performance'))
    performances = Performance.query.filter_by(player_id=current_user.id).order_by(Performance.date.desc()).all()
    matches = Match.query.order_by(Match.match_date.desc()).all()
    return render_template('performance.html', performances=performances, matches=matches)

# ============ ADMIN ROUTES ============

@app.route('/admin/rate-player', methods=['GET', 'POST'])
@login_required
def admin_rate_player():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        player_id = request.form.get('player_id')
        smash = int(request.form.get('smash_accuracy', 0))
        net = int(request.form.get('net_play', 0))
        foot = int(request.form.get('footwork', 0))
        cons = int(request.form.get('consistency', 0))
        variety = int(request.form.get('shot_variety', 0))
        comments = request.form.get('comments', '')
        match_id = request.form.get('match_id')

        perf = Performance(
            player_id=player_id,
            match_id=int(match_id) if match_id else None,
            rating_type='admin',
            smash_accuracy=smash,
            net_play=net,
            footwork=foot,
            consistency=cons,
            shot_variety=variety,
            comments=comments
        )
        db.session.add(perf)
        db.session.commit()
        flash(f'✅ Rating submitted for player {player_id}!', 'success')
        return redirect(url_for('admin_panel'))

    players = all_players()
    matches = Match.query.order_by(Match.match_date.desc()).all()
    return render_template('admin_rate_player.html', players=players, matches=matches)

# ============ CONTENT MANAGEMENT ============

@app.route('/admin/announcements', methods=['GET', 'POST'])
@login_required
def admin_announcements():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        is_public = 'is_public' in request.form
        is_pinned = 'is_pinned' in request.form

        ann = Announcement(title=title, content=content, is_public=is_public, is_pinned=is_pinned)
        db.session.add(ann)
        db.session.commit()

        if is_pinned:
            for p in User.query.all():
                create_notification(p.id, f"📌 New Pinned Announcement: {title}")

        flash('📢 Announcement posted!', 'success')
        return redirect(url_for('admin_announcements'))

    announcements = Announcement.query.order_by(Announcement.is_pinned.desc(), Announcement.date_posted.desc()).all()
    return render_template('admin_announcements.html', announcements=announcements)

@app.route('/admin/announcements/delete/<int:id>')
@login_required
def delete_announcement(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    ann = Announcement.query.get_or_404(id)
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'info')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/achievements', methods=['GET', 'POST'])
@login_required
def admin_achievements():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        player_id = request.form.get('player_id')

        ach = Achievement(title=title, description=description, player_id=player_id if player_id else None)
        db.session.add(ach)
        db.session.commit()
        flash('🏆 Achievement added!', 'success')
        return redirect(url_for('admin_achievements'))

    achievements = Achievement.query.order_by(Achievement.date_achieved.desc()).all()
    players = all_players()
    return render_template('admin_achievements.html', achievements=achievements, players=players)

@app.route('/admin/achievements/delete/<int:id>')
@login_required
def delete_achievement(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    ach = Achievement.query.get_or_404(id)
    db.session.delete(ach)
    db.session.commit()
    flash('Achievement deleted.', 'info')
    return redirect(url_for('admin_achievements'))

@app.route('/admin/schedule', methods=['GET', 'POST'])
@login_required
def admin_schedule():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        day = request.form.get('day')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        location = request.form.get('location')
        is_active = 'is_active' in request.form

        # Update existing or create new
        schedule_id = request.form.get('schedule_id')
        if schedule_id:
            sched = PracticeSchedule.query.get(schedule_id)
            sched.day = day
            sched.start_time = start_time
            sched.end_time = end_time
            sched.location = location
            sched.is_active = is_active
        else:
            sched = PracticeSchedule(day=day, start_time=start_time, end_time=end_time, location=location, is_active=is_active)
            db.session.add(sched)

        db.session.commit()
        flash('📅 Schedule updated!', 'success')
        return redirect(url_for('admin_schedule'))

    schedules = PracticeSchedule.query.all()
    return render_template('admin_schedule.html', schedules=schedules)

@app.route('/admin/schedule/delete/<int:id>')
@login_required
def delete_schedule(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    sched = PracticeSchedule.query.get_or_404(id)
    db.session.delete(sched)
    db.session.commit()
    flash('Schedule deleted.', 'info')
    return redirect(url_for('admin_schedule'))

# ============ TOURNAMENTS ============

@app.route('/admin/auto-seed', methods=['GET', 'POST'])
@login_required
def admin_auto_seed():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        tournament_id = request.form.get('tournament_id')
        if not tournament_id:
            flash('Please select a tournament', 'warning')
            return redirect(url_for('admin_auto_seed'))

        # 1. Calculate ratings for all players
        players = all_players()
        player_ratings = []
        for p in players:
            perfs = Performance.query.filter_by(player_id=p.id).all()
            if not perfs:
                rating = 50.0 # Baseline
            else:
                total = 0
                for perf in perfs:
                    total += (perf.smash_accuracy or 0) + (perf.net_play or 0) + \
                              (perf.footwork or 0) + (perf.consistency or 0) + \
                              (perf.shot_variety or 0)
                rating = total / (len(perfs) * 5)
            player_ratings.append({'id': p.id, 'name': p.full_name, 'rating': rating})

        # Sort players by rating (descending)
        player_ratings.sort(key=lambda x: x['rating'], reverse=True)

        # 2. Create balanced teams (1st + Last, 2nd + 2nd Last, etc.)
        teams = []
        left = 0
        right = len(player_ratings) - 1
        while left < right:
            p1 = player_ratings[left]
            p2 = player_ratings[right]
            teams.append({
                'players': [p1, p2],
                'rating': (p1['rating'] + p2['rating']) / 2
            })
            left += 1
            right -= 1

        # Handle odd number of players
        if left == right:
            p_odd = player_ratings[left]
            teams.append({
                'players': [p_odd, {'name': 'Bye', 'rating': 0}],
                'rating': p_odd['rating'] / 2
            })

        # 3. Seed teams (Sorted by combined rating)
        teams.sort(key=lambda x: x['rating'], reverse=True)

        # 4. Generate matches (Seed 1 vs Seed N, etc.)
        num_teams = len(teams)
        # Ensure we have a power of 2 for the bracket (simple version)
        match_count = num_teams // 2

        for i in range(match_count):
            # Standard seeding: Seed i+1 vs Seed (N - i)
            team1 = teams[i]
            team2 = teams[num_teams - 1 - i]

            match = Match(
                match_date=datetime.now().strftime('%Y-%m-%d'),
                match_time='TBD',
                team1_player1=team1['players'][0]['name'],
                team1_player2=team1['players'][1]['name'] if 'name' not in team1['players'][1] else 'Bye',
                team2_player1=team2['players'][0]['name'],
                team2_player2=team2['players'][1]['name'] if 'name' not in team2['players'][1] else 'Bye',
                bracket_round=1,
                status='upcoming',
                tournament_id=tournament_id
            )
            db.session.add(match)

            # Notify players in the match
            for player_name in [team1['players'][0]['name'], team2['players'][0]['name']]:
                user = User.query.filter_by(full_name=player_name).first()
                if user:
                    create_notification(user.id, f"🏆 A new match has been scheduled for you in the tournament!")

        db.session.commit()
        flash(f'✅ Successfully auto-seeded {match_count} matches!', 'success')
        return redirect(url_for('matches'))

    tournaments = Tournament.query.all()
    return render_template('admin_auto_seed.html', tournaments=tournaments)

@app.route('/admin/tournaments', methods=['GET', 'POST'])
@login_required
def admin_tournaments():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        tournament = Tournament(name=name, start_date=start_date, end_date=end_date)
        db.session.add(tournament)
        db.session.commit()
        flash('🏆 Tournament created!', 'success')
        return redirect(url_for('admin_tournaments'))

    tournaments = Tournament.query.all()
    return render_template('admin_tournaments.html', tournaments=tournaments)

@app.route('/admin/tournaments/delete/<int:id>')
@login_required
def delete_tournament(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    tournament = Tournament.query.get_or_404(id)
    db.session.delete(tournament)
    db.session.commit()
    flash('Tournament deleted.', 'info')
    return redirect(url_for('admin_tournaments'))

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))
    players = all_players()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    today = datetime.now().strftime('%Y-%m-%d')
    checkins = CheckIn.query.filter_by(date=today).all()
    return render_template('admin.html', players=players, announcements=announcements, checkins=checkins, today=today)

@app.route('/admin/check-players', methods=['POST'])
@login_required
def admin_check_players():
    if current_user.role not in ['admin', 'captain']:
        return jsonify({'error': 'Unauthorized'}), 403
    player_id = request.form.get('player_id')
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    existing = CheckIn.query.filter_by(player_id=player_id, date=date).first()
    if existing:
        flash('Player already checked in!', 'warning')
    else:
        checkin = CheckIn(player_id=player_id, date=date)
        db.session.add(checkin)
        db.session.commit()
        flash('✅ Player checked in!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/attendance')
@login_required
def admin_attendance():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))
    checkins = CheckIn.query.all()
    attendance_by_date = {}
    for checkin in checkins:
        if checkin.date not in attendance_by_date:
            attendance_by_date[checkin.date] = []
        user = User.query.get(checkin.player_id)
        if user:
            attendance_by_date[checkin.date].append(user.full_name)
    return render_template('admin_attendance.html', attendance_by_date=attendance_by_date)

@app.route('/admin/player-stats/<int:player_id>')
@login_required
def admin_player_stats(player_id):
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))
    player = User.query.get_or_404(player_id)
    performances = Performance.query.filter_by(player_id=player_id).all()
    checkins = CheckIn.query.filter_by(player_id=player_id).all()
    scores = Score.query.filter_by(player_id=player_id).all()

    # Calculate average rating across all performance metrics
    total_score = 0
    count = 0
    for p in performances:
        total_score += (p.smash_accuracy or 0) + (p.net_play or 0) + (p.footwork or 0) + (p.consistency or 0) + (p.shot_variety or 0)
        count += 5

    avg_rating = total_score / count if count > 0 else 0
    wins = sum(1 for s in scores if s.is_winner)
    total_scores = len(scores)
    win_rate = (wins / total_scores * 100) if total_scores > 0 else 0
    return render_template('admin_player_stats.html',
                         player=player,
                         avg_rating=round(avg_rating, 1),
                         total_checkins=len(checkins),
                         wins=wins,
                         total_matches=total_scores,
                         win_rate=round(win_rate, 1),
                         performances=performances[:10])

@app.route('/admin/calendar')
@login_required
def admin_calendar():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))

    availabilities = Availability.query.all()
    # Group by day_of_week and time_slot
    calendar_data = {} # {day: {slot: count}}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    slots = ['12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm']

    for day in days:
        calendar_data[day] = {slot: 0 for slot in slots}

    for av in availabilities:
        if av.is_available:
            day_name = days[av.day_of_week] if 0 <= av.day_of_week < 7 else None
            if day_name and av.time_slot in calendar_data[day_name]:
                calendar_data[day_name][av.time_slot] += 1

    return render_template('admin_calendar.html', calendar_data=calendar_data, slots=slots, recommendations=best_practice_slots(2))

@app.route('/admin/create-brackets', methods=['GET', 'POST'])
@login_required
def admin_create_brackets():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))

    tournament_id = request.args.get('tournament_id')

    if request.method == 'POST':
        match_date = request.form.get('match_date')
        match_time = request.form.get('match_time')
        team1_p1 = request.form.get('team1_p1')
        team1_p2 = request.form.get('team1_p2')
        team2_p1 = request.form.get('team2_p1')
        team2_p2 = request.form.get('team2_p2')
        bracket_round = int(request.form.get('bracket_round', 1))
        t_id = request.form.get('tournament_id')

        match = Match(
            match_date=match_date,
            match_time=match_time,
            team1_player1=team1_p1,
            team1_player2=team1_p2,
            team2_player1=team2_p1,
            team2_player2=team2_p2,
            bracket_round=bracket_round,
            status='upcoming',
            tournament_id=t_id
        )
        db.session.add(match)

        # Notify players in the match
        for player_name in [team1_p1, team1_p2, team2_p1, team2_p2]:
            if player_name:
                user = User.query.filter_by(full_name=player_name).first()
                if user:
                    create_notification(user.id, f"🏆 A new match has been scheduled for you!")

        db.session.commit()
        flash('🏆 Bracket match created!', 'success')
        return redirect(url_for('matches'))

    players = all_players()
    tournaments = Tournament.query.all()
    return render_template('admin_create_brackets.html', players=players, tournaments=tournaments, tournament_id=tournament_id)

# ============ LIVE ROSTER (STAFF) ============

@app.route('/roster')
@login_required
def roster_page():
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))
    today = datetime.now().strftime('%Y-%m-%d')
    checkins = {c.player_id: c for c in CheckIn.query.filter_by(date=today).all()}
    rows = [{
        'id': u.id, 'name': u.full_name, 'username': u.username, 'role': u.role,
        'streak': attendance_streak(u.id),
        'img': url_for('static', filename='uploads/' + u.player_image) if u.player_image and u.player_image != 'default.png' else None,
        'status': 'in' if u.id in checkins else 'out',
        'time': checkins[u.id].check_in_time.strftime('%I:%M %p') if u.id in checkins else None,
    } for u in all_players()]
    present = sum(1 for r in rows if r['status'] == 'in')
    return render_template('roster.html', rows=rows, present=present, total=len(rows))


@app.route('/roster/toggle/<int:user_id>', methods=['POST'])
@login_required
def roster_toggle(user_id):
    if current_user.role not in ['admin', 'captain']:
        return jsonify(ok=False, error='Forbidden'), 403
    user = User.query.get_or_404(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    existing = CheckIn.query.filter_by(player_id=user_id, date=today).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        state = 'out'
        create_notification(user.id, f"✅ You were checked out today by {current_user.full_name}. See you next practice!")
    else:
        db.session.add(CheckIn(player_id=user_id))
        db.session.commit()
        state = 'in'
        create_notification(user.id, f"🥇 {current_user.full_name} checked you in. Let's get on court!")
    return jsonify(ok=True, state=state, name=user.full_name,
                   time=datetime.now().strftime('%I:%M %p') if state == 'in' else None)


@app.route('/api/roster')
@login_required
def api_roster():
    if current_user.role not in ['admin', 'captain']:
        return jsonify(ok=False), 403
    today = datetime.now().strftime('%Y-%m-%d')
    checkins = {c.player_id: c for c in CheckIn.query.filter_by(date=today).all()}
    data = [{
        'id': u.id, 'name': u.full_name, 'username': u.username, 'role': u.role,
        'status': 'in' if u.id in checkins else 'out',
        'time': checkins[u.id].check_in_time.strftime('%I:%M %p') if u.id in checkins else None,
    } for u in all_players()]
    return jsonify(players=data,
                   present=sum(1 for p in data if p['status'] == 'in'),
                   total=len(data))


@app.route('/api/on-court')
@login_required
def api_on_court():
    today = datetime.now().strftime('%Y-%m-%d')
    rows = (db.session.query(User.id, User.full_name)
            .join(CheckIn, CheckIn.player_id == User.id)
            .filter(CheckIn.date == today)
            .order_by(CheckIn.check_in_time).all())
    return jsonify(count=len(rows), on_court=[{'id': i, 'name': n} for i, n in rows])


@app.route('/admin/attendance/export')
@login_required
def admin_attendance_export():
    if current_user.role not in ['admin', 'captain']:
        return redirect(url_for('dashboard'))
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Player', 'Username', 'Date', 'Check-in Time'])
    for c in CheckIn.query.order_by(CheckIn.date.desc(), CheckIn.check_in_time.desc()).all():
        u = User.query.get(c.player_id)
        if u:
            writer.writerow([u.full_name, u.username, c.date,
                             c.check_in_time.strftime('%I:%M %p') if c.check_in_time else ''])
    out = io.BytesIO()
    out.write(si.getvalue().encode('utf-8'))
    out.seek(0)
    return send_file(out, mimetype='text/csv', as_attachment=True, download_name='badminton_attendance.csv')


# ============ USER MANAGEMENT ============

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin_users.html', users=User.query.order_by(User.id).all())

@app.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required
def admin_user_update(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    role = request.form.get('role')
    new_pass = request.form.get('password', '').strip()
    if role in ['admin', 'captain', 'player']:
        user.role = role
    if new_pass:
        if len(new_pass) < 6:
            flash('⚠️ Password must be at least 6 characters.', 'danger')
            return redirect(url_for('admin_users'))
        user.password_hash = generate_password_hash(new_pass, method='pbkdf2:sha256')
    db.session.commit()
    flash(f'✅ Updated {user.full_name}.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
def admin_user_delete(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    if user_id == current_user.id:
        flash('⛔ You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_users'))
    user = User.query.get_or_404(user_id)
    full_name = user.full_name
    User.query.filter_by(id=user_id).delete()
    db.session.commit()
    flash(f'🗑️ Removed {full_name}.', 'info')
    return redirect(url_for('admin_users'))

# ============ MATCH RESULTS + BRACKET ADVANCEMENT ============

@app.route('/admin/set-result/<int:match_id>', methods=['GET', 'POST'])
@login_required
def admin_set_result(match_id):
    if current_user.role not in ['admin', 'captain']:
        flash('⚠️ Admin or Captain access only!', 'danger')
        return redirect(url_for('dashboard'))
    match = Match.query.get_or_404(match_id)
    if request.method == 'POST':
        side = request.form.get('winner')
        score1 = int(request.form.get('score1', 0))
        score2 = int(request.form.get('score2', 0))
        if side not in ['team1', 'team2']:
            flash('Select the winning team.', 'danger')
            return redirect(url_for('admin_set_result', match_id=match_id))
        team1 = [match.team1_player1] + ([match.team1_player2] if match.team1_player2 else [])
        team2 = [match.team2_player1] + ([match.team2_player2] if match.team2_player2 else [])
        winners = team1 if side == 'team1' else team2
        match.winner = ' & '.join(winners)
        side_int = {'team1': 1, 'team2': 2}[side]
        match.status = 'completed'
        match.score_team1 = score1
        match.score_team2 = score2
        for name in winners:
            user = User.query.filter_by(full_name=name).first()
            if user:
                create_notification(user.id, f"🏆 You advanced in Round {match.bracket_round}! {match.winner} wins {score1}-{score2}.")
        advance_winner(match)
        db.session.commit()
        flash('✅ Result recorded & bracket advanced!', 'success')
        return redirect(url_for('brackets'))
    return render_template('admin_set_result.html', match=match)


def advance_winner(match):
    """Promote the winner of `match` into the next round, pairing with its sibling match."""
    round_matches = (Match.query
                     .filter_by(tournament_id=match.tournament_id, bracket_round=match.bracket_round)
                     .order_by(Match.id).all())
    if not round_matches:
        return
    idx = round_matches.index(match)
    sibling_idx = idx + 1 if idx % 2 == 0 else idx - 1
    if sibling_idx >= len(round_matches):
        return
    sibling = round_matches[sibling_idx]
    if not sibling.winner:
        return
    pairing = [match, sibling] if idx % 2 == 0 else [sibling, match]
    nxt = Match(
        match_date='TBD', match_time='TBD',
        team1_player1=split_winner(pairing[0].winner, 0),
        team1_player2=split_winner(pairing[0].winner, 1),
        team2_player1=split_winner(pairing[1].winner, 0),
        team2_player2=split_winner(pairing[1].winner, 1),
        bracket_round=match.bracket_round + 1,
        status='upcoming',
        tournament_id=match.tournament_id
    )
    db.session.add(nxt)
    for name in [nxt.team1_player1, nxt.team1_player2, nxt.team2_player1, nxt.team2_player2]:
        if name:
            user = User.query.filter_by(full_name=name).first()
            if user:
                create_notification(user.id, f"🏸 New match scheduled: {nxt.team1_player1} vs {nxt.team2_player1} (Round {nxt.bracket_round})")


def split_winner(winner, index):
    parts = [p.strip() for p in (winner or '').split('&')]
    return parts[index] if index < len(parts) else None

# ============ BEST PRACTICE TIME PUBLISH ============

@app.route('/admin/calendar/publish', methods=['POST'])
@login_required
def admin_publish_practice_pick():
    if current_user.role not in ['admin', 'captain']:
        return redirect(url_for('dashboard'))
    picks = best_practice_slots(2)
    if not picks:
        flash('No availability data yet — ask players to set their slots.', 'warning')
        return redirect(url_for('admin_calendar'))
    lines = [f"🏸 Best practice slots this week: {p['day']} at {p['slot']} ({p['count']}/{p['total']} players available)" for p in picks]
    ann = Announcement(
        title='📅 Recommended Practice Windows',
        content='\n'.join(lines),
        is_public=True, is_pinned=True
    )
    db.session.add(ann)
    db.session.commit()
    for u in User.query.all():
        create_notification(u.id, '📅 New pinned announcement: Recommended Practice Windows')
    flash('✅ Published as a pinned announcement!', 'success')
    return redirect(url_for('admin_calendar'))

# ============ DATA BACKUP ============

@app.route('/admin/backup')
@login_required
def admin_backup():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'team.db')
    if os.path.exists(source):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            src = sqlite3.connect(source)
            dst = sqlite3.connect(tmp.name)
            try:
                with dst:
                    src.backup(dst)
            finally:
                dst.close()
                src.close()
            tmp_path = tmp.name

        @after_this_request
        def rm_tmp(response):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return response

        return send_file(tmp_path, mimetype='application/octet-stream', as_attachment=True,
                         download_name=f"badminton_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
    flash('Database file not found.', 'danger')
    return redirect(url_for('admin_panel'))


if __name__ == '__main__':
    print("\n🚀 Starting NYIT Badminton Team Manager...")
    print("📍 Open http://localhost:5002 in your browser")
    print("👤 Admins: kabir / sadia (admin123) · Players: player123\n")
    app.run(debug=True, port=5002)