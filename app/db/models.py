import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Integer, Numeric, Boolean, Date, DateTime,
    ForeignKey, Enum, Index, CheckConstraint, func, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


 
#  ENUMS
 

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER  = "user"

class UserStatus(str, enum.Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    BANNED   = "banned"

class RoomStatus(str, enum.Enum):
    ACTIVE      = "active"
    INACTIVE    = "inactive"
    MAINTENANCE = "maintenance"

class ReservationStatus(str, enum.Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW   = "no_show"

class PaymentStatus(str, enum.Enum):
    INITIATED = "initiated"
    PAID      = "paid"
    FAILED    = "failed"
    REFUNDED  = "refunded"

class MessageRole(str, enum.Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    TOOL      = "tool"



#  1. USERS

class User(Base):
    __tablename__ = "users"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name   = Column(String(255), nullable=False)
    email       = Column(String(255), unique=True, nullable=False, index=True)
    phone       = Column(String(30), nullable=True)
    role        = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    status      = Column(Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False)

    # Auth
    password                    = Column(String(255), nullable=True)   # nullable = allow OAuth later
    reset_password_otp          = Column(String(10), nullable=True)
    reset_password_expires_at   = Column(DateTime(timezone=True), nullable=True)

    # Activity tracking
    last_login_at   = Column(DateTime(timezone=True), nullable=True)
    last_active_at  = Column(DateTime(timezone=True), nullable=True)

    # Soft delete
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at  = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    reservations            = relationship("Reservation", back_populates="user")
    conversation_sessions   = relationship("ConversationSession", back_populates="user")

    __table_args__ = (
        # Partial index: only index active (non-deleted) users for fast lookups
        Index("idx_users_email_active",     "email",      postgresql_where=(deleted_at.is_(None))),
        Index("idx_users_role_status",      "role",       "status"),
        Index("idx_users_created_at",       "created_at"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"



#  2. TOKEN BLACKLIST  (JWT logout / revocation)

class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    token           = Column(String, primary_key=True, index=True)
    user_id         = Column(UUID(as_uuid=True), nullable=False, index=True)
    blacklisted_at  = Column(DateTime(timezone=True), server_default=func.now())
    expires_at      = Column(DateTime(timezone=True), nullable=False)
    reason          = Column(String(50), default="logout")

    __table_args__ = (
        # Purge old tokens efficiently
        Index("idx_token_blacklist_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<TokenBlacklist(user_id={self.user_id}, reason={self.reason})>"


 
#  3. HOTELS
 

class Hotel(Base):
    __tablename__ = "hotels"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String(255), nullable=False)
    city        = Column(String(100), nullable=False)
    country     = Column(String(100), nullable=False)
    address     = Column(Text, nullable=True)
    rating      = Column(Numeric(2, 1), nullable=True)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at  = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    room_types   = relationship("RoomType", back_populates="hotel")
    rooms        = relationship("Room", back_populates="hotel")
    reservations = relationship("Reservation", back_populates="hotel")

    __table_args__ = (
        Index("idx_hotels_city",    "city"),
        Index("idx_hotels_country", "country"),
        CheckConstraint("rating >= 0 AND rating <= 5", name="check_hotel_rating"),
    )

    def __repr__(self):
        return f"<Hotel(id={self.id}, name={self.name}, city={self.city})>"


 
#  4. ROOM TYPES  (standard / deluxe / suite)
 

class RoomType(Base):
    __tablename__ = "room_types"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id    = Column(UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String(100), nullable=False)   # e.g. "Deluxe King", "Suite"
    description = Column(Text, nullable=True)
    max_guests  = Column(Integer, nullable=False)
    base_price  = Column(Numeric(10, 2), nullable=False)
    currency    = Column(String(10), default="USD", nullable=False)
    amenities   = Column(ARRAY(String), default=[])     # e.g. ["WiFi", "Pool", "Gym"]
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    hotel = relationship("Hotel", back_populates="room_types")
    rooms = relationship("Room", back_populates="room_type")

    __table_args__ = (
        Index("idx_room_types_hotel",  "hotel_id"),
        Index("idx_room_types_amenities", "amenities", postgresql_using="gin"),
        CheckConstraint("max_guests > 0",   name="check_max_guests"),
        CheckConstraint("base_price >= 0",  name="check_base_price"),
    )

    def __repr__(self):
        return f"<RoomType(id={self.id}, name={self.name}, price={self.base_price})>"


 
#  5. ROOMS  (physical inventory)
 

class Room(Base):
    __tablename__ = "rooms"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id        = Column(UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    room_type_id    = Column(UUID(as_uuid=True), ForeignKey("room_types.id", ondelete="CASCADE"), nullable=False, index=True)
    room_number     = Column(String(20), nullable=False)
    floor           = Column(Integer, nullable=True)
    status          = Column(Enum(RoomStatus), default=RoomStatus.ACTIVE, nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at      = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    hotel        = relationship("Hotel", back_populates="rooms")
    room_type    = relationship("RoomType", back_populates="rooms")
    inventory    = relationship("RoomInventory", back_populates="room")
    locks        = relationship("ReservationLock", back_populates="room")
    reservations = relationship("Reservation", back_populates="room")

    __table_args__ = (
        Index("idx_rooms_hotel_status", "hotel_id", "status"),
        Index("idx_rooms_active", "hotel_id", postgresql_where=(deleted_at.is_(None))),
        CheckConstraint("floor >= 0", name="check_floor"),
    )

    def __repr__(self):
        return f"<Room(id={self.id}, number={self.room_number}, status={self.status})>"


 
#  6. ROOM INVENTORY  ★ MOST CRITICAL TABLE ★
#     One row per room per day — the ONLY source of truth for availability
 

class RoomInventory(Base):
    __tablename__ = "room_inventory"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id         = Column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_date  = Column(Date, nullable=False)
    is_available    = Column(Boolean, default=True, nullable=False)
    price_override  = Column(Numeric(10, 2), nullable=True)   # NULL = use room_type.base_price
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="inventory")

    __table_args__ = (
        # THE most important constraint: one record per room per day
        Index("uq_room_inventory_date", "room_id", "inventory_date", unique=True),
        # Fastest availability search path
        Index("idx_inventory_date",         "inventory_date"),
        Index("idx_inventory_room_date",    "room_id", "inventory_date"),
        Index("idx_inventory_available",    "room_id", "inventory_date",
              postgresql_where=(is_available.is_(True))),
        CheckConstraint("price_override IS NULL OR price_override >= 0", name="check_price_override"),
    )

    def __repr__(self):
        return f"<RoomInventory(room={self.room_id}, date={self.inventory_date}, available={self.is_available})>"


 
#  7. RESERVATIONS
 

class Reservation(Base):
    __tablename__ = "reservations"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    hotel_id            = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False, index=True)
    room_id             = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, index=True)
    checkin_date        = Column(Date, nullable=False)
    checkout_date       = Column(Date, nullable=False)
    guest_count         = Column(Integer, nullable=False)
    status              = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING, nullable=False)
    total_amount        = Column(Numeric(10, 2), nullable=True)
    currency            = Column(String(10), default="USD", nullable=False)
    confirmation_code   = Column(String(50), unique=True, index=True, nullable=True)
    special_requests    = Column(Text, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    cancelled_at        = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user     = relationship("User", back_populates="reservations")
    hotel    = relationship("Hotel", back_populates="reservations")
    room     = relationship("Room", back_populates="reservations")
    guests   = relationship("ReservationGuest", back_populates="reservation", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="reservation")

    __table_args__ = (
        Index("idx_reservations_user",      "user_id"),
        Index("idx_reservations_hotel",     "hotel_id"),
        Index("idx_reservations_status",    "status"),
        Index("idx_reservations_dates",     "checkin_date", "checkout_date"),
        # Checkout must be after checkin
        CheckConstraint("checkout_date > checkin_date", name="check_checkout_after_checkin"),
        CheckConstraint("guest_count > 0",              name="check_guest_count"),
        CheckConstraint("total_amount IS NULL OR total_amount >= 0", name="check_total_amount"),
    )

    def __repr__(self):
        return f"<Reservation(id={self.id}, status={self.status}, code={self.confirmation_code})>"


 
#  8. RESERVATION GUESTS  (multiple guests per booking)
 

class ReservationGuest(Base):
    __tablename__ = "reservation_guests"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_id  = Column(UUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name       = Column(String(255), nullable=False)
    email           = Column(String(255), nullable=True)
    phone           = Column(String(30), nullable=True)

    reservation = relationship("Reservation", back_populates="guests")

    def __repr__(self):
        return f"<ReservationGuest(name={self.full_name}, reservation={self.reservation_id})>"


 
#  9. PAYMENTS
 

class Payment(Base):
    __tablename__ = "payments"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_id  = Column(UUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True)
    amount          = Column(Numeric(10, 2), nullable=False)
    currency        = Column(String(10), nullable=False, default="USD")
    provider        = Column(String(50), nullable=False)            # "stripe", "paypal"
    transaction_ref = Column(String(255), unique=True, nullable=True)
    status          = Column(Enum(PaymentStatus), default=PaymentStatus.INITIATED, nullable=False)
    extra_metadata  = Column(JSONB, default={})                     # provider-specific data
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    reservation = relationship("Reservation", back_populates="payments")

    __table_args__ = (
        Index("idx_payments_reservation", "reservation_id"),
        Index("idx_payments_status",      "status"),
        CheckConstraint("amount > 0", name="check_payment_amount"),
    )

    def __repr__(self):
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"


 
#  10. RESERVATION LOCKS  (hold during AI conversation)
#      Prevents double-booking while user is deciding
 

class ReservationLock(Base):
    __tablename__ = "reservation_locks"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id     = Column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id  = Column(String(255), nullable=False)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    room = relationship("Room", back_populates="locks")

    __table_args__ = (
        Index("idx_locks_expiry",   "expires_at"),
        Index("idx_locks_session",  "session_id"),
        Index("idx_locks_room",     "room_id", "expires_at"),
    )

    def __repr__(self):
        return f"<ReservationLock(room={self.room_id}, session={self.session_id}, expires={self.expires_at})>"


 
#  11. CONVERSATION SESSIONS  (LangGraph state persistence)
 

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # NULL = anonymous caller
    session_state   = Column(JSONB, nullable=True)  # full LangGraph checkpoint state
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user     = relationship("User", back_populates="conversation_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_user",       "user_id"),
        Index("idx_sessions_updated_at", "updated_at"),
    )

    def __repr__(self):
        return f"<ConversationSession(id={self.id}, user={self.user_id})>"


 
#  12. MESSAGES  (full conversation history)
 

class Message(Base):
    __tablename__ = "messages"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id  = Column(UUID(as_uuid=True), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role        = Column(Enum(MessageRole), nullable=False)   # user / assistant / tool
    content     = Column(Text, nullable=False)
    extra_metadata = Column(JSONB, default={})                # tool call args, token counts etc.
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ConversationSession", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_session",    "session_id"),
        Index("idx_messages_role",       "session_id", "role"),
        Index("idx_messages_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Message(session={self.session_id}, role={self.role})>"
