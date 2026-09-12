from datetime import datetime, date, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.agents.order_agent import process_order
from app.agents.fulfillment_agent import process_fulfillment
from app.core.security import decode_access_token
from app.database.database import get_db
from app.database.models import (
    AgentEvent,
    Customer,
    Order,
    OrderItem,
    Product,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/api/agents",
    tags=["AI Agents"],
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
# AI QUERY SCHEMA
# =========================================================

class AIQueryRequest(BaseModel):
    query: str


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def money(value) -> float:
    return round(float(value or 0), 2)


def money_text(value) -> str:
    return (
        f"Rs. {money(value):,.2f}"
    )


def order_date_text(value) -> str:
    if not value:
        return "N/A"

    return value.strftime("%d %b %Y")


def order_time_text(value) -> str:
    if not value:
        return "N/A"

    return value.strftime("%d %b %Y %I:%M %p")


def get_today_range():
    today = date.today()

    start = datetime.combine(
        today,
        time.min,
    )

    end = start + timedelta(days=1)

    return start, end


def calculate_outstanding(order):
    total = money(order.total_amount)
    recovered = money(order.recovered_amount)

    return max(
        total - recovered,
        0,
    )


# =========================================================
# CUSTOMER INTELLIGENCE
# =========================================================

def get_customer_report(
    db: Session,
    customer_id: int,
) -> dict:

    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail=f"Customer #{customer_id} not found.",
        )

    orders = (
        db.query(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
        )
        .filter(
            Order.customer_id == customer.id
        )
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    total_orders = len(orders)

    completed_orders = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "completed",
            "complete",
            "fulfilled",
        ]
    )

    pending_orders = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "pending",
            "review",
            "manual_review",
            "inventory_review",
        ]
    )

    cancelled_orders = sum(
        1
        for order in orders
        if str(order.status).lower()
        == "cancelled"
    )

    total_sales = sum(
        money(order.total_amount)
        for order in orders
    )

    total_recovered = sum(
        money(order.recovered_amount)
        for order in orders
    )

    total_refunds = sum(
        money(order.refund_amount)
        for order in orders
    )

    outstanding = max(
        total_sales - total_recovered,
        0,
    )

    total_items = sum(
        int(item.quantity or 0)
        for order in orders
        for item in order.items
    )

    high_risk_orders = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "high"
    )

    medium_risk_orders = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "medium"
    )

    low_risk_orders = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "low"
    )

    recent_orders = []

    for order in orders[:10]:

        items = []

        for item in order.items:

            product_name = (
                item.product.name
                if item.product
                else f"Product #{item.product_id}"
            )

            items.append(
                {
                    "product_id": item.product_id,
                    "product_name": product_name,
                    "quantity": item.quantity,
                    "unit_price": money(
                        item.unit_price
                    ),
                    "line_total": money(
                        item.quantity
                        * item.unit_price
                    ),
                }
            )

        recent_orders.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "date": order_date_text(
                    order.created_at
                ),
                "status": order.status,
                "risk_score": money(
                    order.risk_score
                ),
                "risk_level": order.risk_level,
                "total_amount": money(
                    order.total_amount
                ),
                "recovered_amount": money(
                    order.recovered_amount
                ),
                "outstanding_amount": calculate_outstanding(
                    order
                ),
                "refund_amount": money(
                    order.refund_amount
                ),
                "items": items,
            }
        )

    return {
        "type": "customer_report",
        "title": "Customer Intelligence Report",

        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
            "created_at": order_date_text(
                customer.created_at
            ),
        },

        "order_performance": {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "pending_orders": pending_orders,
            "cancelled_orders": cancelled_orders,
        },

        "financial_performance": {
            "total_sales": total_sales,
            "total_recovered": total_recovered,
            "outstanding": outstanding,
            "total_refunds": total_refunds,
        },

        "risk_profile": {
            "high_risk_orders": high_risk_orders,
            "medium_risk_orders": medium_risk_orders,
            "low_risk_orders": low_risk_orders,
        },

        "activity": {
            "total_items_ordered": total_items,
            "last_order": (
                recent_orders[0]
                if recent_orders
                else None
            ),
        },

        "recent_orders": recent_orders,

        "ai_summary": (
            f"Customer #{customer.id} "
            f"{customer.name} has "
            f"{total_orders} total orders with "
            f"{money_text(total_sales)} in total sales. "
            f"{money_text(total_recovered)} has been recovered "
            f"and the current outstanding amount is "
            f"{money_text(outstanding)}."
        ),
    }


