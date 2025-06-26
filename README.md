# Environment Booker

[![Python Version](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)  
[![Flask Version](https://img.shields.io/badge/flask-2.x-green)](https://flask.palletsprojects.com/)  
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

A Flask web app to book and manage shared testing environments.  
Supports **regular** users and **admins**.

---

## Features

- **User Accounts & Roles**  
  - **Regular** users can register, log in, create/read/update/delete *their own* bookings, and view *their own* audit entries.  
  - **Admin** users can perform CRUD on environments & bookings, and view audit entries.

- **Environments** (admin only)  
  - Create / edit / delete environments  
  - Assign to an “owner squad”  
  - Record creator & timestamp

- **Bookings**  
  - Single & recurring (series) bookings  
  - Clash detection within each environment  
  - 8 hr max duration, 90% daily utilization cap  
  - ±3 hr suggestions for alternate slots  
  - “Force book” override for admins

- **Audit Trail**  
  - Logs every create/update/delete on environments & bookings  
  - Includes actor, timestamp, and readable details

- **Responsive UI**  
  - Bootstrap 5, DataTables for sortable/filterable lists  
  - Delete-confirm modals, dark/light-mode toggle  
  - Relative “time ago” timestamps via timeago.js

- **Accessibility**  
  - “Skip to content” link, ARIA roles & landmarks  
  - Meta tags & Open Graph for sharing  
  - SRI & `crossorigin` on CDN assets  
  - Dynamic active-link highlighting

---

## Tech Stack

- **Backend**: Python 3.12, Flask, Flask-Login, Flask-SQLAlchemy  
- **Database**: SQLite
- **Frontend**: Bootstrap 5, jQuery, DataTables, Bootstrap Icons, timeago.js  
- **Dev & Testing**: pip, `flask` CLI, pytest, Flake8  
- **Deployment**: PythonAnywhere (WSGI)

---

## Prerequisites

- Python 3.12  
- `virtualenv`, `pip`
- flask init-db

---

## Environment Variables

Create a `.env` in the project root:

SECRET_KEY="your-secret-key"
FLASK_CONFIG="development"
FLASK_APP=app:create_app
DATABASE_URL="sqlite:///instance/dev.db"

---

## Documentation

- [Data Model](docs/data-model.md)
- [Architecture & Component Design](docs/architecture.md)
- [Agile Artefacts](docs/agile-artifacts.md)
- [User Guide & UI Walkthrough](docs/user-guide.md)

---

## Quickstart

1. **Clone & venv**

   ```bash
   git clone https://github.com/yourusername/env-booker.git
   cd env-booker
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   flask init-db
