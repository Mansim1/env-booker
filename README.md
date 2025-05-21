# EasyEnvBooker

## Overview
Environment-Booking System for PolicyCenter lower environments.
Manage single & recurring bookings, auto-suggest alternative slots, enforce utilisation caps, and download calendar invites.

---

## 📌 Key Features

- **User Authentication**: Secure registration & login (admin & regular roles).  
- **Environment Management** (Admin): Create, edit, retire sandboxes.  
- **Booking Engine**:  
  - Single and **recurring series** bookings  
  - **Clash detection** + **alternative-slot suggestions**  
  - **Utilisation guard** (90 % daily cap)  
  - **Maintenance blackout** (00:00 – 01:00 nightly)  
- **.ics Export**: Download calendar file for any booking.  
- **Audit Trail**: Admin override actions are logged for compliance.

---

## Quickstart
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run

