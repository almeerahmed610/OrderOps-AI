from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.database.models import (
    AgentEvent,
    Customer,
    Order,
    OrderItem,
    Product,
)


router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)

security = HTTPBearer()


# =========================================================
# AUTHENTICATION
# =========================================================

def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = decode_access_token(
        credentials.credentials
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return payload


# =========================================================
# ORDER NUMBER
# =========================================================

def generate_order_number() -> str:
    short_id = uuid4().hex[:8].upper()

    return (
        f"ORD-{datetime.now().strftime('%Y%m%d')}"
        f"-{short_id}"
    )


# =========================================================
# CREATE ORDER
# =========================================================

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    customer_id = data.get("customer_id")
    items = data.get("items")

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="Customer ID is required.",
        )

    if not items:
        raise HTTPException(
            status_code=400,
            detail="At least one order item is required.",
        )

    if not isinstance(items, list):
        raise HTTPException(
            status_code=400,
            detail="Items must be a list.",
        )

    # -----------------------------------------------------
    # Customer
    # -----------------------------------------------------

    customer = (
        db.query(Customer)
        .filter(Customer.id == int(customer_id))
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    # -----------------------------------------------------
    # Validate ALL products BEFORE creating order
    # -----------------------------------------------------

    prepared_items = []
    total_amount = 0

    for item in items:

        product_id = item.get("product_id")
        quantity = item.get("quantity")

        if not product_id:
            raise HTTPException(
                status_code=400,
                detail="Product ID is required for every item.",
            )

        if quantity is None:
            raise HTTPException(
                status_code=400,
                detail="Quantity is required for every item.",
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Quantity must be a valid number.",
            )

        if quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity must be greater than zero.",
            )

        product = (
            db.query(Product)
            .filter(Product.id == int(product_id))
            .first()
        )

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found.",
            )

        if not product.is_active:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Product '{product.name}' "
                    f"is currently inactive."
                ),
            )

        # -------------------------------------------------
        # STOCK CHECK
        # -------------------------------------------------

        if product.stock_quantity < quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for "
                    f"'{product.name}'. "
                    f"Available stock: "
                    f"{product.stock_quantity}."
                ),
            )

        unit_price = float(product.price)

        line_total = unit_price * quantity

        total_amount += line_total

        prepared_items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        )

    # -----------------------------------------------------
    # Create Order
    # -----------------------------------------------------

    order = Order(
        order_number=generate_order_number(),
        customer_id=customer.id,
        status="pending",
        risk_score=0,
        risk_level="low",
        total_amount=total_amount,
        recovered_amount=0,
        refund_amount=0,
    )

    db.add(order)
    db.flush()

    # -----------------------------------------------------
    # Create Order Items + Reduce Stock
    # -----------------------------------------------------

    response_items = []

    for item in prepared_items:

        product = item["product"]
        quantity = item["quantity"]
        unit_price = item["unit_price"]

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=unit_price,
        )

        db.add(order_item)

        # Reduce inventory
        product.stock_quantity -= quantity

        response_items.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": unit_price * quantity,
                "remaining_stock": product.stock_quantity,
            }
        )

    # -----------------------------------------------------
    # Agent Event
    # -----------------------------------------------------

    agent_event = AgentEvent(
        order_id=order.id,
        node_name="OrderCreationAgent",
        event_type="order_created",
        message=(
            f"Order {order.order_number} created "
            f"for customer {customer.name}."
        ),
        status="completed",
    )

    db.add(agent_event)

    # -----------------------------------------------------
    # Commit
    # -----------------------------------------------------

    db.commit()
    db.refresh(order)

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return {
        "message": "Order created successfully.",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "customer_id": order.customer_id,
            "customer_name": customer.name,
            "status": order.status,
            "risk_score": order.risk_score,
            "risk_level": order.risk_level,
            "total_amount": order.total_amount,
            "recovered_amount": order.recovered_amount,
            "refund_amount": order.refund_amount,
            "items": response_items,
            "created_at": order.created_at,
        },
    }


# =========================================================
# LIST ORDERS
# =========================================================

@router.get("/")
def get_orders(
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    orders = (
        db.query(Order)
        .order_by(Order.id.desc())
        .all()
    )

    result = []

    for order in orders:

        result.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "customer_name": (
                    order.customer.name
                    if order.customer
                    else None
                ),
                "status": order.status,
                "risk_score": order.risk_score,
                "risk_level": order.risk_level,
                "total_amount": order.total_amount,
                "recovered_amount": order.recovered_amount,
                "refund_amount": order.refund_amount,
                "items_count": len(order.items),
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            }
        )

    return result


# =========================================================
# ORDER DETAIL
# =========================================================