# =========================================================
# TODAY'S BUSINESS REPORT
# =========================================================

def get_today_report(
    db: Session,
) -> dict:

    start, end = get_today_range()

    orders = (
        db.query(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.items)
            .joinedload(OrderItem.product),
        )
        .filter(
            Order.created_at >= start,
            Order.created_at < end,
        )
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    total_orders = len(orders)

    total_sales = sum(
        money(order.total_amount)
        for order in orders
    )

    total_recovered = sum(
        money(order.recovered_amount)
        for order in orders
    )

    total_refunds = sum(
        money(order.refund_amount)
        for order in orders
    )

    outstanding = max(
        total_sales - total_recovered,
        0,
    )

    completed = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "completed",
            "complete",
            "fulfilled",
        ]
    )

    pending = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "pending",
            "review",
            "manual_review",
            "inventory_review",
        ]
    )

    cancelled = sum(
        1
        for order in orders
        if str(order.status).lower()
        == "cancelled"
    )

    approved = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "approved",
            "fulfillment_ready",
        ]
    )

    high_risk = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "high"
    )

    medium_risk = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "medium"
    )

    low_risk = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "low"
    )

    customer_ids = {
        order.customer_id
        for order in orders
    }

    product_quantity = {}

    for order in orders:

        for item in order.items:

            product_name = (
                item.product.name
                if item.product
                else f"Product #{item.product_id}"
            )

            product_quantity[product_name] = (
                product_quantity.get(
                    product_name,
                    0,
                )
                + int(item.quantity or 0)
            )

    top_product = None

    if product_quantity:

        top_product = max(
            product_quantity.items(),
            key=lambda item: item[1],
        )

    order_list = []

    for order in orders:

        order_list.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "customer_name": (
                    order.customer.name
                    if order.customer
                    else "Unknown"
                ),
                "date": order_time_text(
                    order.created_at
                ),
                "status": order.status,
                "risk_score": money(
                    order.risk_score
                ),
                "risk_level": order.risk_level,
                "total_amount": money(
                    order.total_amount
                ),
                "recovered_amount": money(
                    order.recovered_amount
                ),
                "outstanding_amount": calculate_outstanding(
                    order
                ),
                "refund_amount": money(
                    order.refund_amount
                ),
            }
        )

    return {
        "type": "today_report",
        "title": "Today's Business Intelligence Report",
        "date": date.today().isoformat(),

        "sales": {
            "total_sales": money(total_sales),
            "recovered": money(total_recovered),
            "outstanding": money(outstanding),
            "refunds": money(total_refunds),
        },

        "orders": {
            "total": total_orders,
            "completed": completed,
            "approved": approved,
            "pending": pending,
            "cancelled": cancelled,
        },

        "risk": {
            "high": high_risk,
            "medium": medium_risk,
            "low": low_risk,
        },

        "customers": {
            "customers_served": len(
                customer_ids
            ),
        },

        "top_product": (
            {
                "name": top_product[0],
                "quantity": top_product[1],
            }
            if top_product
            else None
        ),

        "orders_list": order_list,

        "ai_summary": (
            f"Today there are {total_orders} orders "
            f"with total sales of "
            f"{money_text(total_sales)}. "
            f"{money_text(total_recovered)} has been recovered "
            f"and {money_text(outstanding)} remains outstanding. "
            f"There are {pending} pending orders and "
            f"{high_risk} high-risk orders."
        ),
    }


# =========================================================
# TODAY'S SALES
# =========================================================

