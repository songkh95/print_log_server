import sqlite3
import os
from datetime import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor, QFont
from constants import DB_PATH

class LogsTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        # 수정 모드 상태를 관리하는 변수
        self.is_edit_mode = False
        
        layout = QVBoxLayout(self)
        
        # -----------------------------------------------------
        # 1. 상단 컨트롤 영역 (제목, 날짜 조회, 수정, 새로고침)
        # -----------------------------------------------------
        top_layout = QHBoxLayout()
        title = QLabel("📊 실시간 인쇄 과금 대시보드")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        
        # 날짜 필터 UI 추가
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-30)) # 기본 조회: 최근 30일
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        
        search_btn = QPushButton("🔍 조회")
        search_btn.setFixedSize(80, 35)
        # 조회 버튼 클릭 시 다른 탭의 통계도 함께 갱신되도록 전체 새로고침 신호 발송
        search_btn.clicked.connect(self.refresh_requested.emit)
        
        # 수정(삭제 활성화) 버튼 추가
        self.edit_btn = QPushButton("✏️ 수정")
        self.edit_btn.setFixedSize(100, 40)
        self.edit_btn.setCheckable(True)
        self.edit_btn.clicked.connect(self.toggle_edit_mode)

        refresh_btn = QPushButton("🔄 데이터 새로고침")
        refresh_btn.setFixedSize(150, 40)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        
        # 상단 레이아웃 조립
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(QLabel("조회 기간 :"))
        top_layout.addWidget(self.start_date)
        top_layout.addWidget(QLabel("~"))
        top_layout.addWidget(self.end_date)
        top_layout.addWidget(search_btn)
        top_layout.addSpacing(20) # 간격 띄우기
        top_layout.addWidget(self.edit_btn)
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        # -----------------------------------------------------
        # 2. 메인 테이블 영역 (삭제 열 추가)
        # -----------------------------------------------------
        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(9) # 🌟 삭제 컬럼이 추가되어 총 9개 열
        self.table_logs.setHorizontalHeaderLabels([
            "삭제", "인쇄 시간", "사용자명 (부서)", "문서명", "용지", "선택 색상", "스풀러 요청 페이지 ℹ️", "과금액", "비고 (경고)"
        ])
        
        self.table_logs.horizontalHeaderItem(6).setToolTip(
            "본 과금 시스템은 윈도우 OS 스풀러의 논리 페이지 기준으로 과금됩니다.\n"
            "사용자가 프린터 제조사 전용 드라이버의 '모아찍기'를 사용한 경우 실제 물리적 종이 매수와 다르게 과금될 수 있습니다.\n"
            "억울한 과금 클레임은 우클릭하여 [수동 조정]을 진행해 주세요."
        )
        
        self.table_logs.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_logs.horizontalHeader().setStretchLastSection(True) 
        self.table_logs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # 각 열의 너비 지정 (인덱스 + 1 밀림)
        self.table_logs.setColumnWidth(0, 50)  # 삭제 (X) 버튼 열
        self.table_logs.setColumnWidth(1, 160) # 인쇄 시간
        self.table_logs.setColumnWidth(2, 160) # 사용자명
        self.table_logs.setColumnWidth(3, 280) # 문서명
        self.table_logs.setColumnWidth(4, 70)  # 용지
        self.table_logs.setColumnWidth(5, 80)  # 색상
        self.table_logs.setColumnWidth(6, 150) # 페이지
        self.table_logs.setColumnWidth(7, 100) # 과금액
        
        # 🌟 기본적으로 삭제 열(0번 열)은 숨겨둡니다.
        self.table_logs.setColumnHidden(0, True)
        
        self.table_logs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_logs.customContextMenuRequested.connect(self.show_log_context_menu)
        
        layout.addWidget(self.table_logs)

    # ====================================================================
    # 🌟 [신규] 수정 모드 토글 및 삭제 로직
    # ====================================================================
    def toggle_edit_mode(self):
        """수정 버튼 클릭 시 삭제 열을 나타내거나 숨깁니다."""
        self.is_edit_mode = self.edit_btn.isChecked()
        if self.is_edit_mode:
            self.edit_btn.setText("✅ 수정 완료")
            self.edit_btn.setStyleSheet("background-color: #ffe6e6; color: red; font-weight: bold;")
            self.table_logs.setColumnHidden(0, False) # 삭제 열 보이기
        else:
            self.edit_btn.setText("✏️ 수정")
            self.edit_btn.setStyleSheet("")
            self.table_logs.setColumnHidden(0, True)  # 삭제 열 숨기기

    def delete_log(self, log_id):
        """선택한 영수증을 DB에서 완전히 삭제합니다."""
        reply = QMessageBox.question(self, "삭제 확인", 
            "해당 영수증 내역을 완전히 삭제하시겠습니까?\n(삭제된 데이터는 인쇄 통계에서도 영구적으로 제외됩니다.)", 
            QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM PrintLogs WHERE LogID = ?", (log_id,))
                conn.commit()
                # 삭제 성공 시 전체 데이터와 통계를 갱신합니다.
                self.refresh_requested.emit() 
            except Exception as e:
                QMessageBox.critical(self, "시스템 오류", f"삭제 중 오류가 발생했습니다: {e}")
            finally:
                conn.close()

    # ====================================================================
    # 관리자 직권 양방향 과금 수동 조정 UI 로직 (인덱스 수정 반영)
    # ====================================================================
    def show_log_context_menu(self, pos):
        item = self.table_logs.itemAt(pos)
        if item is None: return
        
        row = item.row()
        # 🌟 인쇄 시간이 1번 열로 밀렸으므로 (row, 1)에서 가져옵니다.
        time_item = self.table_logs.item(row, 1) 
        if not time_item: return
            
        log_id = time_item.data(Qt.UserRole)
        if not log_id: return
            
        # 🌟 선택 색상이 5번 열로 밀렸으므로 (row, 5)에서 가져옵니다.
        current_color_text = self.table_logs.item(row, 5).text()
        
        menu = QMenu(self)
        if current_color_text == "컬러":
            action_to_mono = menu.addAction("🛠️ 흑백 단가로 과금 조정 (환불/롤백)")
            action_to_color = None
        else:
            action_to_color = menu.addAction("🛠️ 컬러 단가로 과금 조정 (오류 정정)")
            action_to_mono = None
        
        action = menu.exec(self.table_logs.viewport().mapToGlobal(pos))
        
        if action == action_to_mono: self.adjust_billing(log_id, target_color_mode=1)
        elif action == action_to_color: self.adjust_billing(log_id, target_color_mode=2)

    def adjust_billing(self, log_id, target_color_mode):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT PaperSize, TotalPages, Copies, CalculatedPrice, Remark, FileName FROM PrintLogs WHERE LogID = ?", (log_id,))
            row = cursor.fetchone()
            if not row:
                QMessageBox.warning(self, "오류", "해당 로그를 찾을 수 없습니다.")
                return
                
            paper_size, total_pages, copies, old_price, remark, file_name = row
            
            cursor.execute("SELECT BaseMonoPrice, BaseColorPrice, Multiplier, ColorMultiplier FROM PricingPolicy WHERE PaperSize = ?", (paper_size,))
            policy = cursor.fetchone()
            if not policy:
                cursor.execute("SELECT BaseMonoPrice, BaseColorPrice, Multiplier, ColorMultiplier FROM PricingPolicy WHERE PaperSize = 9")
                policy =fetchone()
            if not policy:
                QMessageBox.warning(self, "오류", "단가 정책을 찾을 수 없어 조정을 진행할 수 없습니다.")
                return
                
            base_mono, base_color, multi, color_multi = policy
            if color_multi is None: color_multi = multi
            
            if target_color_mode == 1:
                new_price = int(base_mono * multi * total_pages * copies)
                color_name = "흑백"
            else:
                new_price = int(base_color * color_multi * total_pages * copies)
                color_name = "컬러"
            
            if old_price == new_price and target_color_mode == 1:
                QMessageBox.information(self, "안내", "단가 변동이 없어 조정이 취소되었습니다.")
                return
                
            reply = QMessageBox.question(self, "과금 수동 조정", 
                f"문서명: '{file_name}'\n\n관리자 직권으로 인쇄물의 색상과 요금을 조정합니다.\n\n"
                f"기존 청구액: {old_price:,} 원\n변경 청구액: {new_price:,} 원 ({color_name} 요금 적용)\n\n진행하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No)
                                         
            if reply == QMessageBox.Yes:
                today_str = datetime.now().strftime("%y/%m/%d %H:%M")
                audit_msg = f"[관리자 조정: {color_name} 요금으로 변경({today_str})]"
                new_remark = f"{remark} {audit_msg}" if remark else audit_msg
                
                cursor.execute("UPDATE PrintLogs SET CalculatedPrice = ?, Remark = ?, ColorType = ? WHERE LogID = ?", 
                               (new_price, new_remark, target_color_mode, log_id))
                conn.commit()
                QMessageBox.information(self, "처리 완료", f"과금이 {new_price:,}원으로 성공적으로 조정되었습니다.")
                self.refresh_requested.emit() 
                
        except Exception as e:
            QMessageBox.critical(self, "시스템 오류", f"조정 중 오류 발생: {e}")
        finally:
            conn.close()

    # ====================================================================
    # 🌟 [수정] 데이터 로딩 시 '날짜 필터' 반영 및 '삭제(X)' 버튼 동적 생성
    # ====================================================================
    def load_data(self):
        import os
        if not os.path.exists(DB_PATH): return
        
        # 1. 사용자가 지정한 날짜 필터 문자열 조립 (00:00:00 ~ 23:59:59)
        start_date_str = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_date_str = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 2. 날짜 조건(WHERE BETWEEN)이 추가된 쿼리 실행
        cursor.execute('''
            SELECT p.PrintTime, u.UserName, u.Department, p.FileName, p.PaperSize, p.ColorType, p.TotalPages, p.CalculatedPrice, p.Remark, p.User_UUID, p.LogID 
            FROM PrintLogs p 
            LEFT JOIN Users u ON p.User_UUID = u.UUID 
            WHERE p.PrintTime >= ? AND p.PrintTime <= ?
            ORDER BY p.LogID DESC
        ''', (start_date_str, end_date_str))
        
        logs = cursor.fetchall()
        self.table_logs.setRowCount(0)
        
        for row_idx, row_data in enumerate(logs):
            self.table_logs.insertRow(row_idx)
            
            # DB에서 꺼내온 데이터 매핑
            time_str = row_data[0][:19]
            user_name, dept, uuid_str, log_id = row_data[1], row_data[2], row_data[9], row_data[10]
            display_user = f"{user_name} ({dept})" if user_name and user_name != "미등록 사용자" else uuid_str[:13] + "..."
            file_name = row_data[3]
            paper_size = "A4" if row_data[4] == 9 else ("A3" if row_data[4] == 8 else str(row_data[4]))
            color_str = "컬러" if row_data[5] == 2 else "흑백"
            pages = f"{row_data[6]}장"
            price = f"{row_data[7]:,}원"
            remark = row_data[8] if row_data[8] else ""

            # 🌟 [신규] 0번 열: 삭제용 [X] 버튼 생성
            del_btn = QPushButton("❌")
            del_btn.setStyleSheet("color: red; border: none; font-size: 14px;")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(lambda checked=False, lid=log_id: self.delete_log(lid))
            
            # 1번 열: 인쇄 시간 (LogID 숨김)
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, log_id)

            items = [
                time_item, QTableWidgetItem(display_user), QTableWidgetItem(file_name),
                QTableWidgetItem(paper_size), QTableWidgetItem(color_str), QTableWidgetItem(pages),
                QTableWidgetItem(price), QTableWidgetItem(remark)
            ]

            # 0번째 셀에 삭제 버튼 위젯 부착
            self.table_logs.setCellWidget(row_idx, 0, del_btn)
            
            # 나머지 1~8번째 셀에 데이터 부착
            for col_idx, item in enumerate(items):
                # 텍스트 중앙 정렬 (문서명은 좌측 정렬)
                item.setTextAlignment(Qt.AlignCenter if col_idx != 2 else Qt.AlignLeft | Qt.AlignVCenter)
                
                if remark:
                    if "⚠️" in remark: item.setBackground(QColor(255, 200, 200))
                    elif "관리자 조정" in remark: item.setBackground(QColor(220, 240, 255))
                
                # 열 번호가 1칸씩 밀렸으므로 col_idx + 1 에 할당
                self.table_logs.setItem(row_idx, col_idx + 1, item)
                
        conn.close()