from decimal import Decimal

from sqlalchemy.orm import Session

from .models import Product

PRODUCTS = [
    # Electronics
    {"name": "Wireless Noise-Cancelling Headphones", "category": "Electronics", "price": "149.99", "stock_qty": 85, "description": "Premium over-ear headphones with active noise cancellation and 30-hour battery life."},
    {"name": "Smart Watch Series 5", "category": "Electronics", "price": "299.99", "stock_qty": 60, "description": "Track fitness, receive notifications, and monitor health metrics from your wrist."},
    {"name": "Mechanical Keyboard", "category": "Electronics", "price": "89.99", "stock_qty": 120, "description": "Tactile mechanical switches, RGB backlight, compact 75% layout."},
    {"name": "USB-C Hub 7-in-1", "category": "Electronics", "price": "49.99", "stock_qty": 200, "description": "Expand your laptop with HDMI, USB-A x3, SD card, and Ethernet."},
    {"name": "Portable SSD 1TB", "category": "Electronics", "price": "109.99", "stock_qty": 75, "description": "Ultra-fast NVMe portable storage. Read speeds up to 1050 MB/s."},
    {"name": "Webcam 4K Pro", "category": "Electronics", "price": "129.99", "stock_qty": 90, "description": "4K 30fps webcam with auto-focus, built-in ring light, and privacy shutter."},
    # Clothing
    {"name": "Classic Crew Neck T-Shirt", "category": "Clothing", "price": "24.99", "stock_qty": 300, "description": "100% organic cotton, pre-shrunk. Available in 8 colors."},
    {"name": "Slim Fit Chinos", "category": "Clothing", "price": "59.99", "stock_qty": 150, "description": "Wrinkle-resistant stretch fabric. Office to weekend in one pant."},
    {"name": "Waterproof Hiking Jacket", "category": "Clothing", "price": "119.99", "stock_qty": 80, "description": "3-layer Gore-Tex shell. Packable into its own chest pocket."},
    {"name": "Merino Wool Hoodie", "category": "Clothing", "price": "79.99", "stock_qty": 110, "description": "Lightweight merino wool blend. Temperature-regulating, odour-resistant."},
    {"name": "Running Sneakers", "category": "Clothing", "price": "99.99", "stock_qty": 95, "description": "Responsive foam midsole. Breathable mesh upper. 12mm heel drop."},
    # Books
    {"name": "Designing Data-Intensive Applications", "category": "Books", "price": "49.99", "stock_qty": 500, "description": "Martin Kleppmann. The definitive guide to building reliable, scalable data systems."},
    {"name": "The Pragmatic Programmer", "category": "Books", "price": "44.99", "stock_qty": 400, "description": "Hunt & Thomas. 20th anniversary edition. Timeless advice for software craftsmanship."},
    {"name": "Fundamentals of Data Engineering", "category": "Books", "price": "54.99", "stock_qty": 350, "description": "Reis & Housley. The complete lifecycle from source systems to analytics."},
    {"name": "Clean Architecture", "category": "Books", "price": "39.99", "stock_qty": 450, "description": "Robert C. Martin. Principles and patterns for maintainable software structure."},
    {"name": "Python for Data Analysis", "category": "Books", "price": "44.99", "stock_qty": 380, "description": "Wes McKinney. NumPy, pandas, and data wrangling from the creator of pandas."},
    # Home & Garden
    {"name": "Pour-Over Coffee Maker", "category": "Home & Garden", "price": "34.99", "stock_qty": 180, "description": "Borosilicate glass carafe with stainless steel filter. Brews 600ml."},
    {"name": "LED Desk Lamp with USB Charging", "category": "Home & Garden", "price": "44.99", "stock_qty": 160, "description": "5 colour temperatures, 10 brightness levels, built-in USB-A + USB-C charging."},
    {"name": "Bamboo Desk Organiser", "category": "Home & Garden", "price": "29.99", "stock_qty": 220, "description": "6-compartment organiser. Sustainable bamboo. Keeps your workspace clutter-free."},
    {"name": "Ceramic Plant Pot Set", "category": "Home & Garden", "price": "39.99", "stock_qty": 140, "description": "Set of 3 matte ceramic pots with drainage holes and bamboo saucers."},
]


def seed_products(db: Session) -> None:
    if db.query(Product).count() > 0:
        return
    for data in PRODUCTS:
        product = Product(
            name=data["name"],
            category=data["category"],
            description=data["description"],
            price=Decimal(data["price"]),
            stock_qty=data["stock_qty"],
        )
        db.add(product)
    db.commit()
