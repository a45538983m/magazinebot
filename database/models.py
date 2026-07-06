from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

# Промежуточная таблица многие-ко-многим
product_compatibility = Table(
    "product_compatibility",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id"), primary_key=True),
    Column("car_model_id", Integer, ForeignKey("car_models.id"), primary_key=True),
)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    purchase_price = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)
    stock_quantity = Column(Integer, default=0)
    location_code = Column(String, nullable=True)

    compatible_models = relationship(
        "CarModel",
        secondary=product_compatibility,
        back_populates="products"
    )

    purchases = relationship("Purchase", back_populates="product")

    def __repr__(self):
        return f"<Product(article={self.article}, name={self.name})>"


class CarModel(Base):
    __tablename__ = "car_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year_from = Column(Integer, nullable=True)
    year_to = Column(Integer, nullable=True)

    products = relationship(
        "Product",
        secondary=product_compatibility,
        back_populates="compatible_models"
    )

    def __repr__(self):
        return f"<CarModel(brand={self.brand}, model={self.model})>"


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)  # закупочная цена на момент прихода
    created_at = Column(DateTime, default=datetime.now)

    product = relationship("Product", back_populates="purchases")

    def __repr__(self):
        return f"<Purchase(product_id={self.product_id}, quantity={self.quantity})>"