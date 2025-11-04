from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint, Index, DateTime

class Base(DeclarativeBase):
    pass

class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    gsp_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    dno_name: Mapped[str] = mapped_column(String(120), nullable=True)

class RegionPrefix(Base):
    __tablename__ = "region_prefixes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    __table_args__ = (UniqueConstraint("region_id", "prefix", name="uq_region_prefix"),)

class GridIntensity(Base):
    __tablename__ = "grid_intensity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    ts_utc: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    ci_g_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    renewable_share_pct: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(12), nullable=False)  # 'actual'|'forecast'
    __table_args__ = (
        UniqueConstraint("region_id", "ts_utc", "source", name="uq_intensity_region_ts_source"),
        Index("ix_intensity_region_ts", "region_id", "ts_utc"),
    )
