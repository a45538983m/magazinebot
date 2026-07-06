from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship

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
    brand = Column(String, nullable=True)                        # <-- НОВОЕ: бренд
    purchase_price = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)
    stock_quantity = Column(Integer, default=0)
    location_code = Column(String, nullable=True)

    compatible_models = relationship(
        "CarModel",
        secondary=product_compatibility,
        back_populates="products"
    )

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