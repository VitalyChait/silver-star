from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import EmailStr

from .. import schemas, crud, models
from ..db import get_db
from ..security import create_access_token
from ..deps import authenticate, get_current_user


router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", response_model=schemas.UserPublic)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = crud.get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = crud.create_user(db, user_in)
    return user


@router.post("/login")
def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    user = authenticate(db, user_in.email, user_in.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    token = create_access_token(subject=user.email)
    # Ensure we don't leak sensitive fields like hashed_password
    return {"token": token, "user": schemas.UserPublic.model_validate(user)}


@router.get("/profile", response_model=schemas.UserPublic)
def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/token", response_model=schemas.Token)
def login_for_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    token = create_access_token(subject=user.email)
    return {"access_token": token, "token_type": "bearer"}
