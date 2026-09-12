from sqlalchemy.orm import Session

from app.database.models import (
    AgentEvent,
    Order,
    Product,
)

from app.agents.resolution_agent import resolve_order


# =========================================================
# RISK ANALYSIS AGENT
# =========================================================

def analyze_order_risk(
    db: Session,
    order: Order,
) -> dict:

    risk_score = 0
    reasons = []

    if order.total_amount >= 10000:
        risk_score += 30
        reasons.append("High order value.")

    elif order.total_amount >= 5000:
        risk_score += 15
        reasons.append("Medium-high order value.")

    total_quantity = sum(
        item.quantity
        for item in order.items
    )

    if total_quantity >= 50:
        risk_score += 30
        reasons.append("Large order quantity.")

    elif total_quantity >= 20:
        risk_score += 15
        reasons.append("Above-normal order quantity.")

    if risk_score >= 60:
        risk_level = "high"

    elif risk_score >= 30:
        risk_level = "medium"

    else:
        risk_level = "low"

    order.risk_score = risk_score
    order.risk_level = risk_level

    message = (
        f"Risk analysis completed. "
        f"Score: {risk_score}. "
        f"Level: {risk_level}."
    )

    if reasons:
        message += " Reasons: " + " ".join(reasons)

    event = AgentEvent(
        order_id=order.id,
        node_name="RiskAnalysisAgent",
        event_type="risk_analysis",
        message=message,
        status="completed",
    )

    db.add(event)
    db.commit()
    db.refresh(order)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reasons": reasons,
    }


# =========================================================
# INVENTORY AGENT
# =========================================================

def check_order_inventory(
    db: Session,
    order: Order,
) -> dict:

    inventory_ok = True
    problems = []

    for item in order.items:

        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .first()
        )

        if not product:
            inventory_ok = False
            problems.append(
                f"Product {item.product_id} does not exist."
            )
            continue

        if not product.is_active:
            inventory_ok = False
            problems.append(
                f"{product.name} is inactive."
            )
            continue

        if product.stock_quantity < item.quantity:
            inventory_ok = False
            problems.append(
                f"{product.name}: requested "
                f"{item.quantity}, available "
                f"{product.stock_quantity}."
            )

    if inventory_ok:
        message = "Inventory check passed successfully."
        event_status = "completed"

    else:
        message = (
            "Inventory check failed. "
            + " ".join(problems)
        )
        event_status = "failed"

    event = AgentEvent(
        order_id=order.id,
        node_name="InventoryAgent",
        event_type="inventory_check",
        message=message,
        status=event_status,
    )

    db.add(event)
    db.commit()

    return {
        "inventory_ok": inventory_ok,
        "problems": problems,
    }


# =========================================================
# ORDER DECISION AGENT
# =========================================================

def make_order_decision(
    db: Session,
    order: Order,
    inventory_result: dict,
    risk_result: dict,
) -> dict:

    inventory_ok = inventory_result["inventory_ok"]
    risk_level = risk_result["risk_level"]

    if not inventory_ok:

        decision = "inventory_review"
        message = "Order requires inventory review."

    elif risk_level == "high":

        decision = "manual_review"
        message = "High-risk order requires manual review."

    elif risk_level == "medium":

        decision = "review"
        message = "Medium-risk order flagged for review."

    else:

        decision = "approved"
        message = "Order passed automated checks."

    # Keep pending until ResolutionAgent decides
    order.status = "pending"

    event = AgentEvent(
        order_id=order.id,
        node_name="OrderDecisionAgent",
        event_type="order_decision",
        message=message,
        status="completed",
    )

    db.add(event)
    db.commit()
    db.refresh(order)

    return {
        "decision": decision,
        "status": order.status,
        "message": message,
    }


# =========================================================
# COMPLETE ORDER PROCESSING
# =========================================================

def process_order(
    db: Session,
    order: Order,
) -> dict:

    # -----------------------------------------------------
    # AGENT 1 — RISK
    # -----------------------------------------------------

    risk_result = analyze_order_risk(
        db=db,
        order=order,
    )

    # -----------------------------------------------------
    # AGENT 2 — INVENTORY
    # -----------------------------------------------------

    inventory_result = check_order_inventory(
        db=db,
        order=order,
    )

    # -----------------------------------------------------
    # AGENT 3 — DECISION
    # -----------------------------------------------------

    decision_result = make_order_decision(
        db=db,
        order=order,
        inventory_result=inventory_result,
        risk_result=risk_result,
    )

    # -----------------------------------------------------
    # AGENT 4 — RESOLUTION
    # -----------------------------------------------------

    resolution_result = resolve_order(
        db=db,
        order=order,
        decision_result=decision_result,
    )

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    return {
        "order_id": order.id,
        "order_number": order.order_number,

        "risk": risk_result,

        "inventory": inventory_result,

        "decision": decision_result,

        "resolution": resolution_result,
    }