from sqlalchemy.orm import Session

from app.database.models import AgentEvent, Order


# =========================================================
# AI RESOLUTION AGENT
# =========================================================

def resolve_order(
    db: Session,
    order: Order,
    decision_result: dict,
) -> dict:
    """
    Decide the next operational action for an order
    based on the previous AI decision.
    """

    decision = decision_result.get("decision", "")

    # -----------------------------------------------------
    # APPROVED ORDER
    # -----------------------------------------------------

    if decision == "approved":

        resolution = "fulfillment_ready"

        message = (
            "Order approved by AI and marked ready "
            "for fulfillment."
        )

        order.status = "approved"

    # -----------------------------------------------------
    # MEDIUM RISK
    # -----------------------------------------------------

    elif decision == "review":

        resolution = "review_required"

        message = (
            "Order requires operational review "
            "before fulfillment."
        )

        order.status = "review"

    # -----------------------------------------------------
    # HIGH RISK
    # -----------------------------------------------------

    elif decision == "manual_review":

        resolution = "manual_review"

        message = (
            "High-risk order requires manual "
            "review before fulfillment."
        )

        order.status = "review"

    # -----------------------------------------------------
    # INVENTORY ISSUE
    # -----------------------------------------------------

    elif decision == "inventory_review":

        resolution = "inventory_review"

        message = (
            "Order requires inventory review "
            "before fulfillment."
        )

        order.status = "inventory_review"

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    else:

        resolution = "pending_review"

        message = (
            "Order could not be automatically resolved "
            "and requires review."
        )

        order.status = "pending"

    # -----------------------------------------------------
    # SAVE AI EVENT
    # -----------------------------------------------------

    event = AgentEvent(
        order_id=order.id,
        node_name="ResolutionAgent",
        event_type="order_resolution",
        message=message,
        status="completed",
    )

    db.add(event)

    db.commit()
    db.refresh(order)

    return {
        "resolution": resolution,
        "order_status": order.status,
        "message": message,
    }