@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    items = []

    for item in order.items:

        items.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "sku": (
                    item.product.sku
                    if item.product
                    else None
                ),
                "product_name": (
                    item.product.name
                    if item.product
                    else None
                ),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": (
                    item.quantity * item.unit_price
                ),
                "current_stock": (
                    item.product.stock_quantity
                    if item.product
                    else None
                ),
            }
        )

    negotiations = []

    for negotiation in order.negotiations:

        negotiations.append(
            {
                "id": negotiation.id,
                "original_product_id": (
                    negotiation.original_product_id
                ),
                "alternative_product_id": (
                    negotiation.alternative_product_id
                ),
                "discount_percent": (
                    negotiation.discount_percent
                ),
                "offered_price": (
                    negotiation.offered_price
                ),
                "channel": negotiation.channel,
                "status": negotiation.status,
                "customer_response": (
                    negotiation.customer_response
                ),
                "message": negotiation.message,
                "created_at": negotiation.created_at,
                "responded_at": negotiation.responded_at,
            }
        )

    agent_events = []

    for event in order.agent_events:

        agent_events.append(
            {
                "id": event.id,
                "node_name": event.node_name,
                "event_type": event.event_type,
                "message": event.message,
                "status": event.status,
                "created_at": event.created_at,
            }
        )

    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer": {
            "id": (
                order.customer.id
                if order.customer
                else None
            ),
            "name": (
                order.customer.name
                if order.customer
                else None
            ),
            "email": (
                order.customer.email
                if order.customer
                else None
            ),
            "phone": (
                order.customer.phone
                if order.customer
                else None
            ),
            "address": (
                order.customer.address
                if order.customer
                else None
            ),
        },
        "status": order.status,
        "risk_score": order.risk_score,
        "risk_level": order.risk_level,
        "total_amount": order.total_amount,
        "recovered_amount": order.recovered_amount,
        "refund_amount": order.refund_amount,
        "items": items,
        "negotiations": negotiations,
        "agent_events": agent_events,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


# =========================================================
# UPDATE ORDER STATUS
# =========================================================

@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    new_status = str(
        data.get("status", "")
    ).strip().lower()

    allowed_statuses = {
        "pending",
        "processing",
        "fulfillment",
        "out_of_stock",
        "negotiation",
        "accepted",
        "rejected",
        "refunded",
        "completed",
        "cancelled",
        "human_audit",
    }

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid order status. "
                f"Allowed values: "
                f"{', '.join(sorted(allowed_statuses))}"
            ),
        )

    order.status = new_status

    db.commit()
    db.refresh(order)

    return {
        "message": "Order status updated successfully.",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
    }


# =========================================================
# UPDATE RISK
# =========================================================

@router.patch("/{order_id}/risk")
def update_order_risk(
    order_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if "risk_score" not in data:
        raise HTTPException(
            status_code=400,
            detail="Risk score is required.",
        )

    try:
        risk_score = float(
            data["risk_score"]
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Risk score must be a valid number.",
        )

    if risk_score < 0 or risk_score > 100:
        raise HTTPException(
            status_code=400,
            detail="Risk score must be between 0 and 100.",
        )

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    order.risk_score = risk_score
    order.risk_level = risk_level

    if risk_level == "high":
        order.status = "human_audit"

    db.commit()
    db.refresh(order)

    return {
        "message": "Order risk updated successfully.",
        "order_id": order.id,
        "order_number": order.order_number,
        "risk_score": order.risk_score,
        "risk_level": order.risk_level,
        "status": order.status,
    }


# =========================================================
# CANCEL ORDER
# =========================================================

@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if order.status in {
        "completed",
        "refunded",
        "cancelled",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Order cannot be cancelled "
                f"because its status is "
                f"'{order.status}'."
            ),
        )

    order.status = "cancelled"

    db.commit()
    db.refresh(order)

    return {
        "message": "Order cancelled successfully.",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
    }


# =========================================================
# REFUND ORDER
# =========================================================

@router.post("/{order_id}/refund")
def refund_order(
    order_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if order.status == "refunded":
        raise HTTPException(
            status_code=400,
            detail="This order has already been refunded.",
        )

    refund_amount = data.get(
        "refund_amount",
        order.total_amount,
    )

    try:
        refund_amount = float(
            refund_amount
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Refund amount must be a valid number.",
        )

    if refund_amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Refund amount cannot be negative.",
        )

    if refund_amount > order.total_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                "Refund amount cannot be greater "
                "than the order total."
            ),
        )

    order.refund_amount = refund_amount
    order.status = "refunded"

    db.commit()
    db.refresh(order)

    return {
        "message": "Order refunded successfully.",
        "order_id": order.id,
        "order_number": order.order_number,
        "refund_amount": order.refund_amount,
        "status": order.status,
    }


# =========================================================
# DELETE ORDER
# =========================================================

@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if order.status in {
        "completed",
        "refunded",
        "fulfillment",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "This order cannot be permanently deleted "
                "because it is already in processing or "
                "has financial history."
            ),
        )

    # Return stock before deleting
    for item in order.items:

        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .first()
        )

        if product:
            product.stock_quantity += item.quantity

    db.delete(order)
    db.commit()

    return {
        "message": "Order deleted successfully.",
        "order_id": order_id,
    }