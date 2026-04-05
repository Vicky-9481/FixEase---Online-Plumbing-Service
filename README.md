# Fix Ease

This project is a Flask web app backed by MySQL.

## 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure MySQL

Copy `.env.example` to `.env` and update the MySQL password if needed.

```powershell
Copy-Item .env.example .env
```

Default database details:

- Host: `127.0.0.1`
- Port: `3306`
- Database: `plumbing_service`
- User: `root`

The app will create the database and tables automatically when it starts, as long as MySQL Server is running and the username/password are correct.

## 3. Run the app

```powershell
python app.py
```

Open `http://127.0.0.1:5000`

## 4. First use

- Register a user account.
- If you want an admin account, tick `Grant Admin Rights` during registration.
- Log in as the admin and add plumbers.
- Log in as a normal user to request plumbing service.
