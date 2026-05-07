from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
import aiosqlite
from pathlib import Path
from config import settings

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(data: dict) -> str:
    """Create JWT token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return user info."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("user_id")
        email = payload.get("email")
        if user_id is None or email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "email": email}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthToken(BaseModel):
    token: str
    email: str
    user_id: int


async def init_users_db():
    """Initialize users database."""
    db_path = Path(__file__).parent.parent / "aria_users.db"
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


@router.post("/register", response_model=AuthToken)
async def register(request: RegisterRequest):
    """Register a new user."""
    db_path = Path(__file__).parent.parent / "aria_users.db"
    password_hash = pwd_context.hash(request.password)

    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (request.email, password_hash, request.name)
            )
            await db.commit()

            async with db.execute(
                "SELECT id, email FROM users WHERE email = ?",
                (request.email,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=500, detail="User registration failed")
                user_id, email = row

        token = create_token({"user_id": user_id, "email": email})
        return AuthToken(token=token, email=email, user_id=user_id)
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already registered")


@router.post("/login", response_model=AuthToken)
async def login(request: LoginRequest):
    """Login and get JWT token."""
    db_path = Path(__file__).parent.parent / "aria_users.db"

    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (request.email,)
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, email, password_hash = row

    if not pwd_context.verify(request.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"user_id": user_id, "email": email})
    return AuthToken(token=token, email=email, user_id=user_id)


@router.post("/anonymous", response_model=AuthToken)
async def anonymous_login():
    """Anonymous login for demo purposes - returns a JWT token without registration."""
    import uuid
    anon_id = str(uuid.uuid4())[:8]
    email = f"anon_{anon_id}@aria.local"

    token = create_token({
        "user_id": 0,
        "email": email,
        "is_anonymous": True
    })

    return AuthToken(
        token=token,
        email=email,
        user_id=0
    )