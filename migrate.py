from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    columns = {
        "otp_code": "VARCHAR(6)",
        "otp_purpose": "VARCHAR(20)",
        "otp_expires_at": "TIMESTAMP",
        "otp_attempts": "INTEGER DEFAULT 0",
    }
    for col_name, col_type in columns.items():
        try:
            db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            print(f"Added column: {col_name}")
        except Exception as e:
            db.session.rollback()
            print(f"Skipped {col_name}: {e}")
