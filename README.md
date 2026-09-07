# 🏸 NYIT Badminton Team Manager

A full-featured team-management web app for the NYIT Badminton club: attendance,
match brackets, tournaments, performance ratings, leaderboards, weekly MVP voting,
a photo gallery, live roster management, and a premium PWA-style UI with dark mode.

---

## 1. Quick Start

```bash
git clone https://github.com/Sadia-F/Badminton-webapp.git
cd Badminton-webapp

python3 -m venv .venv
source .venv/bin/activate            # macOS/Linux
# .venv\Scripts\activate             # Windows

pip install -r requirements.txt

python app.py                        # starts at http://localhost:5002
```

The SQLite database (`instance/team.db`) is created automatically and seeded on the
first run. It is **git-ignored** — teammates on their own machine get a fresh DB.

### Rebuild the roster / wipe stats

```bash
python reset_roster.py               # wipes all stats, recreates the 12 real players
```

### Credentials

| Role    | Username            | Password   |
|---------|---------------------|------------|
| Admin   | `kabir`, `sadia`    | `admin123` |
| Player  | all 10 others (list below) | `player123` |

Players: `aamir, amrita, ayman, davinder, faizan, mathew, prabjot, saad, supriya, vraj`.

> 💡 **Admins are also athletes.** `all_players()` returns *everyone* (admins included),
> so admins check in, rate themselves, and appear on scores/leaderboards like everyone else.

---

## 2. Tech Stack

| Layer      | Tech |
|------------|------|
| Backend    | Flask 3.1.3, Python 3.14 (works with 3.10+) |
| ORM        | Flask-SQLAlchemy 3.1.1 / SQLAlchemy 2.0.52 |
| Auth       | Flask-Login + Werkzeug `pbkdf2:sha256` password hashes |
| Database   | SQLite (`instance/team.db`) — **no Alembic/migrations** |
| Frontend   | Jinja2 templates + custom CSS (design system v2), Font Awesome 6.4, Google Fonts |
| Charts     | Chart.js (radar chart on player profiles) |
| PWA        | `static/manifest.json` + `static/sw.js` service worker |
| Email      | Optional SMTP via env vars (reminders on notifications) |
| Tests      | `unittest` (30 tests in `test_app.py`) |

---

## 3. What the App Does (Feature Tour)

### For players
- **Dashboard** — today's check-in status, live "On Court" counter, attendance streak 🔥,
  weekly MVP, upcoming matches, quick access to player tools.
- **Check-in** — one tap marks you present for today; checking in builds your streak.
- **Availability** — click a 12-hour × 7-day grid (12pm–11pm) toggling your available slots;
  feeds the admin's heatmap and "best practice time" suggestions.
- **Matches & Scores** — see fixtures/results, log your own match scoreline.
- **Performance** — self-rate 5 metrics (smash, net play, footwork, consistency, shot
  variety) on a 1–10 scale → powers the skill radar + leaderboard rating.
- **Brackets** — visual tournament bracket tracker.
- **Leaderboard** — ranked by wins → win rate → skill rating; shows check-in counts & streaks.
- **Weekly MVP** — vote for one teammate per week; live tally + past-week history.
- **Announcements / Schedule / Achievements / Gallery** — club content.
- **Profile** — upload a profile photo (replaces the monogram avatar everywhere), see
  career win rate, skill radar, achievements, streak, and on/off-court status.
- **Notifications** — bell dropdown; marking unread clears and (optionally) emails.

### For admins & captains (staff)
- **Live Roster** (`/roster`) — every member as a card with name + live On/Off Court
  status + check-in time; one-click check in/out per player; search + filters;
  auto-refreshes every 15s; CSV export of all attendance.
- **Attendance** — per-date attendance records + per-player stats.
- **Bulk Check-in** — mark many players present at once.
- **Availability Map** — heatmap of team availability + auto-computed top practice windows
  with a one-click "Publish to Team" (creates a pinned announcement + notifies everyone).
- **Match Results** — record a winner + scores; the winner is **auto-advanced** into the
  next bracket round (with a free-slot auto-pairing).
