# Manager_Console/models.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# 🌟 [경로 수정 완료] UI(constants.py)와 완벽하게 동일한 경로 사용
PROGRAM_DATA_DIR = r"C:\ProgramData\MyPrintMonitor"
if not os.path.exists(PROGRAM_DATA_DIR):
    os.makedirs(PROGRAM_DATA_DIR)

DB_PATH = os.path.join(PROGRAM_DATA_DIR, "print_monitor.db")
# SQLAlchemy 용 SQLite 절대경로 지정 포맷 (sqlite:///C:\...)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "Users"
    uuid = Column(String, primary_key=True, index=True)
    pc_name = Column(String)
    ip_address = Column(String)
    os_user = Column(String)
    department = Column(String, default="미지정")
    role = Column(String, default="User")           
    use_popup = Column(Boolean, default=True)       
    last_heartbeat = Column(DateTime, default=datetime.now)
    color_limit = Column(Integer, nullable=True) 
    mono_limit = Column(Integer, nullable=True)

class PrintLog(Base):
    __tablename__ = "PrintLogs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    log_time = Column(DateTime, default=datetime.now)
    uuid = Column(String, index=True)
    os_user = Column(String)
    printer_name = Column(String)
    file_name = Column(String)
    total_pages = Column(Integer)
    color_mode = Column(Integer)  
    paper_size = Column(Integer)  
    copies = Column(Integer)
    calculated_price = Column(Integer, default=0) 
    remark = Column(String, default="")
    print_status = Column(String, default="완료") 

class PricingPolicy(Base):
    __tablename__ = "PricingPolicy"
    paper_size = Column(Integer, primary_key=True) 
    base_mono_price = Column(Integer, default=50)
    base_color_price = Column(Integer, default=150)
    multiplier = Column(Integer, default=1)        
    color_multiplier = Column(Integer, default=1)  

class PrintControlPolicy(Base):
    __tablename__ = "PrintControlPolicy"
    id = Column(Integer, primary_key=True, default=1)
    color_limit = Column(Integer, default=999999)
    mono_limit = Column(Integer, default=999999)

class ApprovalRequest(Base):
    __tablename__ = "ApprovalRequests"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    log_id = Column(Integer) 
    request_time = Column(DateTime, default=datetime.now)
    status = Column(String, default="대기중")