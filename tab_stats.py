# Manager_Console/tab_stats.py
import sqlite3
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal, QDate, QSettings
from PySide6.QtGui import QColor, QFont, QBrush
from constants import DB_PATH

class StatsTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        # 🌟 [Phase 6 UX 향상] 설정 저장을 위한 QSettings 객체 초기화
        self.settings = QSettings("MyPrintMonitor", "ManagerConsole_Stats")
        
        layout = QVBoxLayout(self)
        
        # -----------------------------------------------------
        # 1. 상단 컨트롤 영역 (제목, 날짜 조회, 새로고침)
        # -----------------------------------------------------
        top_layout = QHBoxLayout()
        title = QLabel("📈 상세 인쇄 통계 및 과금 분석")
        
        # 🛠️ [UI 통일] tab_logs.py와 동일한 네이티브 폰트 및 크기(14) 적용
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-30)) # 기본값: 최근 30일
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        
        search_btn = QPushButton("🔍 조회")
        search_btn.setFixedSize(80, 35)
        search_btn.setStyleSheet("font-weight: bold; font-size: 13px; background-color: #f0f0f0; border-radius: 5px;")
        search_btn.clicked.connect(self.load_data)

        refresh_btn = QPushButton("🔄 통계 새로고침")
        refresh_btn.setFixedSize(150, 40)
        # 🛠️ [UI 통일] tab_logs.py의 새로고침 버튼과 완벽히 동일한 CSS 스타일 적용
        refresh_btn.setStyleSheet("font-weight: bold; font-size: 13px; background-color: #e0f7fa; border-radius: 5px;")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(QLabel("통계 기간 :"))
        top_layout.addWidget(self.start_date)
        top_layout.addWidget(QLabel("~"))
        top_layout.addWidget(self.end_date)
        top_layout.addWidget(search_btn)
        top_layout.addSpacing(20)
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        # -----------------------------------------------------
        # 2. 이너 탭 (종합 요약 / 기간별 추이) 구성
        # -----------------------------------------------------
        self.inner_tabs = QTabWidget()
        self.tab_summary = QWidget()
        self.tab_period = QWidget()
        
        self.inner_tabs.addTab(self.tab_summary, "📊 종합 요약 분석")
        self.inner_tabs.addTab(self.tab_period, "📅 기간별 추이 (일/월/년)")
        layout.addWidget(self.inner_tabs)

        self.init_summary_tab()
        self.init_period_tab()
        
        self.current_rows = [] # DB에서 가져온 로우 데이터를 캐싱할 변수

    def init_summary_tab(self):
        layout = QVBoxLayout(self.tab_summary)
        
        # 🛠️ [UI 통일] GroupBox 폰트를 Arial 하드코딩에서 시스템 네이티브 폰트로 변경
        group_font = QFont()
        group_font.setBold(True)
        group_font.setPointSize(12)

        group_billing = QGroupBox("💰 용지 및 색상별 정상 과금 통계")
        group_billing.setFont(group_font)
        layout_billing = QVBoxLayout(group_billing)
        self.table_stats_billing = QTableWidget()
        self.table_stats_billing.setColumnCount(3)
        self.table_stats_billing.setHorizontalHeaderLabels(["구분 항목", "누적 페이지 수 (장)", "총 과금액 (원)"])
        
        # 🛠️ [UI 통일] 테이블 교차 색상(Alternating Row Colors) 적용
        self.table_stats_billing.setAlternatingRowColors(True)

        # [UX 향상] 과금 테이블 너비 조절 및 상태 복원
        header_billing = self.table_stats_billing.horizontalHeader()
        header_billing.setSectionResizeMode(QHeaderView.Interactive)
        header_billing.setStretchLastSection(True)
        if self.settings.value("stats_billing_header"):
            header_billing.restoreState(self.settings.value("stats_billing_header"))

        self.table_stats_billing.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_stats_billing.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout_billing.addWidget(self.table_stats_billing)
        layout.addWidget(group_billing)

        group_exception = QGroupBox("🚨 예외 상황 통계 (취소 및 불확실한 데이터)")
        group_exception.setFont(group_font)
        layout_exception = QVBoxLayout(group_exception)
        self.table_stats_exception = QTableWidget()
        self.table_stats_exception.setColumnCount(4)
        self.table_stats_exception.setHorizontalHeaderLabels(["예외 항목", "발생 건수", "관련 페이지 수", "관련 과금액 (원)"])
        
        # 🛠️ [UI 통일] 테이블 교차 색상 적용
        self.table_stats_exception.setAlternatingRowColors(True)

        # [UX 향상] 예외 테이블 너비 조절 및 상태 복원
        header_exception = self.table_stats_exception.horizontalHeader()
        header_exception.setSectionResizeMode(QHeaderView.Interactive)
        header_exception.setStretchLastSection(True)
        if self.settings.value("stats_exception_header"):
            header_exception.restoreState(self.settings.value("stats_exception_header"))

        self.table_stats_exception.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_stats_exception.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout_exception.addWidget(self.table_stats_exception)
        layout.addWidget(group_exception)

    def init_period_tab(self):
        layout = QVBoxLayout(self.tab_period)
        
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("집계 기준 :"))
        self.combo_period = QComboBox()
        self.combo_period.addItems(["일별 (Daily)", "월별 (Monthly)", "연별 (Yearly)"])
        self.combo_period.currentIndexChanged.connect(self.populate_period_table)
        
        control_layout.addWidget(self.combo_period)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        self.table_stats_period = QTableWidget()
        self.table_stats_period.setColumnCount(7)
        self.table_stats_period.setHorizontalHeaderLabels([
            "기간", "총 출력 (장)", "총 과금액 (원)", "흑백 출력 (장)", "컬러 출력 (장)", "취소/오류 (건)", "경고/확인 (건)"
        ])
        
        # 🛠️ [UI 통일] 테이블 교차 색상 적용
        self.table_stats_period.setAlternatingRowColors(True)

        # [UX 향상] 기간별 테이블 너비 조절 및 상태 복원
        header_period = self.table_stats_period.horizontalHeader()
        header_period.setSectionResizeMode(QHeaderView.Interactive)
        header_period.setStretchLastSection(True)
        if self.settings.value("stats_period_header"):
            header_period.restoreState(self.settings.value("stats_period_header"))

        self.table_stats_period.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_stats_period.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table_stats_period)

    # ====================================================================
    # 🌟 새 ORM 컬럼명으로 완벽 매핑된 데이터 로드 함수
    # ====================================================================
    def load_data(self):
        if not os.path.exists(DB_PATH): return
        
        start_str = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_str = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try: 
            cursor.execute("""
                SELECT log_time, paper_size, color_mode, total_pages, copies, calculated_price, remark, print_status 
                FROM PrintLogs
                WHERE log_time >= ? AND log_time <= ?
            """, (start_str, end_str))
        except sqlite3.OperationalError: 
            # 구버전 스키마 대응 로직 유지 (안전망)
            cursor.execute("""
                SELECT PrintTime, PaperSize, ColorType, TotalPages, Copies, CalculatedPrice, Remark, '완료' 
                FROM PrintLogs
                WHERE PrintTime >= ? AND PrintTime <= ?
            """, (start_str, end_str))
            
        self.current_rows = cursor.fetchall()
        conn.close()

        # 데이터 로드 후, 두 탭의 화면을 각각 갱신합니다.
        self.populate_summary_tables()
        self.populate_period_table()

    def populate_summary_tables(self):
        stats = {
            'A4_Mono': {'pages': 0, 'price': 0}, 'A4_Color': {'pages': 0, 'price': 0},
            'A3_Mono': {'pages': 0, 'price': 0}, 'A3_Color': {'pages': 0, 'price': 0},
            'Total_Mono': {'pages': 0, 'price': 0}, 'Total_Color': {'pages': 0, 'price': 0},
            'Total_All': {'pages': 0, 'price': 0},
            'Cancelled': {'count': 0, 'pages': 0, 'price': 0}, 'Uncertain': {'count': 0, 'pages': 0, 'price': 0}
        }

        for row in self.current_rows:
            p_time, p_size, c_type, t_pages, copies, price, remark, status = row
            copies, t_pages, price, remark, status = copies or 1, t_pages or 0, price or 0, remark or "", status or "완료"
            actual_pages = t_pages * copies
            
            is_cancelled = False
            if status == '과금취소' or ('취소' in remark and '관리자 조정' not in remark) or ('오류' in remark):
                is_cancelled = True
                stats['Cancelled']['count'] += 1
                stats['Cancelled']['pages'] += actual_pages
                stats['Cancelled']['price'] += price
                
            if '⚠️' in remark:
                stats['Uncertain']['count'] += 1
                stats['Uncertain']['pages'] += actual_pages
                stats['Uncertain']['price'] += price

            if not is_cancelled:
                stats['Total_All']['pages'] += actual_pages
                stats['Total_All']['price'] += price
                if c_type == 1: 
                    stats['Total_Mono']['pages'] += actual_pages
                    stats['Total_Mono']['price'] += price
                    if p_size == 9: 
                        stats['A4_Mono']['pages'] += actual_pages
                        stats['A4_Mono']['price'] += price
                    elif p_size == 8: 
                        stats['A3_Mono']['pages'] += actual_pages
                        stats['A3_Mono']['price'] += price
                elif c_type == 2: 
                    stats['Total_Color']['pages'] += actual_pages
                    stats['Total_Color']['price'] += price
                    if p_size == 9: 
                        stats['A4_Color']['pages'] += actual_pages
                        stats['A4_Color']['price'] += price
                    elif p_size == 8: 
                        stats['A3_Color']['pages'] += actual_pages
                        stats['A3_Color']['price'] += price

        billing_display_data = [
            ("A4 흑백", stats['A4_Mono']), ("A4 컬러", stats['A4_Color']),
            ("A3 흑백", stats['A3_Mono']), ("A3 컬러", stats['A3_Color']),
            ("◼️ 흑백 전체 합계", stats['Total_Mono']), ("🎨 컬러 전체 합계", stats['Total_Color']),
            ("👑 전체 총계", stats['Total_All'])
        ]
        
        self.table_stats_billing.setRowCount(0)
        for row_idx, (label, data) in enumerate(billing_display_data):
            self.table_stats_billing.insertRow(row_idx)
            item_label, item_pages, item_price = QTableWidgetItem(label), QTableWidgetItem(f"{data['pages']:,} 장"), QTableWidgetItem(f"{data['price']:,} 원")
            item_label.setTextAlignment(Qt.AlignCenter); item_pages.setTextAlignment(Qt.AlignCenter); item_price.setTextAlignment(Qt.AlignCenter)
            
            if "합계" in label or "총계" in label:
                font = QFont(); font.setBold(True)
                item_label.setFont(font); item_pages.setFont(font); item_price.setFont(font)
                bg_color = QColor(230, 240, 250) if "총계" in label else QColor(245, 245, 245)
                item_label.setBackground(bg_color); item_pages.setBackground(bg_color); item_price.setBackground(bg_color)

            self.table_stats_billing.setItem(row_idx, 0, item_label)
            self.table_stats_billing.setItem(row_idx, 1, item_pages)
            self.table_stats_billing.setItem(row_idx, 2, item_price)

        exception_display_data = [("🚫 취소/오류된 인쇄물", stats['Cancelled']), ("⚠️ 불확실한 데이터 건수 (가상프린터 등)", stats['Uncertain'])]
        self.table_stats_exception.setRowCount(0)
        for row_idx, (label, data) in enumerate(exception_display_data):
            self.table_stats_exception.insertRow(row_idx)
            items = [QTableWidgetItem(label), QTableWidgetItem(f"{data['count']:,} 건"), QTableWidgetItem(f"{data['pages']:,} 장"), QTableWidgetItem(f"{data['price']:,} 원")]
            for i, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                if "취소" in label: item.setForeground(QBrush(QColor(150, 150, 150)))
                elif "불확실" in label: item.setForeground(QBrush(QColor(200, 50, 50)))
                self.table_stats_exception.setItem(row_idx, i, item)

    def populate_period_table(self):
        period_type = self.combo_period.currentIndex()
        
        char_length = 10
        if period_type == 1: char_length = 7
        elif period_type == 2: char_length = 4

        aggregated = {}

        for row in self.current_rows:
            p_time, p_size, c_type, t_pages, copies, price, remark, status = row
            date_key = p_time[:char_length]
            
            if date_key not in aggregated:
                aggregated[date_key] = {'total_pages': 0, 'total_price': 0, 'mono_pages': 0, 'color_pages': 0, 'cancel': 0, 'warn': 0}

            copies, t_pages, price, remark, status = copies or 1, t_pages or 0, price or 0, remark or "", status or "완료"
            actual_pages = t_pages * copies
            
            is_cancelled = False
            if status == '과금취소' or ('취소' in remark and '관리자 조정' not in remark) or ('오류' in remark):
                is_cancelled = True
                aggregated[date_key]['cancel'] += 1
                
            if '⚠️' in remark:
                aggregated[date_key]['warn'] += 1

            if not is_cancelled:
                aggregated[date_key]['total_pages'] += actual_pages
                aggregated[date_key]['total_price'] += price
                if c_type == 1: aggregated[date_key]['mono_pages'] += actual_pages
                elif c_type == 2: aggregated[date_key]['color_pages'] += actual_pages

        sorted_dates = sorted(aggregated.keys(), reverse=True)
        
        self.table_stats_period.setRowCount(0)
        for row_idx, date_key in enumerate(sorted_dates):
            data = aggregated[date_key]
            self.table_stats_period.insertRow(row_idx)
            
            items = [
                QTableWidgetItem(date_key),
                QTableWidgetItem(f"{data['total_pages']:,} 장"),
                QTableWidgetItem(f"{data['total_price']:,} 원"),
                QTableWidgetItem(f"{data['mono_pages']:,} 장"),
                QTableWidgetItem(f"{data['color_pages']:,} 장"),
                QTableWidgetItem(f"{data['cancel']:,} 건"),
                QTableWidgetItem(f"{data['warn']:,} 건")
            ]
            
            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                if col_idx == 0: item.setBackground(QColor(240, 240, 240))
                self.table_stats_period.setItem(row_idx, col_idx, item)

    # 🌟 [보안/UX] 프로그램 종료 시 3개의 테이블 헤더 상태를 개별적으로 모두 저장
    def closeEvent(self, event):
        self.settings.setValue("stats_billing_header", self.table_stats_billing.horizontalHeader().saveState())
        self.settings.setValue("stats_exception_header", self.table_stats_exception.horizontalHeader().saveState())
        self.settings.setValue("stats_period_header", self.table_stats_period.horizontalHeader().saveState())
        super().closeEvent(event)