- **Roster/player tools** — evaluate players officially, create bracket slots,
  auto-seed tournaments from performance ratings.
- **Gallery** — upload team photos (also visible to everyone on the public gallery).

### For admins only
- **Admin Panel** — quick actions hub.
- **Users** — change roles (admin/captain/player), reset passwords, remove players.
- **Content admin** — announcements, practice schedule, achievements, delete gallery photos.
- **Backup** — one-click download of a full `.db` backup.

---

## 4. Directory Layout

```
Badminton-webapp/
├── app.py                  # ENTIRE backend + routes + models + seed (single file!)
├── reset_roster.py         # wipe stats + rebuild the 12-player roster
├── test_app.py             # 30 unit tests (temp DB, never touches real data)
├── requirements.txt
├── instance/team.db        # live SQLite DB (git-ignored)
├── static/
│   ├── style.css           # premium design system v2 + dark mode
│   ├── sw.js               # service worker (bump CACHE_NAME after CSS changes!)
│   ├── manifest.json       # PWA manifest
│   └── uploads/            # gallery photos + avatars (git-ignored)
└── templates/              # Jinja2 templates
    ├── base.html           # shell: sidebar + topbar, notifs, theme toggle, toasts
    ├── home.html, login.html, register.html   # standalone guest pages
    ├── dashboard.html, roster.html, profile.html, availability.html, ...
    └── admin_*.html        # staff/admin pages
```

---

## 5. Data Model

All defined in `app.py` (SQLAlchemy models, ~lines 32–158). New tables are created
automatically on app start via `db.create_all()`.

| Model            | Key fields |
|------------------|-----------|
| `User`           | `username` (unique), `email` (unique), `password_hash`, `full_name`, `role` (`player`/`captain`/`admin`), `player_image` |
| `Announcement`   | `title`, `content`, `date_posted`, `is_public`, `is_pinned` |
| `Tournament`     | `name`, `start_date`, `end_date`, `is_active` + `matches` |
| `Match`          | `match_date`, `match_time`, `team1_player1/2`, `team2_player1/2`, `bracket_round`, `winner`, `status` (`upcoming`/`completed`), `score_team1/2`, `tournament_id` |
| `Performance`    | `player_id`, `match_id`, `rating_type` (`self`/`admin`), 5 metric ints (0–10), `comments` |
| `PracticeSchedule` | `day`, `start_time`, `end_time`, `location`, `is_active` |
| `Achievement`    | `title`, `description`, `date_achieved`, `player_id` |
| `Availability`   | `player_id`, `day_of_week` (0=Mon…6=Sun), `time_slot` (`'6pm'` etc.), `is_available` |
| `CheckIn`        | `player_id`, `check_in_time` (UTC timestamp), `date` (string `YYYY-MM-DD`) |
| `Score`          | `match_id`, `player_id`, `player_score`, `opponent_score`, `is_winner` |
| `Notification`   | `user_id`, `message`, `timestamp`, `is_read` |
| `MvpNomination`  | `week_start` (Monday `YYYY-MM-DD`), `player_id`, `nominated_by` — unique (week, player) |
| `MvpVote`        | `week_start`, `player_id`, `user_id` — unique (week, user) |
| `GalleryImage`   | `filename`, `caption`, `uploaded_by`, `uploaded_at` |

> ⚠️ **No migrations.** `create_all()` only *adds missing tables*; it will **not** alter
> existing tables. Adding a column to a live table requires a manual step (see §10).

---

## 6. Routes / Endpoints

`@login_required` routes redirect to `/login` when logged out.

### Public
| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Home page (guest marketing page) |
| `/login` | GET/POST | Login (rate-limited, see §7) |
| `/register` | GET/POST | Self-registration (username `3–20` alnum/underscore, valid email, password ≥ 6) |
| `/leaderboard` | GET | Team rankings |
| `/mvp` | GET | Weekly MVP votes + past winners |
| `/gallery` | GET | Public photo gallery |
| `/logout` | GET | Log out |

