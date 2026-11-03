# Faculty Evaluation

Django 5.2 LTS app on Python 3.13, served by Waitress on Windows (no Docker).

```
browser ──► IIS (port 80/443, URL Rewrite + ARR) ──► Waitress serve.py (127.0.0.1:8000) ──► PostgreSQL
```

IIS sits in front because Waitress on Windows can hold at most ~500 open connections
(Python's `select()` limit); IIS holds the browser connections and forwards requests over a few.
WhiteNoise serves `/static/` from inside Django, so IIS only needs to proxy.
PDF reports are drawn with ReportLab (pure Python), so there are no system libraries to install.

## Who sees what

| Role | Signs in to | Can do |
|---|---|---|
| Student | My classes | Evaluate each enrolled class once while its semester is active |
| Faculty | My results | See their own classes' results and comments (always anonymous) and download PDFs, once staff release results in Settings |
| Staff | Dashboard | Manage students, faculty, classes and enrollment, subjects and other school records, the questionnaire, results and PDFs |
| Administrator (superuser) | Dashboard | Everything staff can do, plus add or remove staff accounts |

Students sign in with their school ID number (they never pick a username); faculty, staff and
administrators sign in with their username. New ID numbers must be unique; older data has some shared
ones, which the dashboard flags and **Students → Status: Duplicate ID numbers** lists for cleanup.
A person who is both staff and faculty signs in to the staff dashboard.
Records that are still in use (a subject with classes, a student with submitted evaluations)
can't be deleted; the delete page says what is using them.

## Project layout

| Path | What it is |
|---|---|
| `core/` | Django project (settings, urls, wsgi) |
| `evaluation/` | The app: models, views (`views/` split by role), templates, migrations |
| `evaluation/services.py` | Scoring and result calculations shared by pages and PDFs |
| `evaluation/reports.py` | PDF reports (ReportLab) |
| `static/` | Source static files: `css/app.css`, `js/app.js`, fonts, htmx, logo |
| `serve.py` | Production entry point (Waitress) |
| `.env.example` | Every setting the app reads; copy to `.env` |
| `deploy/install-service.ps1` | Registers `serve.py` as a Windows service (NSSM) |
| `deploy/web.config` | IIS reverse-proxy config |

Generated, not edited: `.venv/`, `staticfiles/` (from `collectstatic`), `logs/`.

## Installation

These steps set the app up on a development machine or a server. For a production server, follow
them up to step 5 and then continue with [Deploying to Windows Server 2019](#deploying-to-windows-server-2019).

### Requirements

- **Python 3.13** (64-bit). On Windows, tick "Add python.exe to PATH" and "py launcher" in the installer.
- **PostgreSQL 17**. Note the `postgres` password and the port (5432 unless you changed it).
- **Git**

Nothing else is needed: PDFs are drawn in pure Python, and fonts and htmx ship in `static/`.

### 1. Get the code

```powershell
git clone https://github.com/0jieE/cdk_faculty_evaluation.git
cd cdk_faculty_evaluation
```

### 2. Create the virtual environment

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

On Linux or macOS use `python3.13 -m venv .venv` and `.venv/bin/python` in place of `.venv\Scripts\python`.

### 3. Create the database

```powershell
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres -p 5432 fe_database
```

Or create an empty database named `fe_database` in pgAdmin. To start from an existing backup instead,
restore it now (see [Database](#3-database) under deployment).

### 4. Configure `.env`

```powershell
copy .env.example .env
notepad .env
```

Set at least:

| Setting | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A new random key. Generate one with `.venv\Scripts\python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"` |
| `DJANGO_DEBUG` | `True` on a development machine, `False` on a server |
| `DB_PASSWORD`, `DB_PORT` | Your PostgreSQL password and port |

`.env` holds passwords, so it is ignored by Git. Never commit it.

### 5. Create the tables and the first administrator

```powershell
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser
.venv\Scripts\python manage.py collectstatic --noinput
```

`createsuperuser` asks for a username and password. That account signs in to the staff dashboard
and can add the other staff accounts.

### 6. Run it

```powershell
.venv\Scripts\python manage.py runserver     # development server, reloads on code changes
.venv\Scripts\python serve.py                # or: the production server (Waitress)
```

Open http://127.0.0.1:8000 and sign in with the superuser.

With `DJANGO_DEBUG=False`, static files come from `staticfiles/`: after changing CSS or JS, run
`collectstatic` again and restart `serve.py`.

### 7. Set up the school data

A new database is empty. Sign in as the administrator and fill it in this order, since each step
uses the ones before it:

1. **School years** and **Semesters**. Mark the current semester active; students can only evaluate in the active semester.
2. **Departments**, **Programs**, **Year levels** and **Sections**.
3. **Questionnaire**: add the statements for both parts (inventory and appraisal). Students can't submit until both have questions.
4. **Subjects** and **Faculty**. Add **Staff accounts** if other people will manage the system.
5. **Students**: staff add them, or students create their own account from the sign-in page with their ID number.
6. **Classes**: add each class for the semester and enroll its students.
7. **Settings**: release results when faculty should see their evaluations.

The dashboard's **Needs attention** card lists anything still missing.

## Deploying to Windows Server 2019

### 1. Install prerequisites

- **Python 3.13** (64-bit) from python.org - tick "Add python.exe to PATH" and "py launcher".
- **PostgreSQL 17** - note the `postgres` password and port (default 5432).
- **IIS** with the **URL Rewrite** and **Application Request Routing (ARR) 3.0** modules
  (Server Manager → Add Roles → Web Server (IIS); the two modules are free downloads from iis.net).
- **NSSM** (https://nssm.cc/download) - unzip, e.g. to `C:\tools\nssm`.

### 2. Get the app and create the venv

```powershell
git clone https://github.com/0jieE/cdk_faculty_evaluation.git C:\apps\faculty_evaluation
cd C:\apps\faculty_evaluation
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In `.env` set at least: a new `DJANGO_SECRET_KEY` (the command to generate one is in the file),
`DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` with the server's
name or IP, and the `DB_*` values.

### 3. Database

Create the database and either restore an existing backup or start fresh:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres fe_database
# restore a dump made with pg_dump --no-owner --no-privileges:
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d fe_database -f fe_database.sql
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser    # skip if the restored backup already has an administrator
.venv\Scripts\python manage.py collectstatic --noinput
.venv\Scripts\python manage.py check --deploy
```

### 4. Run Waitress as a service

From an **elevated** PowerShell in the project folder:

```powershell
.\deploy\install-service.ps1 -Nssm C:\tools\nssm\win64\nssm.exe -DependsOn postgresql-x64-17
```

The service starts at boot and restarts if it exits. Logs: `logs\waitress.log`.
After changing code or `.env`: `Restart-Service FacultyEvaluation`.

Check it locally on the server: http://127.0.0.1:8000

### 5. IIS reverse proxy

From an **elevated** PowerShell:

```powershell
$appcmd = "$env:windir\system32\inetsrv\appcmd.exe"
# Turn on ARR proxying; don't append the client port to X-Forwarded-For
& $appcmd set config -section:system.webServer/proxy /enabled:"True" /includePortInXForwardedFor:"False" /commit:apphost
# Allow the rewrite rules to set the forwarded headers
& $appcmd set config -section:system.webServer/rewrite/allowedServerVariables /+"[name='HTTP_X_FORWARDED_PROTO']" /commit:apphost
& $appcmd set config -section:system.webServer/rewrite/allowedServerVariables /+"[name='HTTP_X_FORWARDED_HOST']" /commit:apphost

New-Item -ItemType Directory -Force C:\inetpub\faculty_evaluation | Out-Null
Copy-Item .\deploy\web.config C:\inetpub\faculty_evaluation\
```

In IIS Manager, point the site (e.g. *Default Web Site*) at `C:\inetpub\faculty_evaluation`,
add your bindings (HTTP 80, and HTTPS 443 with a certificate), and open the ports in Windows Firewall.

For HTTPS: uncomment the redirect rule in `web.config`, set `DJANGO_HTTPS=True`, use `https://`
origins in `DJANGO_CSRF_TRUSTED_ORIGINS`, and restart the service.

### Capacity notes (from load testing)

With this configuration (8 threads, DB connection reuse) one Waitress process handled ~100-150
students working at the same time with sub-second responses, ~60 requests/s at peak. Logins are the
most expensive request (~0.3 s CPU each, by design of password hashing), so if the whole school
must evaluate at once, have classes start a minute or two apart. PDF generation also runs inside
the same process, so large report batches are best run outside peak evaluation hours.

Keep `WAITRESS_CONNECTION_LIMIT` at or below 500: above that, Waitress on Windows crashes
(`too many file descriptors in select()`); `serve.py` caps it for safety.

### Updating

```powershell
Stop-Service FacultyEvaluation
git pull
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py collectstatic --noinput
Start-Service FacultyEvaluation
```

### Backups

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -U postgres -d fe_database --no-owner --no-privileges -f "D:\backups\fe_database_$(Get-Date -f yyyyMMdd).sql"
```
