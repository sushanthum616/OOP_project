# MiniShop – Online Shopping System

MiniShop is an Amazon-like online shopping web application built with FastAPI and Python OOP architecture.

## Features

- Product catalog
- User authentication
- Cart management
- Address book
- Checkout & orders
- Payment simulation
- Reviews and ratings
- Admin product & order management

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- SQLite
- Jinja2
- Pytest

## Project Architecture

domain → repositories → services → web

## Run Application

```bash
python -m uvicorn backend.app.main:app --reload


