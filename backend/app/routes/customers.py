from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Customer


router = APIRouter(
    prefix="/api/customers",
    tags=["Customers"],
)


# =========================================================
# CREATE CUSTOMER
# =========================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_customer(
    data: dict,
    db: Session = Depends(get_db),
):
    name = str(data.get("name", "")).strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Customer name is required.",
        )

    email = data.get("email")
    phone = data.get("phone")
    address = data.get("address")

    if email:
        email = str(email).strip().lower()

    if phone:
        phone = str(phone).strip()

    if address:
        address = str(address).strip()

    # Check duplicate email
    if email:
        existing = (
            db.query(Customer)
            .filter(Customer.email == email)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="A customer with this email already exists.",
            )

    customer = Customer(
        name=name,
        email=email,
        phone=phone,
        address=address,
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return {
        "message": "Customer created successfully.",
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
        },
    }


# =========================================================
# GET ALL CUSTOMERS
# =========================================================

@router.get("/")
def get_customers(
    db: Session = Depends(get_db),
):
    customers = (
        db.query(Customer)
        .order_by(Customer.id.desc())
        .all()
    )

    return [
        {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
        }
        for customer in customers
    ]


# =========================================================
# GET SINGLE CUSTOMER
# =========================================================

@router.get("/{customer_id}")
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
    }


# =========================================================
# UPDATE CUSTOMER
# =========================================================

@router.put("/{customer_id}")
def update_customer(
    customer_id: int,
    data: dict,
    db: Session = Depends(get_db),
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    if "name" in data:
        name = str(data.get("name", "")).strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Customer name is required.",
            )

        customer.name = name

    if "email" in data:
        email = data.get("email")

        if email:
            email = str(email).strip().lower()

            existing = (
                db.query(Customer)
                .filter(
                    Customer.email == email,
                    Customer.id != customer_id,
                )
                .first()
            )

            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="Another customer already uses this email.",
                )

        customer.email = email

    if "phone" in data:
        customer.phone = data.get("phone")

    if "address" in data:
        customer.address = data.get("address")

    db.commit()
    db.refresh(customer)

    return {
        "message": "Customer updated successfully.",
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
        },
    }


# =========================================================
# DELETE CUSTOMER
# =========================================================

@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    # Customer ke orders hain to delete na karein
    if customer.orders:
        raise HTTPException(
            status_code=400,
            detail=(
                "Customer cannot be deleted because "
                "orders already exist for this customer."
            ),
        )

    db.delete(customer)
    db.commit()

    return {
        "message": "Customer deleted successfully.",
        "customer_id": customer_id,
    }