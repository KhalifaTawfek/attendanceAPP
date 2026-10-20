from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.metrics import login_attempts
from app.models import Role, User
from app.schemas import ChangePasswordIn, LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def find_user_by_email(db, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DB):
    user = find_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        login_attempts.labels(result="invalid").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        login_attempts.labels(result="inactive").inc()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    login_attempts.labels(result="success").inc()
    return TokenOut(access_token=create_access_token(user.id, user.role.value), user=user)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: DB):
    if not get_settings().allow_self_registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Self-registration is disabled; ask an admin to enroll you")
    if find_user_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email.lower(), full_name=body.full_name,
        password_hash=hash_password(body.password), role=Role.user,
    )
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role.value), user=user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordIn, user: CurrentUser, db: DB):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
