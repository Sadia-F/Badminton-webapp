"""One-time reset: wipe all stats/activity, then build the real NYIT Badminton roster.

Run with:  .venv/bin/python reset_roster.py
"""
from werkzeug.security import generate_password_hash

from app import app, db, User
from app import (Score, Performance, CheckIn, Notification, Match,
                 MvpVote, MvpNomination, Availability, Achievement)

ROSTER = [
    ("Aamir",    "aamir",    "player123"),
    ("Amrita",   "amrita",   "player123"),
    ("Ayman",    "ayman",    "player123"),
    ("Davinder", "davinder", "player123"),
    ("Faizan",   "faizan",   "player123"),
    ("Kabir",    "kabir",    "admin123"),
    ("Sadia",    "sadia",    "admin123"),
    ("Mathew",   "mathew",   "player123"),
    ("Prabjot",  "prabjot",  "player123"),
    ("Saad",     "saad",     "player123"),
    ("Supriya",  "supriya",  "player123"),
    ("Vraj",     "vraj",     "player123"),
]
ADMINS = {"kabir", "sadia"}


def main():
    with app.app_context():
        # 1) wipe all stats / activity (keep content: announcements, schedule,
        #    tournaments, gallery photos)
        for model in (Availability, Score, Performance, CheckIn, Notification,
                      MvpVote, MvpNomination, Achievement, Match, User):
            db.session.execute(db.delete(model))
        db.session.commit()

        # 2) build the real roster
        for full_name, username, password in ROSTER:
            db.session.add(User(
                username=username,
                email=f"{username}@nyit.edu",
                password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                full_name=full_name,
                role="admin" if username in ADMINS else "player",
            ))
        db.session.commit()

        count = db.session.query(User).count()
        admins = [u.username for u in User.query.filter_by(role="admin").all()]
        print(f"✅ Stats wiped. Roster rebuilt: {count} players.")
        print(f"   Admins: {', '.join(admins)} (password: admin123)")
        print("   Players (password: player123): "
              + ", ".join(sorted(u.username for u in User.query.filter_by(role='player').all())))


if __name__ == "__main__":
    main()