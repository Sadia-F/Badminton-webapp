from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///team.db'
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
    is_admin = db.Column(db.Boolean, default=False)
    player_image = db.Column(db.String(200), default='default.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)

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
    date = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='available')
    player = db.relationship('User', backref='availabilities')

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    date = db.Column(db.String(20), default=datetime.now().strftime('%Y-%m-%d'))
    player = db.relationship('User', backref='check_ins')

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

class Performance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    rating = db.Column(db.Float)
    technique = db.Column(db.Integer)
    speed = db.Column(db.Integer)
    stamina = db.Column(db.Integer)
    teamwork = db.Column(db.Integer)
    comments = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    player = db.relationship('User', backref='performances')
    match = db.relationship('Match', backref='performances')

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    player_score = db.Column(db.Integer)
    opponent_score = db.Column(db.Integer)
    is_winner = db.Column(db.Boolean, default=False)
    match = db.relationship('Match', backref='scores')
    player = db.relationship('User', backref='scores')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============ CREATE DATABASE ============

with app.app_context():
    db.create_all()
    
    if not User.query.first():
        admin = User(
            username='admin',
            email='admin@nyit.edu',
            password_hash=generate_password_hash('admin123'),
            full_name='Admin User',
            is_admin=True
        )
        db.session.add(admin)
        
        players = [
            User(username='john', email='john@nyit.edu', password_hash=generate_password_hash('player123'), full_name='John Doe'),
            User(username='jane', email='jane@nyit.edu', password_hash=generate_password_hash('player123'), full_name='Jane Smith'),
            User(username='mike', email='mike@nyit.edu', password_hash=generate_password_hash('player123'), full_name='Mike Johnson'),
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

# ============ PUBLIC ROUTES ============

@app.route('/')
def home():
    announcements = Announcement.query.filter_by(is_public=True).order_by(Announcement.date_posted.desc()).limit(3).all()
    return render_template('home.html', announcements=announcements)

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
    players = User.query.filter_by(is_admin=False).all()
    return render_template('team.html', players=players)

# ============ AUTH ROUTES ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('✅ Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('👋 Logged out successfully', 'info')
    return redirect(url_for('home'))

# ============ DASHBOARD ============

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().strftime('%Y-%m-%d')
    checkin_status = CheckIn.query.filter_by(player_id=current_user.id, date=today).first()
    matches = Match.query.order_by(Match.match_date).limit(5).all()
    performances = Performance.query.filter_by(player_id=current_user.id).order_by(Performance.date.desc()).limit(5).all()
    today_checkins = CheckIn.query.filter_by(date=today).count()
    total_players = User.query.filter_by(is_admin=False).count()
    return render_template('dashboard.html', 
                         checkin_status=bool(checkin_status),
                         matches=matches,
                         performances=performances,
                         today_checkins=today_checkins,
                         total_players=total_players,
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

# ============ AVAILABILITY ============

@app.route('/availability', methods=['GET', 'POST'])
@login_required
def availability():
    if request.method == 'POST':
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        status = request.form.get('status', 'available')
        avail = Availability(
            player_id=current_user.id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status=status
        )
        db.session.add(avail)
        db.session.commit()
        flash('✅ Availability updated!', 'success')
        return redirect(url_for('availability'))
    availabilities = Availability.query.filter_by(player_id=current_user.id).order_by(Availability.date.desc()).all()
    return render_template('availability.html', availabilities=availabilities)

@app.route('/availability/delete/<int:id>')
@login_required
def delete_availability(id):
    avail = Availability.query.get_or_404(id)
    if avail.player_id == current_user.id or current_user.is_admin:
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
        rating = float(request.form.get('rating'))
        technique = int(request.form.get('technique'))
        speed = int(request.form.get('speed'))
        stamina = int(request.form.get('stamina'))
        teamwork = int(request.form.get('teamwork'))
        comments = request.form.get('comments', '')
        perf = Performance(
            player_id=current_user.id,
            match_id=int(match_id) if match_id else None,
            rating=rating,
            technique=technique,
            speed=speed,
            stamina=stamina,
            teamwork=teamwork,
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

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))
    players = User.query.all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    today = datetime.now().strftime('%Y-%m-%d')
    checkins = CheckIn.query.filter_by(date=today).all()
    return render_template('admin.html', players=players, announcements=announcements, checkins=checkins, today=today)

@app.route('/admin/check-players', methods=['POST'])
@login_required
def admin_check_players():
    if not current_user.is_admin:
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
    if not current_user.is_admin:
        flash('⚠️ Admin access only!', 'danger')
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
    if not current_user.is_admin:
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))
    player = User.query.get_or_404(player_id)
    performances = Performance.query.filter_by(player_id=player_id).all()
    checkins = CheckIn.query.filter_by(player_id=player_id).all()
    scores = Score.query.filter_by(player_id=player_id).all()
    avg_rating = sum(p.rating for p in performances) / len(performances) if performances else 0
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
    if not current_user.is_admin:
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))
    availabilities = Availability.query.all()
    date_availability = {}
    for av in availabilities:
        if av.date not in date_availability:
            date_availability[av.date] = {'available': 0, 'total': 0}
        date_availability[av.date]['total'] += 1
        if av.status == 'available':
            date_availability[av.date]['available'] += 1
    return render_template('admin_calendar.html', date_availability=date_availability)

@app.route('/admin/create-brackets', methods=['GET', 'POST'])
@login_required
def admin_create_brackets():
    if not current_user.is_admin:
        flash('⚠️ Admin access only!', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        match_date = request.form.get('match_date')
        match_time = request.form.get('match_time')
        team1_p1 = request.form.get('team1_p1')
        team1_p2 = request.form.get('team1_p2')
        team2_p1 = request.form.get('team2_p1')
        team2_p2 = request.form.get('team2_p2')
        bracket_round = int(request.form.get('bracket_round', 1))
        match = Match(
            match_date=match_date,
            match_time=match_time,
            team1_player1=team1_p1,
            team1_player2=team1_p2,
            team2_player1=team2_p1,
            team2_player2=team2_p2,
            bracket_round=bracket_round,
            status='upcoming'
        )
        db.session.add(match)
        db.session.commit()
        flash('🏆 Bracket created!', 'success')
        return redirect(url_for('matches'))
    players = User.query.filter_by(is_admin=False).all()
    return render_template('admin_create_brackets.html', players=players)

if __name__ == '__main__':
    print("\n🚀 Starting NYIT Badminton Team Manager...")
    print("📍 Open http://localhost:5002 in your browser")
    print("👤 Login: admin / admin123\n")
    app.run(debug=True, port=5002)