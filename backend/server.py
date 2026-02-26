# backend/server.py
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
import os
import threading
import pystray
from PIL import Image, ImageDraw
from datetime import datetime
import calculator 

app = FastAPI()
PROGRAM_DATA_DIR = r"C:\ProgramData\MyPrintMonitor"
DB_PATH = os.path.join(PROGRAM_DATA_DIR, "print_monitor.db")

class PrintLog(BaseModel):
    uuid: str
    pc_name: str
    ip_address: str
    os_user: str
    printer_name: str
    file_name: str
    total_pages: int
    color_mode: int
    paper_size: int
    copies: int
    remark: str = ""

class Heartbeat(BaseModel):
    uuid: str

class StatusUpdate(BaseModel):
    log_id: int
    status: str
    reason: str = ""

@app.get("/api/policy/control")
def get_control_policy(uuid: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ColorLimit, MonoLimit FROM PrintControlPolicy WHERE ID=1")
        global_row = cursor.fetchone()
        global_color = global_row[0] if global_row else 999999
        global_mono = global_row[1] if global_row else 999999

        user_color, user_mono = None, None
        if uuid:
            try:
                cursor.execute("SELECT ColorLimit, MonoLimit FROM Users WHERE UUID=?", (uuid,))
                user_row = cursor.fetchone()
                if user_row:
                    user_color, user_mono = user_row[0], user_row[1]
            except sqlite3.OperationalError:
                pass 

        final_color = user_color if user_color is not None else global_color
        final_mono = user_mono if user_mono is not None else global_mono

        return {"color_limit": final_color, "mono_limit": final_mono}
    except Exception:
        pass
    finally:
        conn.close()
    
    return {"color_limit": 999999, "mono_limit": 999999}

@app.get("/api/print-log/{log_id}/status")
def get_log_status(log_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT PrintStatus FROM PrintLogs WHERE LogID = ?", (log_id,))
        row = cursor.fetchone()
        if row:
            return {"status": row[0]}
    except sqlite3.OperationalError: pass
    finally:
        conn.close()
    return {"status": "not_found"}

@app.post("/api/print-log")
def receive_print_log(log: PrintLog):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    price = calculator.calculate_price(log.paper_size, log.color_mode, log.total_pages, log.copies)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status = "승인 대기" if "승인 대기" in log.remark else "완료"
    
    cursor.execute("""
        INSERT INTO PrintLogs (PrintTime, User_UUID, FileName, PaperSize, ColorType, TotalPages, Copies, CalculatedPrice, Remark, PrintStatus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, log.uuid, log.file_name, log.paper_size, log.color_mode, log.total_pages, log.copies, price, log.remark, status))
    
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"status": "success", "log_id": log_id, "price": price}

@app.post("/api/heartbeat")
def receive_heartbeat(hb: Heartbeat):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE Users SET LastHeartbeat = ?, Status = '온라인' WHERE UUID = ?", (now, hb.uuid))
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO Users (UUID, UserName, Department, Status, LastHeartbeat) VALUES (?, '미등록 사용자', '미배정', '온라인', ?)", (hb.uuid, now))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/api/print-log/status-update")
def update_status(update: StatusUpdate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT Remark FROM PrintLogs WHERE LogID = ?", (update.log_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"status": "error"}
        
    current_remark = row[0] if row[0] else ""
    new_remark = current_remark
    if update.reason:
        new_remark = f"{current_remark} [{update.reason}]".strip()
        
    cursor.execute("UPDATE PrintLogs SET PrintStatus = ?, Remark = ? WHERE LogID = ?", (update.status, new_remark, update.log_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}

# ====================================================================
# 🌟 [복구됨] 시스템 트레이 아이콘 (파란색) 및 백그라운드 서버 구동 로직
# ====================================================================
def run_fastapi_server():
    """FastAPI 서버를 백그라운드 스레드에서 실행 (접속 로그 숨김 처리)"""
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)

def create_server_image():
    """서버용 트레이 아이콘 이미지 생성 (파란색)"""
    image = Image.new('RGB', (64, 64), color=(255, 255, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(0, 100, 255)) # 파란색 아이콘
    return image

def exit_server(icon, item):
    """트레이 아이콘 종료 시 프로세스 강제 종료"""
    icon.stop()
    os._exit(0)

def setup_and_start(icon):
    """아이콘 준비 완료 시 서버 스레드 출발"""
    icon.visible = True
    server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    server_thread.start()

if __name__ == "__main__":
    os.makedirs(PROGRAM_DATA_DIR, exist_ok=True)
    
    # 시스템 트레이 메뉴 구성
    menu = pystray.Menu(
        pystray.MenuItem("🛑 중앙 서버 완전 종료", exit_server)
    )
    
    # 트레이 아이콘 실행 (이 코드가 메인 스레드를 점유하며 계속 구동됨)
    icon = pystray.Icon("PrintServer", create_server_image(), "프린트 중앙 서버 (작동 중)", menu)
    icon.run(setup=setup_and_start)