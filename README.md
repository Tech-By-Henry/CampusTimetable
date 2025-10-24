# Campus Timetable & Live Update Web App

## What this is (MVP)
One source of truth for campus timetables with clean roles and a real-time-friendly backend.

## What’s shipped
- **OT-Setup:** creates SuperAdmin + Institution (one-time).
- **Auth:** JWT (login via **email** or **username**).
- **Catalog (SuperAdmin-only):** Faculties, Departments, Programs, Rooms, Academic Terms.
- **API:**
    POST /api/v1/superadmin/auth/ot-setup/
    POST /api/v1/superadmin/auth/login/
    GET|POST /api/v1/superadmin/catalog/faculties/
    GET|POST /api/v1/superadmin/catalog/departments/
    GET|POST /api/v1/superadmin/catalog/programs/
    GET|POST /api/v1/superadmin/catalog/rooms/
    GET|POST /api/v1/superadmin/catalog/terms/

## Current stack
- **Backend:** Django + DRF  
- **Auth:** SimpleJWT  
- **DB:** PostgreSQL  
- **Config:** django-environ  

## Run locally
    pip install -r requirements.txt
    # ensure Postgres is running and the DB exists (e.g., createdb campus_timetable)
    python manage.py migrate
    python manage.py runserver