### Any logged-in user
| Route | Method | Description |
|-------|--------|-------------|
| `/dashboard` | GET | Personal dashboard |
| `/check-in` | POST | Check yourself in for today |
| `/profile/<username>` | GET/POST | View profile; POST (own profile only) uploads a photo |
| `/availability` | GET/POST | Toggle an availability slot |
| `/availability/delete/<id>` | GET | Remove own slot row |
| `/matches` | GET | Fixtures & results (staff see "Record Result" buttons) |
| `/update-score` | GET/POST | Log a match scoreline |
| `/performance` | GET/POST | Self-assessment ratings |
| `/brackets` | GET | Tournament brackets |
| `/announcements` | GET | Announcements list |
| `/schedule` | GET | Practice schedule |
| `/achievements` | GET | Team achievements |
| `/notifications/read/<id>` | GET | Mark a notification read |
| `/api/on-court` | GET | JSON: `{count, on_court:[{id,name}]}` — powers live badges |
| `/schedule/export` | GET | iCalendar export of practice schedule |

### Staff (admin **and** captain)
| Route | Method | Description |
|-------|--------|-------------|
| `/roster` | GET | Live roster desk |
| `/roster/toggle/<user_id>` | POST* | Check a player in/out (returns JSON state) |
| `/api/roster` | GET | JSON roster with live status — powers polling |
| `/admin` | GET | Dashboard-level stats (staff) |
| `/admin/bulk-checkin` | GET/POST | Mass check-in |
| `/admin/check-players` | POST* | Check-in selected players (from panel) |
| `/admin/attendance` | GET | Attendance by date |
| `/admin/attendance/export` | GET | Download CSV |
| `/admin/player-stats/<id>` | GET | Per-player stats page |
| `/admin/calendar` | GET | Availability heatmap + recommendations |
| `/admin/calendar/publish` | POST* | Publish recommended slots as pinned announcement |
| `/admin/rate-player` | GET/POST | Official performance evaluation |
| `/admin/create-brackets` | GET/POST | Manual bracket builder |
| `/admin/set-result/<match_id>` | GET/POST | Record result + auto-advance winner |
| `/admin/gallery` | GET/POST | Upload team photos (staff) |

### Admin only
| Route | Method | Description |
|-------|--------|-------------|
| `/admin/users` | GET | User management |
| `/admin/users/update/<id>` | POST* | Change role / reset password |
| `/admin/users/delete/<id>` | POST* | Remove user |
| `/admin/announcements` + `/admin/announcements/delete/<id>` | GET/POST* | Create/delete announcements |
| `/admin/schedule` + `/admin/schedule/delete/<id>` | GET/POST* | Manage practice schedule |
| `/admin/achievements` + `/admin/achievements/delete/<id>` | GET/POST* | Add/delete achievements |
| `/admin/gallery/delete/<id>` | GET/POST* | Delete a gallery photo |
| `/admin/auto-seed` | GET/POST* | Auto-seed a bracket from ratings |
| `/admin/tournaments` + `/admin/tournaments/delete/<id>` | GET/POST* | Tournament management |
| `/admin/backup` | GET | Download full DB backup |

\* `POST` routes require a CSRF token (see §7).

---

## 7. Security Model (READ BEFORE CODING)

### CSRF — enforced app-wide
`app.before_request(enforce_csrf)` aborts with **400** on **any POST without a valid
token**. Token validation:

```python
token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
if not token or token != session.get('csrf_token'): abort(400)
```

- Templates get a token via the `csrf_token()` context-processor function.
- **Every HTML `<form method="POST">` must contain the hidden field:**
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- **Every `fetch()` POST must pass the header** `X-CSRF-Token: <token>` (see
  `templates/roster.html` for the pattern — it reads the token from a hidden input).
- Missing tokens = instant 400s. This is the #1 mistake a new contributor can make.

### Login rate limiting
In-memory `login_attempts` dict keyed by `IP:username`. After **5 failures in 15 min**
the combo is locked (resets when the server restarts).

### Secret key
`SECRET_KEY` env var, else the bundled dev fallback. Use a strong value in production.

