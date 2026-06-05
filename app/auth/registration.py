from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import User, TokenBlacklist
from ..db.connection import get_db
from .authentication import get_current_User, verify_Access_Token, create_access_token, role_required, oauth2_scheme
from app.schemas.auth_schemas import UserRegister, UserLogin, ForgotPasswordRequest, ResetPasswordRequest, VerifyOtp
from app.utils.helper import verify_password, hash_password, generate_otp, get_otp_expire_time
from app.core.config import settings
from fastapi_mail import FastMail, MessageSchema
from fastapi import BackgroundTasks
from app.utils.email_utils import send_account_email, get_html_layout
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text, select
from datetime import datetime, timezone
from jose import jwt, JWTError
from app.core.logging import get_logger



logger = get_logger(__name__)


router = APIRouter(tags=["Auth"], prefix="/auth")







@router.post("/signup")
async def signup(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_User),
    background_tasks: BackgroundTasks = None
):
    # # Role validation
    # if user_data.role == "admin" and current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Only admin can create admin")
    # if user_data.role == "doctor" and current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Only admin can create doctor")
    # if user_data.role == "patient" and current_user.role != "doctor":
    #     raise HTTPException(status_code=403, detail="Only doctor can create patient")

    # Email check
    result = await db.execute(select(User).filter(User.email == user_data.email))
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user instance but DO NOT commit yet
    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        password=hash_password(user_data.password),
        # role =  user_data.role if user_data.role in ["ADMIN", "USER"] else ""
    )
    logger.info("New user created")

    try:
        email_content = get_html_layout(
            title="Welcome to Our Platform!",
            content=f"""
                <p>Hello <strong>{new_user.full_name}</strong>,</p>
                <p>We're excited to have you on board. Your account has been successfully created.</p>
                <p>Your login email: <strong>{new_user.email}</strong></p>
                <p>You can now log in and start exploring our services.</p>
            """,
            button_text="Log In Now",
            button_url=f"{settings.ENVIRONMENT == 'production' and 'https' or 'http'}://127.0.0.1:8000" # Update with real URL if needed
        )
        await send_account_email(
            background_tasks,
            new_user.email,
            "User Account Created",
            email_content
        )
    except Exception as e:
        logger.error("Unable to send email to the user")
        print(e)
    logger.info("Email sent successfully to the user")

    db.add(new_user)
    await db.flush()  # assign ID without committing

    await db.commit()  # commit everything atomically
    await db.refresh(new_user)
    logger.info("User saved successfully in the database")


    return {"msg": f"{new_user.role.value.capitalize() if hasattr(new_user.role, 'value') else str(new_user.role).capitalize()} created successfully", "id": new_user.id}






@router.post("/login")
async def login(user_credentials: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    # fetch user regardless of active/inactive
    result = await db.execute(
        text("""
            SELECT id, email, password, role, status
            FROM users
            WHERE email = :email
            LIMIT 1
        """),
        {"email": user_credentials.email}
    )
    user = result.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials"
        )
    
    # print(user.status)

    # check if account is inactive
    if user.status in ("SUSPENDED", "INACTIVE", "DELETED"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support."
        )

    # verify password
    if not verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials"
        )
    
    # Update last_login_at
    try:
        await db.execute(
            text("UPDATE users SET last_login_at = :now WHERE id = :user_id"),
            {"now": datetime.now(timezone.utc), "user_id": user.id}
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to update last_login_at for user {user.id}: {e}")
        # Continue login even if timestamp update fails
        pass

    # create JWT token with role
    access_token = await create_access_token(
        data={"user_id": str(user.id), "role": user.role}
    )

    
    # Set cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_TIME * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_TIME * 60,
        samesite="lax",
        secure=False, # Set to False if testing locally without HTTPS, but True is safer generally
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_User)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "status": current_user.status
    }




@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest, 
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    # 1. No 'current_user' dependency here. 
    # Forgot password is an unauthenticated (public) route.

    # 2. Fetch only the columns you need to save memory
    result = await db.execute(text(
        "SELECT full_name FROM users WHERE email = :email"
    ), {"email": request.email})
    user = result.fetchone()

    # 3. Privacy/Security: Do not confirm if the email exists or not
    if not user:
        raise HTTPException(status_code=404, detail="Account Not Found")
    
    otp = generate_otp()
    expires_at = get_otp_expire_time()

    logger.info(f"Forgot password hit successfully OTP is: {otp}")


    # print("OTP is :", otp)
    # 4. Use a try/except block for DB operations
    try:
        await db.execute(
            text("""
                UPDATE users 
                SET reset_password_otp = :otp, 
                    reset_password_expires_at = :expires_at 
                WHERE email = :email
            """),
            {"otp": otp, "expires_at": expires_at, "email": request.email}
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    # 5. Send email asynchronously using BackgroundTasks
    email_content = get_html_layout(
        title="Password Reset Request",
        content=f"""
            <p>Hello {user.full_name},</p>
            <p>We received a request to reset your password. Use the code below to complete the process. This code will expire in 5 minutes.</p>
            <div class="otp-box">{otp}</div>
            <p>If you did not request this, you can safely ignore this email.</p>
        """
    )
    await send_account_email(
        background_tasks,
        request.email,
        "Password Reset OTP",
        email_content
    )

    return {"message": "If your email is registered, you will receive an OTP shortly."}





@router.post("/verify-otp", status_code=200)
async def verify_otp(user_data : VerifyOtp, db: AsyncSession = Depends(get_db)):
     result = await db.execute(
         text(
             """SELECT full_name, reset_password_otp, reset_password_expires_at FROM users WHERE email = :email"""
         ), {"email": user_data.email}
     )
     user = result.fetchone()

     if not user:
         raise HTTPException(status_code=400, detail="Email not found ")
     
     if(
        user.reset_password_otp != user_data.otp
        or user.reset_password_expires_at is None
        or datetime.now(timezone.utc) > user.reset_password_expires_at
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
     

     return {"response": "Otp verified successfully"}
         
         



@router.post("/reset-password")
async def reset_password(request:ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    result = await db.execute(
        text("SELECT * FROM users WHERE email = :email"),{"email":request.email}
    )
    user = result.fetchone()


    if not user:
        raise HTTPException(status_code=400, detail="Email not found ")
    
    logger.info(f"Reset Password Called")
    
    # if(
    #     user.reset_password_otp != request.otp
    #     or user.reset_password_expires_at is None
    #     or datetime.now(timezone.utc) > user.reset_password_expires_at
    # ):
        # raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    

    hashed_password = hash_password(request.new_password)


    await db.execute(
        text("""
            UPDATE users 
            SET password = :password, reset_password_otp = NULL, reset_password_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE email = :email
        """),
        {"password": hashed_password, "email": request.email}
    )
    await db.commit()

    return {"msg": "Password reset successfully"}





@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_User),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Decode token to get expiration time
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        
        if not exp:
             raise HTTPException(status_code=400, detail="Invalid token")

        # Create blacklist entry
        blacklist_token = TokenBlacklist(
            token=token,
            user_id=current_user.id,
            expires_at=datetime.fromtimestamp(exp, timezone.utc)
        )
        db.add(blacklist_token)
        
        # Update last active time
        current_user.last_active_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        response = Response(content="Successfully logged out")
        response.delete_cookie("access_token")
        return {"msg": "Successfully logged out"}
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")







# @router.post("/token")
# async def loginAuth(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.username == form_data.username).first()
#     if not user or not verify_password(form_data.password,user.password):
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

#     access_token = await create_access_token(data={"user_id": user.id, "role": user.role})
#     return {"access_token": access_token, "token_type": "bearer"}


