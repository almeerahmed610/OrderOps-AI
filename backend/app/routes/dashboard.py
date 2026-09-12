from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.database.models import (
    AgentEvent,
    Customer,
    Order,
    Product,
)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)

security = HTTPBearer()


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = decode_access_token(
        credentials.credentials
    )

    if not payload:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return payload


@router.get("/")
def dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    # =====================================================
    # ORDERS
    # =====================================================

    orders = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .all()
    )

    total_orders = len(orders)

    ai_approved = sum(
        1
        for order in orders
        if order.status in [
            "approved",
            "fulfillment_ready",
            "completed",
        ]
    )

    manual_review = sum(
        1
        for order in orders
        if order.status in [
            "review",
            "manual_review",
            "inventory_review",
        ]
    )

    high_risk = sum(
        1
        for order in orders
        if order.risk_level == "high"
    )

    # =====================================================
    # CUSTOMERS
    # =====================================================

    total_customers = (
        db.query(Customer).count()
    )

    # =====================================================
    # PRODUCTS
    # =====================================================

    total_products = (
        db.query(Product)
        .filter(Product.is_active == True)
        .count()
    )

    low_stock = (
        db.query(Product)
        .filter(
            Product.is_active == True,
            Product.stock_quantity <= 10,
        )
        .count()
    )

    # =====================================================
    # REVENUE
    # =====================================================

    total_revenue = sum(
        order.total_amount or 0
        for order in orders
    )

    recovered_amount = sum(
        order.recovered_amount or 0
        for order in orders
    )

    refund_amount = sum(
        order.refund_amount or 0
        for order in orders
    )

    # =====================================================
    # RECENT ORDERS
    # =====================================================

    recent_orders = []

    for order in orders[:10]:

        customer_name = "Unknown Customer"

        if order.customer:
            customer_name = order.customer.name

        recent_orders.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": customer_name,
                "amount": order.total_amount or 0,
                "risk_score": order.risk_score or 0,
                "risk_level": order.risk_level or "low",
                "status": order.status,
                "created_at": order.created_at,
            }
        )

    # =====================================================
    # AI ACTIVITY
    # =====================================================

    events = (
        db.query(AgentEvent)
        .order_by(
            AgentEvent.created_at.desc()
        )
        .limit(12)
        .all()
    )

    ai_activity = []

    for event in events:

        ai_activity.append(
            {
                "id": event.id,
                "order_id": event.order_id,
                "node_name": event.node_name,
                "event_type": event.event_type,
                "message": event.message,
                "status": event.status,
                "created_at": event.created_at,
            }
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "stats": {
            "total_orders": total_orders,
            "ai_approved": ai_approved,
            "manual_review": manual_review,
            "high_risk": high_risk,
            "total_customers": total_customers,
            "total_products": total_products,
            "low_stock_products": low_stock,
            "total_revenue": total_revenue,
            "recovered_amount": recovered_amount,
            "refund_amount": refund_amount,
        },
        "recent_orders": recent_orders,
        "ai_activity": ai_activity,
    }