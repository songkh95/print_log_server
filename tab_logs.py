# Manager_Console/tab_logs.py
import os
import sqlite3
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QMenu, QMessageBox, QInputDialog, QLabel,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, Signal, QSettings
from PySide6.QtGui import QColor, QBrush, QFont
from constants import DB_PATH

class TabLogs(QWidget):
    # 🌟 [복구] 메인 윈도우에 새로고침 신호를 전달할 전역 시그널
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        # 🌟 [UX 향상] 컬럼 너비 상태 저장을 위한 QSettings 객체 초기화
        self.settings = QSettings("MyPrintMonitor", "ManagerConsole_Logs")
        self.is_edit_mode = False # 🌟 [복구] 수정 모드 상태 변수
        self.init_ui()
        
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_data)
        self.refresh_timer.start(10000)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- 상단 컨트롤 패널 ---
        top_layout = QHBoxLayout()
        title_label = QLabel("📊 실시간 인쇄 과금 및 로그 관리")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        
        # 🌟 [복구] 삭제 모드 토글 버튼 추가
        self.edit_btn = QPushButton("✏️ 로그 삭제 모드")
        self.edit_btn.setFixedSize(140, 40)
        self.edit_btn.setStyleSheet("font-weight: bold; font-size: 13px; background-color: #f0f0f0; border-radius: 5px;")
        self.edit_btn.clicked.connect(self.toggle_edit_mode)
        
        btn_refresh = QPushButton("🔄 데이터 새로고침")
        btn_refresh.setFixedSize(140, 40)
        btn_refresh.setStyleSheet("font-weight: bold; font-size: 13px; background-color: #e0f7fa; border-radius: 5px;")
        # 단일 탭 새로고침이 아닌, 메인 윈도우 전체 새로고침 시그널 발송
        btn_refresh.clicked.connect(self.refresh_requested.emit) 
        
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(self.edit_btn)
        top_layout.addWidget(btn_refresh)
        layout.addLayout(top_layout)

        # --- 메인 데이터 테이블 ---
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "LogID", "인쇄 시간", "사용자(OS)", "문서명", "프린터명", 
            "페이지", "비고(옵션)", "색상", "용지", "과금액(원)", "현재 상태"
        ])
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # 🌟 [핵심 변경 사항: 컬럼 리사이즈 및 캐싱 로직]
        header = self.table.horizontalHeader()
        # 1. 사용자가 마우스로 컬럼 너비를 자유롭게 드래그 조절 가능하도록 설정
        header.setSectionResizeMode(QHeaderView.Interactive)
        # 2. 마지막 컬럼(현재 상태)은 남은 여백을 꽉 채우도록 설정
        header.setStretchLastSection(True)
        # 3. 마우스로 너무 작게 줄여서 글씨가 안보이는 현상 방지 (최소 60px)
        header.setMinimumSectionSize(60)

        # 4. 관리자가 이전에 조절해둔 너비 상태가 캐싱되어 있다면 복원
        saved_state = self.settings.value("table_header_state")
        if saved_state:
            header.restoreState(saved_state)
        else:
            # 최초 실행 시 내용이 긴 문서명 컬럼을 기본적으로 넓게 할당
            self.table.setColumnWidth(3, 250)
            self.table.setColumnWidth(1, 150) # 인쇄 시간도 넓게 할당

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        self.load_data()

    # 🌟 [복구] 수정/삭제 모드 토글 로직
    def toggle_edit_mode(self):
        self.is_edit_mode = not self.is_edit_mode
        if self.is_edit_mode:
            self.edit_btn.setText("❌ 취소 (일반 모드)")
            self.edit_btn.setStyleSheet("background-color: #ffcdd2; font-weight: bold; font-size: 13px; border-radius: 5px;")
        else:
            self.edit_btn.setText("✏️ 로그 삭제 모드")
            self.edit_btn.setStyleSheet("background-color: #f0f0f0; font-weight: bold; font-size: 13px; border-radius: 5px;")
        self.load_data()

    def load_data(self):
        if not os.path.exists(DB_PATH): return
            
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, log_time, os_user, file_name, printer_name, 
                       total_pages, remark, color_mode, paper_size, 
                       calculated_price, print_status 
                FROM PrintLogs 
                ORDER BY log_time DESC LIMIT 500
            """)
            rows = cursor.fetchall()
            conn.close()

            self.table.setRowCount(0)
            
            for row_idx, row_data in enumerate(rows):
                self.table.insertRow(row_idx)
                
                log_id, log_time, os_user, file_name, printer_name, total_pages, remark, color_mode, paper_size, price, status = row_data
                color_str = "컬러" if color_mode == 2 else ("흑백" if color_mode == 1 else "알수없음")
                paper_str = "A3" if paper_size == 8 else ("A4" if paper_size == 9 else "기타")
                
                # 🌟 [복구] 삭제 모드일 경우 LogID 칸에 삭제 버튼 삽입
                if self.is_edit_mode:
                    del_btn = QPushButton("🗑️ 삭제")
                    del_btn.setStyleSheet("color: red; border: 1px solid red; border-radius: 3px; font-weight: bold;")
                    del_btn.setCursor(Qt.PointingHandCursor)
                    del_btn.clicked.connect(lambda checked=False, lid=log_id: self.delete_log(lid))
                    self.table.setCellWidget(row_idx, 0, del_btn)
                else:
                    id_item = QTableWidgetItem(str(log_id))
                    id_item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, 0, id_item)

                items = [
                    QTableWidgetItem(str(log_time)[:19]), QTableWidgetItem(str(os_user)),
                    QTableWidgetItem(str(file_name)), QTableWidgetItem(str(printer_name)),
                    QTableWidgetItem(f"{total_pages}장"), QTableWidgetItem(str(remark) if remark else "-"),
                    QTableWidgetItem(color_str), QTableWidgetItem(paper_str),
                    QTableWidgetItem(f"{price:,} 원" if price is not None else "0 원"), QTableWidgetItem(str(status))
                ]
                
                for col_idx, item in enumerate(items, start=1): # 0번(LogID)은 제외하고 매핑
                    item.setTextAlignment(Qt.AlignCenter)
                    if status and "승인 대기" in status:
                        item.setForeground(QBrush(QColor("darkorange")))
                        font = item.font(); font.setBold(True); item.setFont(font)
                    elif status and ("반려" in status or "취소" in status):
                        item.setForeground(QBrush(QColor("red")))
                    elif status and ("조정" in status or "환불" in status):
                        item.setForeground(QBrush(QColor("blue")))
                        
                    self.table.setItem(row_idx, col_idx, item)

        except Exception as e:
            QMessageBox.critical(self, "데이터 로드 오류", f"데이터베이스를 불러오는 중 문제가 발생했습니다.\n{e}")

    # 🌟 [복구] 개별 데이터 영구 삭제 로직
    def delete_log(self, log_id):
        reply = QMessageBox.question(self, "삭제 확인", f"LogID {log_id} 데이터를 완전히 삭제하시겠습니까?\n이 작업은 되돌릴 수 없으며 과금 통계에서도 제외됩니다.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM PrintLogs WHERE id=?", (log_id,))
                conn.commit()
                conn.close()
                QMessageBox.information(self, "삭제 완료", "데이터가 영구적으로 삭제되었습니다.")
                self.refresh_requested.emit() # 전체 화면 갱신 시그널
            except Exception as e:
                QMessageBox.critical(self, "오류", f"데이터 삭제 실패: {e}")

    def show_context_menu(self, position):
        if self.is_edit_mode: return # 수정 모드일 때는 우클릭 방지
        
        row = self.table.rowAt(position.y())
        if row < 0: return

        # LogID 추출 (위젯이 들어있을 수 있으므로 안전하게 처리)
        log_id_item = self.table.item(row, 0)
        if not log_id_item: return
        log_id = int(log_id_item.text())
        
        status_item = self.table.item(row, 10)
        file_name_item = self.table.item(row, 3)
        current_status = status_item.text()
        file_name = file_name_item.text()

        menu = QMenu()
        if "승인 대기" in current_status:
            action_approve = menu.addAction("✅ 인쇄 승인 (출력 허용)")
            action_reject = menu.addAction("❌ 인쇄 반려 (대기열 파기)")
        else:
            action_refund = menu.addAction("💰 과금 단가 수동 조정 (환불/할인)")

        action = menu.exec(self.table.viewport().mapToGlobal(position))
        if action:
            if action.text() == "✅ 인쇄 승인 (출력 허용)":
                if QMessageBox.question(self, "승인 확인", f"'{file_name}' 인쇄를 승인하시겠습니까?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                    self.update_print_status(log_id, "승인 완료", "관리자 승인")
            elif action.text() == "❌ 인쇄 반려 (대기열 파기)":
                if QMessageBox.question(self, "반려 확인", f"'{file_name}' 인쇄를 반려하시겠습니까?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                    self.update_print_status(log_id, "반려됨", "관리자 반려")
            elif action.text() == "💰 과금 단가 수동 조정 (환불/할인)":
                self.handle_refund(log_id)

    def update_print_status(self, log_id, status, reason):
        # 🌟 [복구] Double Action 방어 로직: DB를 한 번 더 체크하여 중복 승인 방지
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT print_status FROM PrintLogs WHERE id=?", (log_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] != "승인 대기" and status in ["승인 완료", "반려됨"]:
                QMessageBox.warning(self, "경고", "해당 인쇄물은 이미 승인되거나 처리된 항목입니다.")
                self.refresh_requested.emit()
                return
        except Exception as e:
            pass # DB 체크 실패 시에도 다음 단계로 진행 (안전망)

        try:
            url = f"http://127.0.0.1:8000/api/print-log/status-update"
            res = requests.post(url, json={"log_id": log_id, "status": status, "reason": reason}, timeout=3)
            if res.status_code == 200:
                QMessageBox.information(self, "성공", f"정상적으로 [{status}] 처리되었습니다.")
                self.refresh_requested.emit() # 완료 후 전체 갱신
            else:
                QMessageBox.warning(self, "실패", "서버가 요청을 거부했습니다.")
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "통신 오류", f"중앙 서버(FastAPI)와 연결할 수 없습니다.\n{e}")

    def handle_refund(self, log_id):
        new_price, ok = QInputDialog.getInt(self, "단가 수동 조정", "변경할 최종 요금을 입력하세요 (0원=전액 환불):", 0, 0, 9999999, 10)
        if ok:
            reason, ok2 = QInputDialog.getText(self, "조정 사유", "조정 사유를 입력하세요:")
            if ok2:
                try:
                    url = f"http://127.0.0.1:8000/api/print-log/{log_id}/refund"
                    res = requests.post(url, json={"new_price": new_price, "reason": reason}, timeout=3)
                    if res.status_code == 200:
                        QMessageBox.information(self, "성공", f"요금이 {new_price:,}원으로 변경되었습니다.")
                        self.refresh_requested.emit() # 환불 후 전체 통계 즉시 갱신
                    else:
                        QMessageBox.warning(self, "실패", "요금 조정을 실패했습니다.")
                except requests.exceptions.RequestException as e:
                    QMessageBox.critical(self, "통신 오류", f"중앙 서버(FastAPI)와 연결할 수 없습니다.\n{e}")

    def closeEvent(self, event):
        """[Phase 6 보안/UX] 탭이 닫히거나 프로그램 종료 시 현재 컬럼 너비 상태를 캐시에 영구 저장"""
        self.settings.setValue("table_header_state", self.table.horizontalHeader().saveState())
        super().closeEvent(event)