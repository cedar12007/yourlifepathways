from index import app, db # Get db directly from the initialized app
from models import Post

# Your mock data
all_posts = [
    {
        'title': "Coaching vs. Counseling - What's the difference?",
        'summary': "Do I need a therapist or a coach? While both professions involve deep listening and powerful conversations, they serve very different purposes.",
        'image_file': 'coaching_vs_counseling.jpg',
        'initial_likes': 15,
        'category': 'Professional Growth',
        'is_featured': False
    },
    {
        'title': 'The "I’m Not Broken" Myth (Why High Achievers Avoid Coaching)',
        'summary': "Why coaching isn’t about 'fixing' you, it’s about helping you scale and reach your full potential",
        'image_file': 'i_am_not_broken.jpg',
        'initial_likes': 42,
        'category': 'Leadership',
        'is_featured': False
    },
    {
        'title': 'Coaching vs. Consulting.  Another confusing distinction?!',
        'summary': 'In the simplest terms: One gives you the answer; the other gives you the ability.  Which is which?',
        'image_file': 'coaching_vs_consulting.jpg',
        'initial_likes': 89,
        'category': 'Business',
        'is_featured': False
    },
    {
        'title': 'Coach being coached, is it a paradox?',
        'summary': 'As a coach, I also benefit from the power of coaching by another coach.  Why does it make sense?',
        'image_file': 'coach_being_coached.jpg',
        'initial_likes': 89,
        'category': 'Business',
        'is_featured': False
    }
]


def seed_database():
    # 'with app.app_context()' tells SQLAlchemy which app settings to use
    with app.app_context():
        try:
            print("Creating database tables...")
            db.create_all()

            if Post.query.first():
                print("Data already exists. Skipping.")
            else:
                for data in all_posts:
                    new_post = Post(**data)
                    db.session.add(new_post)
                db.session.commit()
                print("Database successfully seeded!")
        except Exception as e:
            print(f"An error occurred: {e}")
            db.session.rollback()


def reset_and_seed():
    with app.app_context():
        print("Dropping and recreating tables...")
        #db.drop_all()
        #db.create_all()

        print("Seeding data...")
        for data in all_posts:
            # 1. Extract the likes so we don't pass them to the Post model
            likes_count = data.pop('initial_likes', 0)

            # 2. Create the post
            new_post = Post(**data)
            db.session.add(new_post)
            db.session.flush()  # This generates the post.id without committing yet

        db.session.commit()
        print("Database successfully reset and seeded with statistics!")


def do_nothing():
    print("seed_db: Doing Nothing")

if __name__ == '__main__':
    #reset_and_seed()
    #seed_database()
    do_nothing()