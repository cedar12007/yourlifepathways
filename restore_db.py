import json
import os
from datetime import datetime
from index import app, db
from models import User, Post, Comment, PostLike, PostShare, PostView, LoginHistory

def restore_backup():
    print("--- YourLifePathways Database Restoration Tool ---")
    filename = input("Enter the path to your backup JSON file: ").strip()

    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return

    try:
        with open(filename, 'r') as f:
            data = json.load(f)

        with app.app_context():
            print("Cleaning existing tables...")
            # Delete in order of dependencies (leaves first)
            LoginHistory.query.delete()
            PostLike.query.delete()
            PostShare.query.delete()
            PostView.query.delete()
            Comment.query.delete()
            Post.query.delete()
            User.query.delete()
            db.session.commit()

            print("Repopulating tables...")

            # 1. Users
            for u in data.get('users', []):
                db.session.add(User(**u))
            
            # 2. Posts
            for p in data.get('posts', []):
                # Convert ISO strings back to datetime objects
                p['date_created'] = datetime.fromisoformat(p['date_created'])
                p['updated_date'] = datetime.fromisoformat(p['updated_date'])
                db.session.add(Post(**p))
            
            db.session.commit() # Commit parents before children

            # 3. Comments
            for c in data.get('comments', []):
                c['date_created'] = datetime.fromisoformat(c['date_created'])
                db.session.add(Comment(**c))

            # 4. Engagement Tables
            for l in data.get('likes', []):
                if l['timestamp']: l['timestamp'] = datetime.fromisoformat(l['timestamp'])
                db.session.add(PostLike(**l))

            for s in data.get('shares', []):
                if s['timestamp']: s['timestamp'] = datetime.fromisoformat(s['timestamp'])
                db.session.add(PostShare(**s))

            for v in data.get('views', []):
                if v['timestamp']: v['timestamp'] = datetime.fromisoformat(v['timestamp'])
                db.session.add(PostView(**v))

            for log in data.get('login_history', []):
                if log['timestamp']: log['timestamp'] = datetime.fromisoformat(log['timestamp'])
                db.session.add(LoginHistory(**log))

            db.session.commit()
            print("\nSUCCESS: All data from the backup has been restored.")

    except Exception as e:
        print(f"\nFATAL ERROR during restoration: {e}")
        db.session.rollback()

if __name__ == "__main__":
    restore_backup()
