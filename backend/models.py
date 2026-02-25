# Manager_Console/backend/models.py
import sqlite3
import os
import sys
from datetime import datetime

PROGRAM_DATA_DIR = r"C:\ProgramData\MyPrintMonitor"
DB_PATH = os.path.join(PROGRAM_DATA_DIR, "print_monitor.db")

if not os.path.exists(PROGRAM_DATA_DIR):
    os.makedirs(PROGRAM_DATA_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        UUID TEXT PRIMARY KEY,
        UserName TEXT,
        Department TEXT,
        LastHeartbeat DATETIME,
        Status TEXT
    )
    ''')

    # 🌟 [수정됨] PrintStatus (과금 상태) 컬럼이 추가되었습니다.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS PrintLogs (
        LogID INTEGER PRIMARY KEY AUTOINCREMENT,
        User_UUID TEXT,
        PrintTime DATETIME,
        FileName TEXT,
        ColorType INTEGER,
        PaperSize INTEGER,
        TotalPages INTEGER,
        Copies INTEGER,
        CalculatedPrice INTEGER,
        Remark TEXT,
        PrintStatus TEXT DEFAULT '출력진행중'
    )
    ''')

    # 🌟 [추가됨] 이미 구버전 DB가 만들어져 있는 경우 컬럼을 자동으로 끼워넣는 마이그레이션 로직
    try:
        cursor.execute("ALTER TABLE PrintLogs ADD COLUMN PrintStatus TEXT DEFAULT '완료'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # 이미 컬럼이 존재하면 무시하고 넘어감

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS PricingPolicy (
        PaperSize INTEGER PRIMARY KEY,
        BaseColorPrice INTEGER,
        BaseMonoPrice INTEGER,
        Multiplier REAL,
        ColorMultiplier REAL DEFAULT 2.0
    )
    ''')

    cursor.execute("INSERT OR IGNORE INTO PricingPolicy (PaperSize, BaseColorPrice, BaseMonoPrice, Multiplier, ColorMultiplier) VALUES (9, 150, 50, 1.0, 1.0)")
    cursor.execute("INSERT OR IGNORE INTO PricingPolicy (PaperSize, BaseColorPrice, BaseMonoPrice, Multiplier, ColorMultiplier) VALUES (8, 150, 50, 2.0, 2.0)")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()