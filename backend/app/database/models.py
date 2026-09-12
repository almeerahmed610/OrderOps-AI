from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from sqlalchemy.orm import relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(150), nullable=False)

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)

    email = Column(String(255), nullable=True)

    phone = Column(String(50), nullable=True)

    address = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    orders = relationship(
        "Order",
        back_populates="customer",
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    sku = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    price = Column(
        Float,
        nullable=False,
        default=0,
    )

    stock_quantity = Column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active = Column(
        Boolean,
        default=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    order_number = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
    )

    status = Column(
        String(50),
        nullable=False,
        default="pending",
    )

    risk_score = Column(
        Float,
        default=0,
    )

    risk_level = Column(
        String(30),
        default="low",
    )

    total_amount = Column(
        Float,
        default=0,
    )

    recovered_amount = Column(
        Float,
        default=0,
    )

    refund_amount = Column(
        Float,
        default=0,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    customer = relationship(
        "Customer",
        back_populates="orders",
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    negotiations = relationship(
        "Negotiation",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    agent_events = relationship(
        "AgentEvent",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity = Column(
        Integer,
        nullable=False,
        default=1,
    )

    unit_price = Column(
        Float,
        nullable=False,
        default=0,
    )

    order = relationship(
        "Order",
        back_populates="items",
    )

    product = relationship(
        "Product",
    )


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )

    original_product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=True,
    )

    alternative_product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=True,
    )

    discount_percent = Column(
        Float,
        default=0,
    )

    offered_price = Column(
        Float,
        default=0,
    )

    channel = Column(
        String(30),
        default="email",
    )

    status = Column(
        String(50),
        default="pending",
    )

    customer_response = Column(
        String(50),
        nullable=True,
    )

    message = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    responded_at = Column(
        DateTime,
        nullable=True,
    )

    order = relationship(
        "Order",
        back_populates="negotiations",
    )

    original_product = relationship(
        "Product",
        foreign_keys=[original_product_id],
    )

    alternative_product = relationship(
        "Product",
        foreign_keys=[alternative_product_id],
    )


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=True,
    )

    node_name = Column(
        String(100),
        nullable=False,
    )

    event_type = Column(
        String(100),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=True,
    )

    status = Column(
        String(50),
        default="completed",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    order = relationship(
        "Order",
        back_populates="agent_events",
    )