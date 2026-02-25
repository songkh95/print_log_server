# Manager_Console/backend/server.py
from fastapi import FastAPI, Request
import uvicorn
import sqlite3
from datetime import datetime
from models import DB_PATH, init_db
import calculator
import threading
import os
import pystray
from PIL import Image, ImageDraw
import configparser
import logging
from logging.handlers import RotatingFileHandler

PROGRAM_DATA_DIR = r"C:\ProgramData\MyPrintMonitor"
LOG_DIR = os.path.join(PROGRAM_DATA_DIR, "logs")
CONFIG_PATH = os.path.join(PROGRAM_DATA_DIR, "config.ini")

os.makedirs(LOG_DIR, exist_ok=True)

config = configparser.ConfigParser()
server_port = 8000        
log_level_str = "INFO"    

if os.path.exists(CONFIG_PATH):
    config.read(CONFIG_PATH, encoding='utf-8')
    server_port = int(config.get('SERVER', 'PORT', fallback=server_port))
    log_level_str = config.get('SERVER', 'LOG_LEVEL', fallback=log_level_str)

logger = logging.getLogger("ManagerServer")
log_level = getattr(logging, log_level_str.upper(), logging.INFO)
logger.setLevel(log_level)

log_file_path = os.path.join(LOG_DIR, "server_error.log")
handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(handler)

app = FastAPI()
init_db()

@app.post("/api/print-log")
async def receive_print_log(request: Request):
    try:
        data = await request.json()
        
        uuid = data.get('uuid')
        pc_name = data.get('pc_name', '알 수 없음')
        ip_address = data.get('ip_address', '알 수 없음')
        os_user = data.get('os_user', '알 수 없음')
        printer_name = data.get('printer_name', '알 수 없음')
        
        file_name = data.get('file_name')
        total_pages = data.get('total_pages')
        color_mode = data.get('color_mode')
        paper_size = data.get('paper_size', 9) 
        copies = data.get('copies', 1)
        remark = data.get('remark', '')
        
        calculated_price = calculator.calculate_price(paper_size, color_mode, total_pages, copies)
        current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 🌟 [수정됨] 일단 '출력진행중' 상태로 DB에 넣습니다. (완전히 출력되면 클라이언트가 업데이트 할 예정)
        cursor.execute('''
            INSERT INTO PrintLogs (User_UUID, PrintTime, FileName, ColorType, PaperSize, TotalPages, Copies, CalculatedPrice, Remark, PrintStatus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '출력진행중')
        ''', (uuid, current_time_str, file_name, color_mode, paper_size, total_pages, copies, calculated_price, remark))
        
        # 🌟 [추가됨] 방금 넣은 영수증의 고유 번호(LogID)를 가져옵니다.
        log_id = cursor.lastrowid 
        
        conn.commit()
        conn.close()
        
        logger.info(f"📄 [영수증 수신] {os_user}님의 '{file_name}' DB 등록(LogID:{log_id}). 과금액: {calculated_price}원")
        
        # 클라이언트에게 영수증 번호(log_id)를 돌려줍니다. 그래야 나중에 취소할 수 있습니다.
        return {"status": "success", "price": calculated_price, "log_id": log_id}
        
    except Exception as e:
        logger.error(f"🚨 [DB 오류] 영수증 저장 실패: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

# ====================================================================
# 🌟 [신규 추가] 과금 취소 (Rollback) 및 상태 업데이트 API
# ====================================================================
@app.post("/api/print-log/status-update")
async def update_print_status(request: Request):
    try:
        data = await request.json()
        log_id = data.get('log_id')
        new_status = data.get('status') # '완료' 또는 '과금취소'
        reason = data.get('reason', '') # 에러 사유 (선택)
        
        if log_id and new_status:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            if new_status == '과금취소':
                # 취소된 경우 금액을 0원으로 돌리고 비고란에 사유를 적습니다.
                cursor.execute("UPDATE PrintLogs SET PrintStatus = ?, CalculatedPrice = 0, Remark = ? WHERE LogID = ?", 
                               (new_status, f"⚠️ {reason}", log_id))
                logger.warning(f"🔄 [과금 취소] LogID {log_id} 영수증이 취소되었습니다. (사유: {reason})")
            else:
                # 정상 완료된 경우 상태만 '완료'로 바꿉니다.
                cursor.execute("UPDATE PrintLogs SET PrintStatus = ? WHERE LogID = ?", (new_status, log_id))
                logger.info(f"✅ [출력 완료] LogID {log_id} 출력이 정상 완료되었습니다.")
                
            conn.commit()
            conn.close()
            
        return {"status": "success"}
    except Exception as e:
        logger.error(f"🚨 [DB 오류] 상태 업데이트 실패: {e}", exc_info=True)
        return {"status": "error"}

@app.post("/api/heartbeat")
async def receive_heartbeat(request: Request):
    try:
        uuid = (await request.json()).get('uuid')
        if uuid:
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Users (UUID, UserName, Department, LastHeartbeat, Status)
                VALUES (?, '미등록 사용자', '미배정', ?, 'Online')
                ON CONFLICT(UUID) DO UPDATE SET LastHeartbeat = excluded.LastHeartbeat, Status = 'Online'
            ''', (uuid, current_time_str))
            conn.commit()
            conn.close()
            
            logger.debug(f"💓 [하트비트] 기기({uuid}) 생존 신고 DB 갱신 완료")
            
        return {"status": "alive"}
    except Exception as e:
        logger.error(f"🚨 [DB 오류] 하트비트 갱신 실패: {e}", exc_info=True)
        return {"status": "error"}

def run_uvicorn():
    logger.info(f"🚀 Manager Server 백그라운드 구동 시작 (포트: {server_port})")
    uvicorn.run(app, host="0.0.0.0", port=server_port, log_level="error")

def create_image():
    image = Image.new('RGB', (64, 64), color=(255, 255, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(0, 0, 200))
    return image

def exit_app(icon, item):
    logger.info("🛑 [종료] 수신 서버를 완전 종료합니다.")
    icon.stop()
    os._exit(0)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    server_thread.start()
    
    menu = pystray.Menu(pystray.MenuItem("🛑 수신 서버 완전 종료", exit_app))
    icon = pystray.Icon("ManagerServer", create_image(), "프린트 과금 수신 서버 (구동 중)", menu)
    icon.run()