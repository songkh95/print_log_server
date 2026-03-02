# Manager_Console/server.py
import os
import threading
import pystray
from PIL import Image, ImageDraw
from datetime import datetime
import uvicorn
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager

import calculator 
from models import engine, Base, SessionLocal, User, PrintLog, PricingPolicy, PrintControlPolicy, ApprovalRequest

# ====================================================================
# 🌟 [신규] 엔터프라이즈급 서버 로깅 시스템 (파일 & 콘솔 동시 출력)
# ====================================================================
LOG_DIR = r"C:\ProgramData\MyPrintMonitor\logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "server.log")

logger = logging.getLogger("PrintServer")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # 10MB씩 최대 5개의 백업 로그 파일을 순환하며 저장 (디스크 용량 보호)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# ====================================================================
# DB 세션 의존성
# ====================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("==================================================")
    logger.info("🚀 [서버 가동] 엔터프라이즈 과금 관리 서버가 시작되었습니다.")
    logger.info(f"📂 [로그 저장소] {LOG_FILE}")
    logger.info("==================================================")
    
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(PricingPolicy).first():
            db.add(PricingPolicy(paper_size=9, base_mono_price=50, base_color_price=150, multiplier=1, color_multiplier=1)) 
            db.add(PricingPolicy(paper_size=8, base_mono_price=50, base_color_price=150, multiplier=2, color_multiplier=2)) 
            
        if not db.query(PrintControlPolicy).first():
            db.add(PrintControlPolicy(id=1, color_limit=999999, mono_limit=999999))
            
        try: db.execute(text("ALTER TABLE PrintLogs ADD COLUMN calculated_price INTEGER DEFAULT 0"))
        except: pass
        try: db.execute(text("ALTER TABLE Users ADD COLUMN color_limit INTEGER"))
        except: pass
        try: db.execute(text("ALTER TABLE Users ADD COLUMN mono_limit INTEGER"))
        except: pass
        
        db.commit()
    finally:
        db.close()
        
    yield 
    logger.info("🛑 [서버 종료] 데이터베이스 연결을 안전하게 해제합니다.")

app = FastAPI(title="Manager Print API", lifespan=lifespan)

# --- 스키마 ---
class PrintLogSchema(BaseModel):
    uuid: str; pc_name: str; ip_address: str; os_user: str
    printer_name: str; file_name: str; total_pages: int
    color_mode: int; paper_size: int; copies: int; remark: str = ""

class HeartbeatSchema(BaseModel):
    uuid: str

class StatusUpdateSchema(BaseModel):
    log_id: int; status: str; reason: str = ""

class RefundRequestSchema(BaseModel):
    new_price: int; reason: str

# --- API 라우터 ---
@app.get("/api/policy/control")
def get_control_policy(uuid: str = None, db: Session = Depends(get_db)):
    global_policy = db.query(PrintControlPolicy).filter(PrintControlPolicy.id == 1).first()
    final_color = global_policy.color_limit if global_policy else 999999
    final_mono = global_policy.mono_limit if global_policy else 999999

    if uuid:
        user = db.query(User).filter(User.uuid == uuid).first()
        if user:
            if user.color_limit is not None: final_color = user.color_limit
            if user.mono_limit is not None: final_mono = user.mono_limit

    return {"color_limit": final_color, "mono_limit": final_mono}

@app.get("/api/print-log/{log_id}/status")
def get_log_status(log_id: int, db: Session = Depends(get_db)):
    log = db.query(PrintLog).filter(PrintLog.id == log_id).first()
    if log: return {"status": log.print_status}
    return {"status": "not_found"}

@app.post("/api/print-log")
def receive_print_log(log: PrintLogSchema, db: Session = Depends(get_db)):
    price = calculator.calculate_price(log.paper_size, log.color_mode, log.total_pages, log.copies)
    status = "승인 대기" if "승인 대기" in log.remark else "완료"
    
    new_log = PrintLog(
        uuid=log.uuid, os_user=log.os_user, printer_name=log.printer_name,
        file_name=log.file_name, total_pages=log.total_pages, color_mode=log.color_mode,
        paper_size=log.paper_size, copies=log.copies, remark=log.remark, print_status=status
    )
    new_log.calculated_price = price 
    db.add(new_log)
    db.commit()
    db.refresh(new_log) 
    
    # 🌟 [신규] 인쇄 수신 시 로그 기록
    logger.info(f"🖨️ [인쇄 수신] ID:{new_log.id} | 사용자:{log.os_user} | 문서:{log.file_name} ({log.total_pages}장) | 상태:{status}")
    return {"status": "success", "log_id": new_log.id, "price": price}

@app.post("/api/heartbeat")
def receive_heartbeat(hb: HeartbeatSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.uuid == hb.uuid).first()
    
    if user:
        user.last_heartbeat = datetime.now()
        # 생존 신고는 너무 자주 발생하므로 DEBUG 레벨로 숨길 수 있지만, 현재는 모니터링을 위해 INFO로 출력합니다.
        logger.info(f"💓 [생존 신고] 연결 유지됨: UUID({hb.uuid[:8]}...)")
    else:
        new_user = User(
            uuid=hb.uuid, os_user="미등록 사용자", department="미배정", last_heartbeat=datetime.now()
        )
        db.add(new_user)
        logger.warning(f"🆕 [신규 에이전트 등록] 최초 접속 감지: UUID({hb.uuid})")
        
    db.commit()
    return {"status": "ok"}

@app.post("/api/print-log/status-update")
def update_status(update: StatusUpdateSchema, db: Session = Depends(get_db)):
    log = db.query(PrintLog).filter(PrintLog.id == update.log_id).first()
    if not log: return {"status": "error", "message": "Log not found"}
        
    new_remark = log.remark if log.remark else ""
    if update.reason: new_remark = f"{new_remark} [{update.reason}]".strip()
        
    log.print_status = update.status
    log.remark = new_remark
    db.commit()
    
    logger.info(f"✅ [상태 변경] ID:{update.log_id} ➔ {update.status} (사유: {update.reason})")
    return {"status": "updated"}

@app.post("/api/print-log/{log_id}/refund")
def manual_price_adjustment(log_id: int, req: RefundRequestSchema, db: Session = Depends(get_db)):
    log = db.query(PrintLog).filter(PrintLog.id == log_id).first()
    if not log: raise HTTPException(status_code=404, detail="해당 인쇄 기록을 찾을 수 없습니다.")
    
    log.calculated_price = req.new_price
    log.print_status = "환불/조정됨" if req.new_price == 0 else "단가 조정됨"
    log.remark = f"{log.remark} [관리자 조정: {req.reason}]".strip()
    db.commit()
    
    logger.info(f"💰 [단가 조정] ID:{log_id} ➔ {req.new_price}원 (사유: {req.reason})")
    return {"status": "success", "adjusted_price": req.new_price}

# --- 백그라운드 구동 ---
def run_fastapi_server():
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)

def create_server_image():
    image = Image.new('RGB', (64, 64), color=(255, 255, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(0, 100, 255)) 
    return image

def exit_server(icon, item):
    icon.stop()
    os._exit(0)

def setup_and_start(icon):
    icon.visible = True
    server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    server_thread.start()

if __name__ == "__main__":
    menu = pystray.Menu(pystray.MenuItem("🛑 중앙 서버 완전 종료", exit_server))
    icon = pystray.Icon("PrintServer", create_server_image(), "프린트 중앙 서버 (작동 중)", menu)
    icon.run(setup=setup_and_start)