def get_today_sales(
    db: Session,
) -> dict:

    report = get_today_report(db)

    sales = report["sales"]
    orders = report["orders"]

    return {
        "type": "sales_report",
        "title": "Today's Sales Report",

        "date": report["date"],

        "total_orders": orders["total"],

        "total_sales": sales["total_sales"],

        "recovered": sales["recovered"],

        "outstanding": sales["outstanding"],

        "refunds": sales["refunds"],

        "completed_orders": orders["completed"],

        "pending_orders": orders["pending"],

        "cancelled_orders": orders["cancelled"],

        "ai_summary": (
            f"Today's sales are "
            f"{money_text(sales['total_sales'])}. "
            f"Recovered amount is "
            f"{money_text(sales['recovered'])}, "
            f"while outstanding amount is "
            f"{money_text(sales['outstanding'])}."
        ),
    }


# =========================================================
# ORDER LIST REPORT
# =========================================================

def get_order_list_report(
    db: Session,
    only_today: bool = False,
    status_filter: str | None = None,
    risk_filter: str | None = None,
) -> dict:

    query = (
        db.query(Order)
        .options(
            joinedload(Order.customer),
        )
    )

    if only_today:

        start, end = get_today_range()

        query = query.filter(
            Order.created_at >= start,
            Order.created_at < end,
        )

    if status_filter:

        query = query.filter(
            func.lower(Order.status)
            == status_filter.lower()
        )

    if risk_filter:

        query = query.filter(
            func.lower(Order.risk_level)
            == risk_filter.lower()
        )

    orders = (
        query
        .order_by(
            Order.created_at.desc()
        )
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
                    else "Unknown"
                ),
                "date": order_time_text(
                    order.created_at
                ),
                "status": order.status,
                "risk_score": money(
                    order.risk_score
                ),
                "risk_level": order.risk_level,
                "total_amount": money(
                    order.total_amount
                ),
                "recovered_amount": money(
                    order.recovered_amount
                ),
                "outstanding_amount": calculate_outstanding(
                    order
                ),
                "refund_amount": money(
                    order.refund_amount
                ),
            }
        )

    return {
        "type": "order_list",
        "total": len(result),
        "orders": result,
    }


# =========================================================
# INVENTORY REPORT
# =========================================================

def get_inventory_report(
    db: Session,
) -> dict:

    products = (
        db.query(Product)
        .order_by(
            Product.stock_quantity.asc()
        )
        .all()
    )

    low_stock = []
    out_of_stock = []
    all_products = []

    for product in products:

        item = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "price": money(product.price),
            "stock_quantity": product.stock_quantity,
            "is_active": product.is_active,
        }

        all_products.append(item)

        if product.stock_quantity <= 0:

            out_of_stock.append(item)

        elif product.stock_quantity <= 10:

            low_stock.append(item)

    return {
        "type": "inventory_report",
        "title": "Inventory Intelligence Report",

        "total_products": len(products),

        "active_products": sum(
            1
            for product in products
            if product.is_active
        ),

        "low_stock_count": len(
            low_stock
        ),

        "out_of_stock_count": len(
            out_of_stock
        ),

        "low_stock": low_stock,

        "out_of_stock": out_of_stock,

        "products": all_products,
    }


# =========================================================
# BUSINESS SUMMARY
# =========================================================

