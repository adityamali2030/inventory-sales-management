import pytest
from fastapi.testclient import TestClient

import database
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Redirect database connections to a temporary test file.
    test_database = tmp_path / "test_inventory.db"
    monkeypatch.setattr(database, "DATABASE_PATH", test_database)

    # Create empty tables in the temporary database.
    database.create_tables()

    with TestClient(app) as test_client:
        yield test_client


def test_create_and_read_product(client):
    response = client.post(
        "/products",
        json={
            "product_name": "Test Keyboard",
            "price_paise": 75000,
            "stock_quantity": 10,
        },
    )

    assert response.status_code == 201

    product = response.json()
    product_id = product["product_id"]

    assert product["product_name"] == "Test Keyboard"

    response = client.get(f"/products/{product_id}")

    assert response.status_code == 200
    assert response.json() == {
        "product_id": product_id,
        "product_name": "Test Keyboard",
        "price_paise": 75000,
        "stock_quantity": 10,
    }


def test_order_reduces_stock(client):
    product_response = client.post(
        "/products",
        json={
            "product_name": "Test Keyboard",
            "price_paise": 75000,
            "stock_quantity": 10,
        },
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["product_id"]

    customer_response = client.post(
        "/customers",
        json={
            "customer_name": "Test Customer",
            "phone": None,
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["customer_id"]

    order_response = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
        },
    )

    assert order_response.status_code == 201
    assert order_response.json()["total_paise"] == 150000

    product_response = client.get(f"/products/{product_id}")

    assert product_response.status_code == 200
    assert product_response.json()["stock_quantity"] == 8

    summary_response = client.get("/reports/sales-summary")

    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "total_orders": 1,
        "total_units_sold": 2,
        "total_revenue_paise": 150000,
    }


def test_failed_order_rolls_back_all_changes(client):
    product_ids = []

    for name, stock in [("Keyboard", 10), ("Mouse", 1)]:
        response = client.post(
            "/products",
            json={
                "product_name": name,
                "price_paise": 50000,
                "stock_quantity": stock,
            },
        )
        assert response.status_code == 201
        product_ids.append(response.json()["product_id"])

    response = client.post(
        "/customers",
        json={"customer_name": "Test Customer", "phone": None},
    )
    assert response.status_code == 201
    customer_id = response.json()["customer_id"]

    # The first item has enough stock; the second does not.
    response = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product_ids[0], "quantity": 2},
                {"product_id": product_ids[1], "quantity": 2},
            ],
        },
    )

    assert response.status_code == 409

    for product_id, expected_stock in zip(product_ids, [10, 1]):
        response = client.get(f"/products/{product_id}")
        assert response.status_code == 200
        assert response.json()["stock_quantity"] == expected_stock

    response = client.get("/orders")
    assert response.status_code == 200
    assert response.json() == []

    # Check both tables directly for leftover rows.
    connection = database.get_connection()

    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0] == 0

        assert connection.execute(
            "SELECT COUNT(*) FROM order_items"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_negative_stock_is_rejected(client):
    response = client.post(
        "/products",
        json={
            "product_name": "Test Keyboard",
            "price_paise": 75000,
            "stock_quantity": 10,
        },
    )
    assert response.status_code == 201
    product_id = response.json()["product_id"]

    response = client.patch(
        f"/products/{product_id}/stock",
        json={"stock_quantity": -5},
    )

    assert response.status_code == 422

    response = client.get(f"/products/{product_id}")

    assert response.status_code == 200
    assert response.json()["stock_quantity"] == 10


def test_missing_product_returns_404(client):
    response = client.get("/products/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
