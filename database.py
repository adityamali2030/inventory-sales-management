import sqlite3
from pathlib import Path

# Store the database beside this Python file.
DATABASE_PATH = Path(__file__).resolve().parent / "inventory.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)

    # Allow us to access results using column names.
    connection.row_factory = sqlite3.Row

    # Enforce relationships between tables.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                product_name TEXT NOT NULL,
                price_paise INTEGER NOT NULL CHECK (price_paise > 0),
                stock_quantity INTEGER NOT NULL DEFAULT 0
                    CHECK (stock_quantity >= 0)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL
                    CHECK (length(trim(customer_name)) > 0),
                phone TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price_paise INTEGER NOT NULL
                    CHECK (unit_price_paise > 0),
                FOREIGN KEY (order_id)
                    REFERENCES orders(order_id),
                FOREIGN KEY (product_id)
                    REFERENCES products(product_id),
                UNIQUE (order_id, product_id)
            )
        """)
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")
