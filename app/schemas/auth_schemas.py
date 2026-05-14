from pydantic import BaseModel, EmailStr
from typing import Optional






class UserBase(BaseModel):
    username: Optional[str] = None
    email: EmailStr
    role: str


class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: Optional[str] = None  # "admin", "user"


class UserCreate(UserBase):
    password: str


class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class TokenData(BaseModel):
    id: Optional[str] = None
    role: Optional[str] = None


    
class SignupResponse(BaseModel):
    msg: str
    user_id: int



class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    # otp: str
    new_password: str
    confirm_password: str



class VerifyOtp(BaseModel):
    email: EmailStr
    otp: str