def get_business_summary(
    db: Session,
) -> dict:

    orders = db.query(Order).all()

    customers_count = (
        db.query(Customer).count()
    )

    products_count = (
        db.query(Product).count()
    )

    active_products = (
        db.query(Product)
        .filter(
            Product.is_active == True
        )
        .count()
    )

    total_sales = sum(
        money(order.total_amount)
        for order in orders
    )

    recovered = sum(
        money(order.recovered_amount)
        for order in orders
    )

    refunds = sum(
        money(order.refund_amount)
        for order in orders
    )

    outstanding = max(
        total_sales - recovered,
        0,
    )

    high_risk = sum(
        1
        for order in orders
        if str(order.risk_level).lower()
        == "high"
    )

    pending = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "pending",
            "review",
            "manual_review",
            "inventory_review",
        ]
    )

    completed = sum(
        1
        for order in orders
        if str(order.status).lower()
        in [
            "completed",
            "complete",
            "fulfilled",
        ]
    )

    return {
        "type": "business_summary",
        "title": "OrderOps AI Executive Business Summary",

        "customers": customers_count,

        "products": {
            "total": products_count,
            "active": active_products,
        },

        "orders": {
            "total": len(orders),
            "completed": completed,
            "pending": pending,
            "high_risk": high_risk,
        },

        "financials": {
            "total_sales": money(total_sales),
            "recovered": money(recovered),
            "outstanding": money(outstanding),
            "refunds": money(refunds),
        },

        "ai_summary": (
            f"OrderOps AI currently has "
            f"{customers_count} customers and "
            f"{len(orders)} total orders. "
            f"Total sales are "
            f"{money_text(total_sales)}, "
            f"with {money_text(recovered)} recovered "
            f"and {money_text(outstanding)} outstanding. "
            f"There are {high_risk} high-risk orders "
            f"and {pending} orders requiring attention."
        ),
    }


# =========================================================
# AI QUERY INTERPRETER
# =========================================================

def process_ai_query(
    db: Session,
    query: str,
) -> dict:

    original_query = str(
        query or ""
    ).strip()

    normalized = (
        original_query
        .lower()
        .strip()
    )

    if not normalized:

        raise HTTPException(
            status_code=400,
            detail="Please enter an AI query.",
        )

    # -----------------------------------------------------
    # PURE CUSTOMER ID
    # Example: 25
    # -----------------------------------------------------

    if normalized.isdigit():

        customer_id = int(normalized)

        result = get_customer_report(
            db=db,
            customer_id=customer_id,
        )

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # CUSTOMER ID + WORDS
    # Examples:
    # 25 details
    # customer 25
    # customer id 25
    # 25 orders
    # -----------------------------------------------------

    import re

    customer_match = re.search(
        r"(?:customer\s*(?:id|#)?\s*|#)?(\d+)",
        normalized,
    )

    if customer_match:

        customer_id = int(
            customer_match.group(1)
        )

        customer_keywords = [
            "customer",
            "details",
            "detail",
            "profile",
            "information",
            "info",
        ]

        order_keywords = [
            "orders",
            "order history",
            "purchases",
            "purchase history",
        ]

        if any(
            keyword in normalized
            for keyword in customer_keywords
        ):

            result = get_customer_report(
                db=db,
                customer_id=customer_id,
            )

            result["query"] = original_query

            return result

        if any(
            keyword in normalized
            for keyword in order_keywords
        ):

            customer_report = get_customer_report(
                db=db,
                customer_id=customer_id,
            )

            return {
                "type": "customer_orders",
                "title": (
                    f"Order History — "
                    f"Customer #{customer_id}"
                ),
                "query": original_query,
                "customer": customer_report[
                    "customer"
                ],
                "orders": customer_report[
                    "recent_orders"
                ],
                "total_orders": customer_report[
                    "order_performance"
                ]["total_orders"],
            }

    # -----------------------------------------------------
    # TODAY
    # -----------------------------------------------------

    if (
        normalized in [
            "today",
            "today report",
            "today summary",
            "daily report",
            "daily summary",
        ]
        or "today business" in normalized
    ):

        result = get_today_report(db)

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # TODAY SALES
    # -----------------------------------------------------

    if (
        "today sales" in normalized
        or "today sale" in normalized
        or "today revenue" in normalized
    ):

        result = get_today_sales(db)

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # TODAY ORDERS
    # -----------------------------------------------------

    if (
        "today orders" in normalized
        or "today order" in normalized
    ):

        result = get_order_list_report(
            db=db,
            only_today=True,
        )

        result["title"] = (
            "Today's Order Report"
        )

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # PENDING ORDERS
    # -----------------------------------------------------

    if (
        "pending orders" in normalized
        or "pending order" in normalized
        or normalized == "pending"
    ):

        result = get_order_list_report(
            db=db,
            status_filter="pending",
        )

        result["title"] = (
            "Pending Orders Report"
        )

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # HIGH RISK
    # -----------------------------------------------------

    if (
        "high risk" in normalized
        or "high-risk" in normalized
        or "high risk orders" in normalized
    ):

        result = get_order_list_report(
            db=db,
            risk_filter="high",
        )

        result["title"] = (
            "High-Risk Orders Report"
        )

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # MEDIUM RISK
    # -----------------------------------------------------

    if (
        "medium risk" in normalized
        or "medium-risk" in normalized
    ):

        result = get_order_list_report(
            db=db,
            risk_filter="medium",
        )

        result["title"] = (
            "Medium-Risk Orders Report"
        )

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # INVENTORY
    # -----------------------------------------------------

    if (
        "inventory" in normalized
        or "stock" in normalized
        or "products" in normalized
        or "product stock" in normalized
    ):

        result = get_inventory_report(db)

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # BUSINESS SUMMARY
    # -----------------------------------------------------

    if (
        "business summary" in normalized
        or "business report" in normalized
        or "overall business" in normalized
        or "executive summary" in normalized
        or normalized == "summary"
    ):

        result = get_business_summary(db)

        result["query"] = original_query

        return result

    # -----------------------------------------------------
    # SALES / REVENUE
    # -----------------------------------------------------

    if (
        normalized == "sales"
        or "total sales" in normalized
        or "total revenue" in normalized
        or normalized == "revenue"
    ):

        result = get_business_summary(db)

        return {
            "type": "sales_summary",
            "title": "Sales & Revenue Summary",
            "query": original_query,
            "financials": result[
                "financials"
            ],
            "ai_summary": (
                f"Total sales are "
                f"{money_text(result['financials']['total_sales'])}. "
                f"Recovered amount is "
                f"{money_text(result['financials']['recovered'])}. "
                f"Outstanding amount is "
                f"{money_text(result['financials']['outstanding'])}."
            ),
        }

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    return {
        "type": "help",
        "title": "OrderOps AI Assistant",
        "query": original_query,

        "message": (
            "I could not identify the requested report."
        ),

        "supported_queries": [
            "25",
            "25 details",
            "25 orders",
            "today",
            "today sales",
            "today orders",
            "pending orders",
            "high risk orders",
            "medium risk orders",
            "inventory",
            "sales",
            "business summary",
        ],
    }


