from typing import List
from ..db.models import User, TokenBlacklist, UserStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends,status,HTTPException
from ..db.connection import get_db
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime,timedelta,timezone
from ..core.config import settings
from jose import JWTError,jwt
# from ..schemas.schemas import *
from uuid import UUID
from fastapi.security.utils import get_authorization_scheme_param
from app.schemas.auth_schemas import TokenData
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional









class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        authorization: str = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if authorization and scheme.lower() == "bearer":
            return param
        
        # Check cookie
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            # Previous cookie return (Commented out):
            # return cookie_token
            
            # Parse 'Bearer <token>' out of the cookie if present
            c_scheme, c_param = get_authorization_scheme_param(cookie_token)
            if cookie_token and c_scheme.lower() == "bearer":
                return c_param
            return cookie_token
            
        return None


oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="token")





# for using uuid as id 

async def create_access_token(data: dict):
    to_encode = data.copy()
    
    # 1. Convert UUID or other non-serializable objects to strings
    for key, value in to_encode.items():
        if isinstance(value, UUID):  # Ensure you import 'from uuid import UUID'
            to_encode[key] = str(value)

    # 2. Set expiration time
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_TIME)
    to_encode.update({"exp": expire})

    # 3. Encode the JWT
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


async def verify_Access_Token(token: str, crediential_exception):
    if not token:
        raise crediential_exception

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        id = payload.get("user_id")
        role = payload.get("role")

        if id is None or role is None:
            raise crediential_exception

        return TokenData(id=str(id), role=role)

    except JWTError:
        raise crediential_exception





async def get_current_User(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    crediential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # print(f"Verifying token: {token}")

    if not token:
        raise crediential_exception

    # Now it is SAFE to continue
    result = await db.execute(select(TokenBlacklist).filter(
        TokenBlacklist.token == token
    ))
    blacklisted = result.scalars().first()

    if blacklisted:
        raise crediential_exception

    token_data = await verify_Access_Token(
        token=token,
        crediential_exception=crediential_exception
    )

    try:
        user_uuid = UUID(token_data.id)
        result = await db.execute(select(User).filter(User.id == user_uuid))
        user = result.scalars().first()
    except ValueError:
        raise crediential_exception

    if user is None:
        raise crediential_exception

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deleted"
        )

    user.last_active_at = datetime.now(timezone.utc)
    await db.commit()

    return user






async def get_current_user_optional(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    try:
        if not token:
            return None
        
        result = await db.execute(select(TokenBlacklist).filter(
            TokenBlacklist.token == token
        ))
        blacklisted = result.scalars().first()
        if blacklisted:
            return None

        crediential_exception = HTTPException(401)
        token_data = await verify_Access_Token(token, crediential_exception)
        
        user_uuid = UUID(token_data.id)
        result = await db.execute(select(User).filter(User.id == user_uuid))
        user = result.scalars().first()
        
        if user and user.status == UserStatus.ACTIVE and user.deleted_at is None:
            return user
            
        return None
    except:
        return None


def role_required(required_roles: List[str]):
    def role_checker(user:User = Depends(get_current_User)):
        if user.role not in required_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You do not have access to this resource")
        return user
    return role_checker















# for using simple id 

# async def create_access_token(data:dict):
#     to_encode=data.copy()
#     # print(f"ACCESS_TOKEN_EXPIRE_TIME: {setting.TOKEN_EXPIRE_TIME}")
#     expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_TIME)
#     to_encode.update({"exp": expire})

#     encoded_jwt=jwt.encode(to_encode,settings.SECRET_KEY,algorithm=settings.ALGORITHM)

#     return encoded_jwt







# async def get_current_User(
#     token: str = Depends(oauth2_scheme),
#     db: Session = Depends(get_db),
# ):
#     crediential_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )

#     # Verify JWT token
#     token_data = await verify_Access_Token(token=token, crediential_exception=crediential_exception)

#     # Fetch user from DB
#     user = db.query(User).filter(User.id == int(token_data.id)).first()
#     if not user:
#         raise crediential_exception

#     return user
