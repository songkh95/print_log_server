# Manager_Console/main.py
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from models import Base, engine

from tab_logs import TabLogs
from tab_stats import StatsTab
from tab_users import UsersTab
from tab_settings import SettingsTab

class ManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("엔터프라이즈 프린트 과금 관리 대시보드 (v1.1 Secure Final)")
        self.resize(1200, 800)
        
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 1. 탭 객체 생성
        self.tab_logs = TabLogs()
        self.tab_stats = StatsTab()
        self.tab_users = UsersTab()
        self.tab_settings = SettingsTab()
        
        # 2. 탭 부착
        self.tabs.addTab(self.tab_logs, "📊 실시간 로그 및 결재 관리")
        self.tabs.addTab(self.tab_stats, "📈 통계 분석 (일/월/년)")
        self.tabs.addTab(self.tab_users, "👥 기기 현황 및 예외 설정")
        self.tabs.addTab(self.tab_settings, "⚙️ 과금 단가 및 전사 정책 설정")
        
        # 🌟 [복구] 3. 원클릭 전체 새로고침(Global Refresh) 시그널 통합 라우팅
        self.tab_logs.refresh_requested.connect(self.load_all_data)
        self.tab_stats.refresh_requested.connect(self.load_all_data)
        self.tab_users.refresh_requested.connect(self.load_all_data)
        self.tab_settings.refresh_requested.connect(self.load_all_data)

    # 🌟 [복구] 모든 탭의 데이터를 한 번에 최신화하는 중앙 컨트롤 로직
    def load_all_data(self):
        self.tab_logs.load_data()
        self.tab_stats.load_data()
        self.tab_users.load_data()
        self.tab_settings.load_data()

if __name__ == "__main__":
    # ORM 엔진 초기화 및 테이블 안전 점검
    Base.metadata.create_all(bind=engine)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
    window = ManagerWindow()
    window.show()
    sys.exit(app.exec())