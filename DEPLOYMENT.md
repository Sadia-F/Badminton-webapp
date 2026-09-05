# 🚀 Deployment Guide for NYIT Badminton Manager

Since this application uses **Python (Flask)** and a **Database (SQLite/PostgreSQL)**, it cannot be hosted on GitHub Pages (which only supports static HTML/CSS/JS). 

To make your website live and accessible to your team, follow these steps to host it on **Render** (Free Tier).

## 1. Prepare your project for Deployment

### Add a `requirements.txt` file
Render needs to know which libraries to install. Run this command in your terminal:
```bash
pip freeze > requirements.txt
```

### Add a `gunicorn` server
Production servers don't use `app.run()`. Install `gunicorn`:
```bash
pip install gunicorn
```
Then update your `requirements.txt` again:
```bash
pip freeze > requirements.txt
```

## 2. Host on Render.com

1. **Create an account** at [render.com](https://render.com) and connect your GitHub account.
2. **Create a new "Web Service"**.
3. **Select your repository**: `Sadia-F/Badminton-webapp`.
4. **Configure the service**:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. **Environment Variables**:
   - Add `PYTHON_VERSION` = `3.11.0` (or your local version).
6. **Click "Deploy Web Service"**.

## 3. Important Note on the Database
Your current app uses `sqlite` (`team.db`). 
- **On Render Free Tier:** The filesystem is "ephemeral," meaning your database will be reset every time the server restarts.
- **The Solution:** Use a **Render PostgreSQL** database (available on the free tier). 
  - Create a PostgreSQL database on Render.
  - Copy the **Internal Database URL**.
  - In Render's Web Service settings, add an Environment Variable: `DATABASE_URL` = `[Your PostgreSQL URL]`.
  - Update `app.py` to use this variable: `app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///team.db')`.


## 4. Access your site
Once deployed, Render will give you a URL (e.g., `badminton-nyit.onrender.com`). Share this with your players!
