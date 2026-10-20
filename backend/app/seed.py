"""Seed demo users. Idempotent: existing demo users only get their password reset.

Usage:  python -m app.seed [--password PASSWORD]
"""
import argparse

from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import seed_admin
from app.models import Role, User
from app.security import hash_password

DEMO_USERS = [
    ("Alice Johnson", "alice.johnson@example.com", Role.user),
    ("Bogdan Popescu", "bogdan.popescu@example.com", Role.user),
    ("Carmen Ionescu", "carmen.ionescu@example.com", Role.user),
    ("David Miller", "david.miller@example.com", Role.user),
    ("Elena Dumitru", "elena.dumitru@example.com", Role.user),
    ("Farid Haddad", "farid.haddad@example.com", Role.user),
    ("Grace Kim", "grace.kim@example.com", Role.user),
    ("Hugo Martin", "hugo.martin@example.com", Role.user),
    ("Ioana Stan", "ioana.stan@example.com", Role.user),
    ("Jonas Weber", "jonas.weber@example.com", Role.user),
    ("Katarzyna Nowak", "katarzyna.nowak@example.com", Role.user),
    ("Liam O'Brien", "liam.obrien@example.com", Role.user),
    ("Maria Garcia", "maria.garcia@example.com", Role.admin),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password", default="test", help="shared password for all seeded users")
    args = parser.parse_args()

    seed_admin()
    pw_hash = hash_password(args.password)
    created = 0
    with SessionLocal() as db:
        for full_name, email, role in DEMO_USERS:
            user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
            if user:
                user.password_hash = pw_hash
                continue
            db.add(User(email=email, full_name=full_name, password_hash=pw_hash, role=role))
            created += 1
        db.commit()
    print(f"Created {created} user(s), reset password on {len(DEMO_USERS) - created}. Password: {args.password}")


if __name__ == "__main__":
    main()