### File uploads
`MAX_CONTENT_LENGTH = 12 MB`; only `png/jpg/jpeg/gif/webp` accepted
(`allowed_image()`). New files are given random hex names (`secrets.token_hex(4)`).

### Never commit
- `instance/*.db` (live data — emails + password hashes) → git-ignored.
- `static/uploads/` (user photos) → git-ignored.
- `.venv/`, `__pycache__`, `*.backup*`.

---

## 8. Key Business Logic (helpers in `app.py`)

| Helper | What it does |
|--------|--------------|
| `all_players()` | `User.query.order_by(User.role, User.full_name)` — includes admins. Use this instead of `role != 'admin'` filters. |
| `attendance_streak(player_id)` | Consecutive check-in days ending today or yesterday. |
| `player_rating(user_id)` | Average of the 5 performance metrics across all evaluations (0–5 scale). |
| `team_leaderboard()` | Rows sorted by wins → win-rate → rating; supplies `/leaderboard`. |
| `current_week_start()` | Monday of the current week as `YYYY-MM-DD` (MVP week key). |
| `best_practice_slots(n=2)` | Top (day, slot) pairs by available-player count. |
| `advance_winner(match)` / `split_winner(winner, idx)` | After a result, pair winning teams from sibling matches into the next round. |
| `create_notification(user_id, msg)` | Inserts a notification AND emails the user if SMTP is configured. Commits itself. |
| `inject_notifications()` | Template context: `unread_notifs` + `recent_notifs` for the bell. |
| `inject_globals()` | Adds `active(...)` (nav highlighting), `csrf_token()`, `all_players`, `avatar_url(...)` to every template. |

---

## 9. Frontend Conventions (match the existing style!)

### Template shell
- App pages `{% extends "base.html" %}` and fill `{% block content %}` (optional
  `{% block head %}`, `{% block scripts %}`).
- Guest pages (`home.html`, `login.html`, `register.html`) are **standalone** — full
  `<html>` with the `login-wrapper` layout, no sidebar.
- `base.html` provides: sidebar nav (Team Hub / My Zone / Management groups), topbar,
  notification dropdown, **dark-mode toggle**, **live "on court" badge** (staff),
  **toast system** (`window.toast(msg, type)` + `window.playBlip()`), and the SW hook.

### Navigation highlighting
Use the endpoint helper, e.g.:
```jinja
<a href="/roster" class="{{ active('roster_page') }}">...</a>
```

### Design tokens (CSS variables in `:root`)
`--nyit-blue #0033A0`, `--nyit-gold #FFD700`, `--primary`, `--primary-2`, `--accent`,
`--success #16C784`, `--danger`, `--bg-main`, `--bg-card`, `--bg-soft`, `--text-main`,
`--text-muted`, `--border-color`, `--radius-sm/md/lg/xl`, `--shadow-md/lg`, `--transition`.

**Dark mode is driven by `[data-theme="dark"]`** overriding those variables +
targeted tweak rules. Always add a dark-mode override when you add a component with
hard-coded light backgrounds (see `[data-theme="dark"] .slot-unavailable` as a model).
The toggle writes `localStorage('badminton-theme')` and a head script applies it before
paint to avoid a flash.

### Reusable components
`.card`, `.dashboard-grid` + `.dashboard-card` (+`.admin-section`), `.stats-row` +
`.stat-card` (`.blue/.green/.gold/.red/.lime`), `.page-head` + `.eyebrow` + `.subtitle`,
`.role-badge` (`.admin`/`.player`), `.pill`, `.btn-primary`, `.btn-ghost`, `.action-grid` +
`.action-btn` (`.act-blue/.green/.gold/.red/.indigo/.cyan`), `.highlight-row` +
`.highlight-card`, `.roster-grid` + `.roster-card`, `.lb-table` + `.medal/.lb-rank`,
`.gallery-grid` + `.gallery-item`, `.flash`, `.avatar`/`.top-avatar`/`.profile-image`
(photo-capable via `avatar_url(user)`), `.toast-stack`, `.on-court-badge`, `.pulse-dot`.

