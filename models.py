"""Modèles de données du CRM Epic Events."""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Role(Base):
    """Département auquel appartient un collaborateur."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(20), unique=True, nullable=False)

    collaborators = relationship("Collaborator", back_populates="role")


class Collaborator(Base):
    __tablename__ = "collaborators"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    role = relationship("Role", back_populates="collaborators")
    clients = relationship("Client", back_populates="sales_contact")
    events = relationship("Event", back_populates="support_contact")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=False)
    company_name = Column(String(150), nullable=False)
    created_at = Column(Date, default=date.today, nullable=False)
    updated_at = Column(Date, default=date.today, onupdate=date.today, nullable=False)
    sales_contact_id = Column(Integer, ForeignKey("collaborators.id"), nullable=False)

    sales_contact = relationship("Collaborator", back_populates="clients")
    contracts = relationship("Contract", back_populates="client")


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="positive_total_amount"),
        CheckConstraint(
            "amount_due >= 0 AND amount_due <= total_amount",
            name="valid_amount_due",
        ),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    amount_due = Column(Numeric(12, 2), nullable=False)
    created_at = Column(Date, default=date.today, nullable=False)
    is_signed = Column(Boolean, default=False, nullable=False)

    client = relationship("Client", back_populates="contracts")
    events = relationship("Event", back_populates="contract")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="valid_event_dates"),
        CheckConstraint("attendee_count >= 0", name="positive_attendee_count"),
    )

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    support_contact_id = Column(Integer, ForeignKey("collaborators.id"), nullable=True)
    name = Column(String(150), nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=False)
    attendee_count = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

    contract = relationship("Contract", back_populates="events")
    support_contact = relationship("Collaborator", back_populates="events")
