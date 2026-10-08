# Inventory and Sales Management API

A Python and SQL backend project built with FastAPI and SQLite.
It manages products, customers, stock, and sales orders, with
SQL-based reporting and automated tests.

## Technologies

- Python 3.13
- FastAPI
- SQLite
- Pydantic
- pytest and FastAPI TestClient

## Features

- Create and list products
- Retrieve a product by ID
- Update stock quantities
- Create customers
- Create orders containing multiple products
- Reduce stock when an order succeeds
- Reject orders with insufficient stock
- Roll back the entire order if any item fails
- View order-item history
- Generate sales summary, low-stock, and product-sales reports

## Database Design

- customers: customer details
- products: product prices and current stock
- orders: customer and order timestamp
- order_items: products, quantities, and sale-time prices

Relationships:

- One customer can have many orders.
- One order can contain many order items.
- One product can appear in many order items.

Prices are stored as integer paise to avoid floating-point
rounding issues. For example, 75000 paise represents INR 750.

## Setup

Run these commands from the project folder on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python database.py
python -m uvicorn main:app --reload
```

Open the interactive API documentation:

http://127.0.0.1:8000/docs

## API Endpoints

| Method | Endpoint                     | Purpose                                        |
| ------ | ---------------------------- | ---------------------------------------------- |
| GET    | /                            | Health message                                 |
| POST   | /products                    | Create a product                               |
| GET    | /products                    | List products                                  |
| GET    | /products/{product_id}       | Get one product                                |
| PATCH  | /products/{product_id}/stock | Set stock quantity                             |
| POST   | /customers                   | Create a customer                              |
| POST   | /orders                      | Create an order                                |
| GET    | /orders                      | List order items with customer/product details |
| GET    | /reports/sales-summary       | Overall sales totals                           |
| GET    | /reports/low-stock           | Products at or below a stock threshold         |
| GET    | /reports/product-sales       | Units sold and revenue per product             |

The stock update endpoint sets the new total; it does not add
units to the existing stock.

## Example Order Request

Create a customer and product first, then use their returned IDs:

```json
{
  "customer_id": 1,
  "items": [
    {
      "product_id": 1,
      "quantity": 2
    }
  ]
}
```

Order creation saves the order and its items and reduces stock
within one transaction. Any failure rolls back all changes.

Each successful POST /orders request creates a new order.
Repeated requests are not automatically deduplicated.

## Run Tests

```bash
python -m pytest -v
```

Five automated tests cover:

1. Product creation and retrieval
2. Successful order creation, stock reduction, and sales totals
3. Full rollback when a later order item has insufficient stock
4. Rejection of negative stock without changing stored stock
5. A 404 response for a missing product

Each test uses a separate temporary SQLite database.

## SQL Concepts Demonstrated

- CREATE TABLE and INSERT
- SELECT, WHERE, UPDATE, and ORDER BY
- Primary keys, foreign keys, and constraints
- INNER JOIN and LEFT JOIN
- GROUP BY, SUM, COUNT DISTINCT, and COALESCE
- Transactions, COMMIT, and ROLLBACK

## Current Limitations

This is a learning and portfolio project, not a production-ready
service. It does not yet include authentication, pagination,
order cancellation, or stock-adjustment audit history.

Order timestamps are stored in UTC. Revenue reports measure
sales revenue, not profit.

The local database is excluded from Git. Running database.py
creates the tables for a new installation.
