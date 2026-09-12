from sqlalchemy.orm import Session

from app.database.models import AgentEvent, Order


# =========================================================
# FULFILLMENT AGENT
# =========================================================

def process_fulfillment(
    db: Session,
    order: Order,
) -> dict:
    """
    Process an AI-approved order for fulfillment.
    """

    # -----------------------------------------------------
    # ONLY APPROVED ORDERS CAN ENTER FULFILLMENT
    # -----------------------------------------------------

    if order.status != "approved":

        message = (
            f"Order cannot enter fulfillment. "
            f"Current status: {order.status}."
        )

        event = AgentEvent(
            order_id=order.id,
            node_name="FulfillmentAgent",
            event_type="fulfillment_blocked",
            message=message,
            status="failed",
        )

        db.add(event)
        db.commit()

        return {
            "success": False,
            "fulfillment_status": "blocked",
            "order_status": order.status,
            "message": message,
        }

    # -----------------------------------------------------
    # FULFILLMENT READY
    # -----------------------------------------------------

    order.status = "fulfillment_ready"

    message = (
        "Order approved successfully and moved "
        "to fulfillment."
    )

    event = AgentEvent(
        order_id=order.id,
        node_name="FulfillmentAgent",
        event_type="fulfillment_started",
        message=message,
        status="completed",
    )

    db.add(event)

    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "fulfillment_status": "ready",
        "order_status": order.status,
        "message": message,
    }