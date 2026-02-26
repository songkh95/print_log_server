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
        self.is_edit_mode = False
        
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        title = QLabel("📊 실시간 인쇄 과금 대시보드")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-30)) 
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        
        search_btn = QPushButton("🔍 조회")
        search_btn.setFixedSize(80, 35)
        search_btn.clicked.connect(self.refresh_requested.emit)
        
        self.edit_btn = QPushButton("✏️ 수정")
        self.edit_btn.setFixedSize(90, 40)
        self.edit_btn.setCheckable(True)
        self.edit_btn.clicked.connect(self.toggle_edit_mode)

        self.cancel_edit_btn = QPushButton("❌ 취소")
        self.cancel_edit_btn.setFixedSize(80, 40)
        self.cancel_edit_btn.setVisible(False) 
        self.cancel_edit_btn.clicked.connect(self.cancel_edit_mode)

        refresh_btn = QPushButton("🔄 데이터 새로고침")
        refresh_btn.setFixedSize(150, 40)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(QLabel("조회 기간 :"))
        top_layout.addWidget(self.start_date)
        top_layout.addWidget(QLabel("~"))
        top_layout.addWidget(self.end_date)
        top_layout.addWidget(search_btn)
        top_layout.addSpacing(20) 
        top_layout.addWidget(self.edit_btn)
        top_layout.addWidget(self.cancel_edit_btn) 
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(9) 
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
        
        self.table_logs.setColumnWidth(0, 50)  
        self.table_logs.setColumnWidth(1, 160) 
        self.table_logs.setColumnWidth(2, 160) 
        self.table_logs.setColumnWidth(3, 280) 
        self.table_logs.setColumnWidth(4, 70)  
        self.table_logs.setColumnWidth(5, 80)  
        self.table_logs.setColumnWidth(6, 150) 
        self.table_logs.setColumnWidth(7, 100) 
        
        self.table_logs.setColumnHidden(0, True)
        self.table_logs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_logs.customContextMenuRequested.connect(self.show_log_context_menu)
        
        layout.addWidget(self.table_logs)

    def toggle_edit_mode(self):
        self.is_edit_mode = self.edit_btn.isChecked()
        if self.is_edit_mode:
            self.edit_btn.setText("✅ 완료")
            self.edit_btn.setStyleSheet("background-color: #ffe6e6; color: red; font-weight: bold;")
            self.cancel_edit_btn.setVisible(True)     
            self.table_logs.setColumnHidden(0, False) 
        else:
            self.edit_btn.setText("✏️ 수정")
            self.edit_btn.setStyleSheet("")
            self.cancel_edit_btn.setVisible(False)    
            self.table_logs.setColumnHidden(0, True)  

    def cancel_edit_mode(self):
        self.edit_btn.setChecked(False) 
        self.toggle_edit_mode()         

    def delete_log(self, log_id):
        reply = QMessageBox.question(self, "삭제 확인", 
            "해당 영수증 내역을 완전히 삭제하시겠습니까?\n(삭제된 데이터는 인쇄 통계에서도 영구적으로 제외됩니다.)", 
            QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM PrintLogs WHERE LogID = ?", (log_id,))
                conn.commit()
                self.refresh_requested.emit() 
            except Exception as e:
                QMessageBox.critical(self, "시스템 오류", f"삭제 중 오류가 발생했습니다: {e}")
            finally:
                conn.close()

    # ====================================================================
    # 🌟 [수정] 우클릭 메뉴 통합 (승인/반려 기능과 과금 조정 기능을 함께 표시)
    # ====================================================================
    def show_log_context_menu(self, pos):
        item = self.table_logs.itemAt(pos)
        if item is None: return
        
        row = item.row()
        time_item = self.table_logs.item(row, 1) 
        if not time_item: return
            
        log_id = time_item.data(Qt.UserRole)
        if not log_id: return
            
        color_item = self.table_logs.item(row, 5)
        current_color_text = color_item.text() if color_item else ""
        
        remark_item = self.table_logs.item(row, 8)
        remark_text = remark_item.text() if remark_item else "" 
        
        menu = QMenu(self)
        action_approve = None
        action_reject = None
        action_to_mono = None
        action_to_color = None
        
        # 1. 문서가 '승인 대기' 상태인 경우 -> 승인/반려 메뉴 최상단에 추가
        if "승인 대기" in remark_text:
            action_approve = menu.addAction("✅ 인쇄 승인 (프린터 전송)")
            action_reject = menu.addAction("❌ 인쇄 반려 (대기열 삭제)")
            menu.addSeparator() # 🌟 구분선을 넣어 메뉴 영역을 분리합니다.
            
        # 2. 과금 조정 메뉴 -> 문서 상태와 무관하게 항상 노출하여 조정 가능하게 함
        if current_color_text == "컬러":
            action_to_mono = menu.addAction("🛠️ 흑백 단가로 과금 조정 (환불/롤백)")
        else:
            action_to_color = menu.addAction("🛠️ 컬러 단가로 과금 조정 (오류 정정)")
        
        action = menu.exec(self.table_logs.viewport().mapToGlobal(pos))
        
        if action:
            if action == action_approve: self.process_approval(log_id, is_approved=True)
            elif action == action_reject: self.process_approval(log_id, is_approved=False)
            elif action == action_to_mono: self.adjust_billing(log_id, target_color_mode=1)
            elif action == action_to_color: self.adjust_billing(log_id, target_color_mode=2)

    # ====================================================================
    # 🌟 [수정] DB 상태 이중 체크 (Double Action 방지) 로직 추가
    # ====================================================================
    def process_approval(self, log_id, is_approved):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # [버그 방어] DB의 현재 상태를 다시 조회하여 이미 처리된 항목인지 검사합니다.
            cursor.execute("SELECT PrintStatus, Remark FROM PrintLogs WHERE LogID = ?", (log_id,))
            row = cursor.fetchone()
            if not row:
                QMessageBox.warning(self, "오류", "해당 데이터를 찾을 수 없습니다.")
                return
                
            current_status, old_remark = row
            
            if current_status != "승인 대기":
                QMessageBox.warning(self, "경고", "해당 인쇄물은 이미 승인되거나 처리된 항목입니다.")
                self.refresh_requested.emit() # 최신 상태로 강제 새로고침
                return

            # 정상 대기 중인 항목이라면 관리자에게 의사를 다시 묻습니다.
            status_str = "승인 완료" if is_approved else "반려됨"
            msg_title = "인쇄 승인" if is_approved else "인쇄 반려"
            msg_body = "해당 인쇄 작업을 승인하시겠습니까?\n(승인 시 프린터에서 즉시 출력이 시작됩니다.)" if is_approved else "해당 인쇄 작업을 반려하시겠습니까?\n(반려 시 사용자 PC의 대기열에서 즉시 파기됩니다.)"
            
            reply = QMessageBox.question(self, msg_title, msg_body, QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                new_remark = old_remark.replace("🚨 [승인 대기]", f"[{status_str}]")
                cursor.execute("UPDATE PrintLogs SET PrintStatus = ?, Remark = ? WHERE LogID = ?", (status_str, new_remark, log_id))
                conn.commit()
                QMessageBox.information(self, "처리 완료", f"해당 인쇄 작업이 {status_str} 처리되었습니다.")
                self.refresh_requested.emit()
                
        except Exception as e:
            QMessageBox.critical(self, "시스템 오류", f"처리 중 오류 발생: {e}")
        finally:
            conn.close()

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
                policy = cursor.fetchone()
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

    def load_data(self):
        import os
        if not os.path.exists(DB_PATH): return
        
        start_date_str = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_date_str = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
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
            
            time_str = row_data[0][:19]
            user_name, dept, uuid_str, log_id = row_data[1], row_data[2], row_data[9], row_data[10]
            display_user = f"{user_name} ({dept})" if user_name and user_name != "미등록 사용자" else uuid_str[:13] + "..."
            file_name = row_data[3]
            paper_size = "A4" if row_data[4] == 9 else ("A3" if row_data[4] == 8 else str(row_data[4]))
            color_str = "컬러" if row_data[5] == 2 else "흑백"
            pages = f"{row_data[6]}장"
            price = f"{row_data[7]:,}원"
            remark = row_data[8] if row_data[8] else ""

            del_btn = QPushButton("❌")
            del_btn.setStyleSheet("color: red; border: none; font-size: 14px;")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(lambda checked=False, lid=log_id: self.delete_log(lid))
            
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, log_id)

            items = [
                time_item, QTableWidgetItem(display_user), QTableWidgetItem(file_name),
                QTableWidgetItem(paper_size), QTableWidgetItem(color_str), QTableWidgetItem(pages),
                QTableWidgetItem(price), QTableWidgetItem(remark)
            ]

            self.table_logs.setCellWidget(row_idx, 0, del_btn)
            
            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter if col_idx != 2 else Qt.AlignLeft | Qt.AlignVCenter)
                if remark:
                    if "🚨 [승인 대기]" in remark: item.setBackground(QColor(255, 240, 150)) 
                    elif "[반려됨]" in remark: item.setBackground(QColor(240, 240, 240)) 
                    elif "⚠️" in remark: item.setBackground(QColor(255, 200, 200))
                    elif "관리자 조정" in remark: item.setBackground(QColor(220, 240, 255))
                    
                self.table_logs.setItem(row_idx, col_idx + 1, item)
                
        conn.close()