# =========================================================
# AI BUSINESS QUERY ENDPOINT
# =========================================================

@router.post("/query")
def ai_business_query(
    request: AIQueryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    """
    Ask OrderOps AI for customer, order,
    sales, inventory and business intelligence.
    """

    result = process_ai_query(
        db=db,
        query=request.query,
    )

    return {
        "success": True,
        "assistant": "OrderOps AI",
        "result": result,
    }


# =========================================================
# PROCESS ORDER WITH AI
# =========================================================

@router.post("/orders/{order_id}/process")
def process_order_with_agents(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    """
    Run complete OrderOps AI processing pipeline.
    """

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

    result = process_order(
        db=db,
        order=order,
    )

    return {
        "message": (
            "Order processed successfully "
            "by OrderOps AI."
        ),
        "result": result,
    }


# =========================================================
# FULFILL ORDER
# =========================================================

@router.post("/orders/{order_id}/fulfill")
def fulfill_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    """
    Move an AI-approved order into fulfillment.
    """

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

    result = process_fulfillment(
        db=db,
        order=order,
    )

    return {
        "message": (
            "Fulfillment Agent processed "
            "the order."
        ),
        "result": result,
    }


# =========================================================
# GET ORDER AGENT EVENTS
# =========================================================

@router.get("/orders/{order_id}/events")
def get_order_agent_events(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_authenticated_user),
):
    """
    Get all AI agent events for an order.
    """

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

    events = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.order_id == order_id
        )
        .order_by(
            AgentEvent.id.asc()
        )
        .all()
    )

    return [
        {
            "id": event.id,
            "node_name": event.node_name,
            "event_type": event.event_type,
            "message": event.message,
            "status": event.status,
            "created_at": event.created_at,
        }
        for event in events
    ]