import os
import sqlite3
import secrets
from flask import session
from config import USERS_ROOT
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from auth import send_email, get_user  # reuse email logic
from flask import render_template, flash
from utils import t

# In-memory store; replace with persistent store for production
VERIFICATION_CODES = {}

def generate_code():
    """Generate a 4-digit verification code."""
    return str(secrets.randbelow(9000) + 1000)  # Generates a number in 1000–9999

def store_verification(email, code):
    """Store verification code with expiry time."""
    VERIFICATION_CODES[email] = {
        "code": code,
        "expires": datetime.utcnow() + timedelta(minutes=10)
    }

def verify_code(email, submitted_code):
    """Check if submitted code is valid and not expired."""
    entry = VERIFICATION_CODES.get(email)
    if not entry:
        return False
    if datetime.utcnow() > entry["expires"]:
        del VERIFICATION_CODES[email]
        return False
    if entry["code"] == submitted_code:
        del VERIFICATION_CODES[email]  # Remove after successful verification
        return True
    return False

