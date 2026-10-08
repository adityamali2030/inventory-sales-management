from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator
from database import get_connection

app = FastAPI(
    title="Inventory and Sales Management API",
    description="A Python and SQL project for managing inventory and sales.",
    version="0.1.0",
)


class ProductCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=100)
    price_paise: int = Field(gt=0, strict=True)
    stock_quantity: int = Field(default=0, ge=0, strict=True)


@app.get("/")
def home():
    return {"message": "Inventory and Sales Management API is running"}


@app.post("/products", status_code=201)
def create_product(product: ProductCreate):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO products (
                product_name, price_paise, stock_quantity
            )
            VALUES (?, ?, ?)
            """,
            (
                product.product_name,
                product.price_paise,
                product.stock_quantity,
            ),
        )
        connection.commit()

        return {
            "product_id": cursor.lastrowid,
            **product.model_dump(),
        }
    finally:
        connection.close()


@app.get("/products")
def list_products():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT product_id, product_name, price_paise, stock_quantity
            FROM products
            ORDER BY product_id
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.get("/products/{product_id}")
def get_product(product_id: int = Path(gt=0)):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT product_id, product_name, price_paise, stock_quantity
            FROM products
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        return dict(row)
    finally:
        connection.close()


class StockUpdate(BaseModel):
    stock_quantity: int = Field(ge=0, strict=True)


@app.patch("/products/{product_id}/stock")
def update_stock(
    stock: StockUpdate,
    product_id: int = Path(gt=0),
):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE products
            SET stock_quantity = ?
            WHERE product_id = ?
            """,
            (stock.stock_quantity, product_id),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        connection.commit()

        return {
            "product_id": product_id,
            "stock_quantity": stock.stock_quantity,
            "message": "Stock updated successfully",
        }
    finally:
        connection.close()


class CustomerCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Customer name cannot be blank")

        return value


@app.post("/customers", status_code=201)
def create_customer(customer: CustomerCreate):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO customers (customer_name, phone)
            VALUES (?, ?)
            """,
            (customer.customer_name, customer.phone),
        )
        connection.commit()

        return {
            "customer_id": cursor.lastrowid,
            **customer.model_dump(),
        }
    finally:
        connection.close()


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0, strict=True)
    quantity: int = Field(gt=0, strict=True)


class OrderCreate(BaseModel):
    customer_id: int = Field(gt=0, strict=True)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def reject_duplicate_products(cls, items):
        product_ids = [item.product_id for item in items]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product must appear only once")

        return items


@app.post("/orders", status_code=201)
def create_order(order: OrderCreate):
    connection = get_connection()

    try:
        # Reserve the database write lock before checking stock.
        connection.execute("BEGIN IMMEDIATE")

        customer = connection.execute(
            "SELECT customer_id FROM customers WHERE customer_id = ?",
            (order.customer_id,),
        ).fetchone()

        if customer is None:
            raise HTTPException(404, "Customer not found")

        cursor = connection.execute(
            "INSERT INTO orders (customer_id) VALUES (?)",
            (order.customer_id,),
        )
        order_id = cursor.lastrowid
        total_paise = 0

        for item in order.items:
            product = connection.execute(
                """
                SELECT price_paise, stock_quantity
                FROM products
                WHERE product_id = ?
                """,
                (item.product_id,),
            ).fetchone()

            if product is None:
                raise HTTPException(
                    404, f"Product {item.product_id} not found"
                )

            if product["stock_quantity"] < item.quantity:
                raise HTTPException(
                    409,
                    f"Insufficient stock for product {item.product_id}",
                )

            unit_price = product["price_paise"]

            connection.execute(
                """
                INSERT INTO order_items (
                    order_id, product_id, quantity, unit_price_paise
                )
                VALUES (?, ?, ?, ?)
                """,
                (order_id, item.product_id, item.quantity, unit_price),
            )

            connection.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE product_id = ?
                """,
                (item.quantity, item.product_id),
            )

            total_paise += unit_price * item.quantity

        connection.commit()

        return {
            "order_id": order_id,
            "customer_id": order.customer_id,
            "total_paise": total_paise,
            "message": "Order created successfully",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.get("/orders")
def list_orders():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                o.order_id,
                o.customer_id,
                c.customer_name,
                o.created_at,
                oi.product_id,
                p.product_name,
                oi.quantity,
                oi.unit_price_paise,
                oi.quantity * oi.unit_price_paise AS line_total_paise
            FROM orders AS o
            JOIN customers AS c
                ON o.customer_id = c.customer_id
            JOIN order_items AS oi
                ON o.order_id = oi.order_id
            JOIN products AS p
                ON oi.product_id = p.product_id
            ORDER BY o.order_id, oi.order_item_id
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.get("/reports/sales-summary")
def sales_summary():
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                COUNT(DISTINCT order_id) AS total_orders,
                COALESCE(SUM(quantity), 0) AS total_units_sold,
                COALESCE(
                    SUM(quantity * unit_price_paise), 0
                ) AS total_revenue_paise
            FROM order_items
            """
        ).fetchone()

        return dict(row)
    finally:
        connection.close()


@app.get("/reports/low-stock")
def low_stock(threshold: int = Query(default=5, ge=0)):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT product_id, product_name, stock_quantity
            FROM products
            WHERE stock_quantity <= ?
            ORDER BY stock_quantity, product_id
            """,
            (threshold,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.get("/reports/product-sales")
def product_sales():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                p.product_id,
                p.product_name,
                COALESCE(SUM(oi.quantity), 0) AS units_sold,
                COALESCE(
                    SUM(oi.quantity * oi.unit_price_paise), 0
                ) AS revenue_paise
            FROM products AS p
            LEFT JOIN order_items AS oi
                ON p.product_id = oi.product_id
            GROUP BY p.product_id, p.product_name
            ORDER BY revenue_paise DESC, p.product_id
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()
