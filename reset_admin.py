import os
from index import app, db
from models import User
from werkzeug.security import generate_password_hash

def reset_password():
    print("--- YourLifePathways Admin Recovery Utility ---")
    username = input("Enter admin username: ").strip()
    new_password = input("Enter NEW password: ").strip()
    
    if len(new_password) < 8:
        print("Error: Password must be at least 8 characters.")
        return

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            print(f"\nSUCCESS: Password for '{username}' has been updated.")
        else:
            print(f"\nERROR: User '{username}' not found in the database.")

if __name__ == "__main__":
    reset_password()