### Forms
Every POST form needs the CSRF hidden input (`&sect;7`). Use `.form-group` + `<label>` +
`input/select/textarea` for consistent styling.

### PWA / service worker
`static/sw.js` uses **cache-first** for `/`, `style.css`, and the FontAwesome CDN.
**After any big CSS/template change, bump `CACHE_NAME`** (currently `badminton-v4`) or
users will keep seeing stale styles.

---

## 10. Gotchas & Things Kabir Must Know

1. **No migrations.** Adding a *column* to an existing table needs a manual migration.
   Safe pattern: add a migration `ALTER TABLE ... ADD COLUMN` inside the
   `with app.app_context():` block guarded by a helper that checks existing columns
   (or run a one-off via `sqlite3 instance/team.db`). New *tables* are safe (auto-created).
2. **CSRF on every POST** — the #1 trap. Run a quick manual POST test after any form work.
3. **`CheckIn.date` is a string** (`YYYY-MM-DD`), `check_in_time` is a UTC datetime.
   Keep both consistent when querying "today".
4. **Airport-style endpoint names matter** — `active('endpoint')`, `url_for('...')` and
   the templates must match the Python function names exactly.
5. **Admins are players too** — filter semantics: use `all_players()`; don't exclude
   `role='admin'` from team-wide pages.
6. **Rate limiter is in-memory** — restarting the server clears failed-login locks.
7. **`debug=True`** in `app.run()` = auto-reloader; the process is a dev server only,
   not production-safe (use `waitress`/`gunicorn` + a reverse proxy in production).
8. **Service worker caching** — bump `CACHE_NAME` in `sw.js` on visual changes.
9. **`create_notification()` commits** — don't wrap it in an uncommitted transaction
   expecting to roll back its change.
10. **Uploads** — photo/gallery files land in `static/uploads/`; the DB stores only the
    filename. Avatar files follow `avatar_<user_id>_<hex>.<ext>`.
11. **Don't commit the DB** — keep `instance/*.db` and `static/uploads/` out of git.
12. **Run the tests after changes** — see §11.

---

## 11. Testing

```bash
.venv/bin/python -m unittest test_app -v      # 30 tests
```

- Tests set `DATABASE_URL` to a **temp directory** *before* importing `app`, so the real
  `instance/team.db` is never touched.
- `test_app.py` covers: auth (login/register/rate-limit/CSRF), core pages, leaderboard,
  MVP voting, gallery upload, admin user management, backup integrity, bracket
  auto-advancement, roster toggle/APIs, CSV export, and profile photo uploads.
- **Add a test for every new route/behavior** — it's expected project practice.

---

## 12. Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Override the SQLite path (used by tests). Default `sqlite:///team.db`. |
| `SECRET_KEY` | Session signing key. Overrides the dev fallback. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Optional email reminders on notifications. Email is silently skipped if unset. |

---

## 13. Checklist for Adding a New Feature

- [ ] Add/modify model in `app.py`. For new columns on existing tables, run a migration.
- [ ] Add the route (observe access level: public / any user / staff / admin).
- [ ] Guard the route (`@login_required` + `role` check consistent with the matrix in §6).
- [ ] If it's a POST route, ensure the template form has `{{ csrf_token() }}` (or the
      `X-CSRF-Token` header for fetch).
- [ ] Create/update the template: `{% extends "base.html" %}`, use design tokens,
      add a dark-mode override if needed, add a sidebar link with `active('endpoint')`.
- [ ] If the sidebar changes for staff, gate with `current_user.role in ['admin','captain']`
      (or `== 'admin'` for admin-only links) like the existing Management section.
- [ ] Add to `/roster` or JSON APIs only if it changes live status data.
- [ ] Bump `CACHE_NAME` in `sw.js` if you changed styling.
- [ ] Write a `unittest` in `test_app.py`.
- [ ] Run: `.venv/bin/python -m unittest test_app` → all green.
- [ ] Verify live at http://localhost:5002 (both an admin and a player account).