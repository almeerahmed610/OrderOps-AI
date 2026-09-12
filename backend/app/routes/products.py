from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Product

router = APIRouter(
    prefix="/api/products",
    tags=["Products"],
)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_product(
    data: dict,
    db: Session = Depends(get_db),
):
    sku = str(data.get("sku", "")).strip()
    name = str(data.get("name", "")).strip()

    if not sku:
        raise HTTPException(400, "SKU is required.")

    if not name:
        raise HTTPException(400, "Product name is required.")

    existing = db.query(Product).filter(Product.sku == sku).first()

    if existing:
        raise HTTPException(400, "Product with this SKU already exists.")

    product = Product(
        sku=sku,
        name=name,
        description=data.get("description"),
        price=float(data.get("price", 0)),
        stock_quantity=int(data.get("stock_quantity", 0)),
        is_active=data.get("is_active", True),
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "message": "Product created successfully.",
        "product": {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "is_active": product.is_active,
        },
    }


@router.get("/")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id.desc()).all()

    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "stock_quantity": p.stock_quantity,
            "is_active": p.is_active,
        }
        for p in products
    ]


@router.get("/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(404, "Product not found.")

    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(404, "Product not found.")

    db.delete(product)
    db.commit()

    return {
        "message": "Product deleted successfully."
    }