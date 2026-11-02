# Lawyer Diary — FastAPI Backend

This repository contains the FastAPI backend for Lawyer Diary, a mobile application designed for lawyers.

## Project Structure

```text
backend/
├── app/
│   ├── main.py             # FastAPI application entry point
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── routers/            # API routes organized by feature
│   ├── services/           # Business logic
│   ├── core/               # Settings, security, dependencies and middleware
│   ├── db/                 # SQLAlchemy Base and database session
│   └── seeds/              # Reference and holiday seed data
├── alembic/
│   ├── env.py
│   └── versions/           # Database migration history
├── alembic.ini
├── .env.example
└── requirements.txt