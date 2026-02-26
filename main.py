# Manager_Console/main.py
import sys
import sqlite3
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from constants import DB_PATH, PROGRAM_DATA_DIR

from tab_logs import LogsTab
from tab_stats import StatsTab
from tab_users import UsersTab
from tab_settings import SettingsTab

class ManagerConsoleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("프린트 과금 및 모니터링 시스템 - 통합 관리자 콘솔")
        self.resize(1150, 750)
        self.setStyleSheet("font-size: 14px;")
        
        self.upgrade_db_schema()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_logs = LogsTab()
        self.tab_stats = StatsTab()
        self.tab_users = UsersTab()
        self.tab_settings = SettingsTab()

        self.tabs.addTab(self.tab_logs, "🖨️ 인쇄 영수증 내역")
        self.tabs.addTab(self.tab_stats, "📈 인쇄 통계 분석") 
        self.tabs.addTab(self.tab_users, "👤 기기 및 사용자 관리")
        self.tabs.addTab(self.tab_settings, "⚙️ 정책 및 승인 설정")

        self.tab_logs.refresh_requested.connect(self.load_all_data)
        self.tab_stats.refresh_requested.connect(self.load_all_data)
        self.tab_users.refresh_requested.connect(self.load_all_data)
        self.tab_settings.refresh_requested.connect(self.load_all_data)

        self.load_all_data()

    def upgrade_db_schema(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("ALTER TABLE PricingPolicy ADD COLUMN ColorMultiplier REAL DEFAULT 2.0")
            cursor.execute("UPDATE PricingPolicy SET ColorMultiplier = 1.0 WHERE PaperSize = 9")
            cursor.execute("UPDATE PricingPolicy SET ColorMultiplier = Multiplier WHERE PaperSize = 8")
            conn.commit()
        except sqlite3.OperationalError: pass
            
        try:
            cursor.execute("ALTER TABLE PrintLogs ADD COLUMN PrintStatus TEXT DEFAULT '완료'")
            conn.commit()
        except sqlite3.OperationalError: pass
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS PrintControlPolicy (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    ColorLimit INTEGER DEFAULT 10,
                    MonoLimit INTEGER DEFAULT 50
                )
            """)
            cursor.execute("SELECT COUNT(*) FROM PrintControlPolicy")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO PrintControlPolicy (ColorLimit, MonoLimit) VALUES (10, 50)")
            conn.commit()
        except sqlite3.OperationalError: pass

        # 🌟 [신규] 사용자별 예외 통제 컬럼 추가
        try:
            cursor.execute("ALTER TABLE Users ADD COLUMN ColorLimit INTEGER")
            cursor.execute("ALTER TABLE Users ADD COLUMN MonoLimit INTEGER")
            conn.commit()
        except sqlite3.OperationalError: pass
        
        conn.close()

    def load_all_data(self):
        self.tab_logs.load_data()
        self.tab_stats.load_data()
        self.tab_users.load_data()
        self.tab_settings.load_data()

if __name__ == "__main__":
    os.makedirs(PROGRAM_DATA_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    window = ManagerConsoleWindow()
    window.show()
    sys.exit(app.exec())