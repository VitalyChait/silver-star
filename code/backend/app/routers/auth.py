from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import EmailStr

from .. import schemas, crud, models
from ..security import get_password_hash
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
    # Guest bypass for testing/demo
    if user_in.email == "gues@gues.com" and user_in.password == "guest":
        user = crud.get_user_by_email(db, user_in.email)
        if not user:
            user = models.User(
                name="Guest",
                email=user_in.email,
                hashed_password=get_password_hash(user_in.password),
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(subject=user.email)
        return {"token": token, "user": schemas.UserPublic.model_validate(user)}

    user = authenticate(db, user_in.email, user_in.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    token = create_access_token(subject=user.email)
    # Ensure we don't leak sensitive fields like hashed_password
    return {"token": token, "user": schemas.UserPublic.model_validate(user)}


@router.get("/profile", response_model=schemas.UserPublic)
def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/profile/details", response_model=schemas.CandidateProfilePublic | dict)
def get_profile_details(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    profile = crud.get_candidate_profile(db, current_user.id)
    if not profile:
        return {}
    return profile


@router.put("/profile/details", response_model=schemas.CandidateProfilePublic)
def update_profile_details(
    payload: schemas.CandidateProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    profile = crud.upsert_candidate_profile(db, current_user.id, payload)
    return profile


@router.post("/token", response_model=schemas.Token)
def login_for_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Guest bypass for OAuth2 form flow
    if form_data.username == "gues@gues.com" and form_data.password == "guest":
        user = crud.get_user_by_email(db, form_data.username)
        if not user:
            user = models.User(
                name="Guest",
                email=form_data.username,
                hashed_password=get_password_hash(form_data.password),
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(subject=user.email)
        return {"access_token": token, "token_type": "bearer"}

    user = authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    token = create_access_token(subject=user.email)
    return {"access_token": token, "token_type": "bearer"}
