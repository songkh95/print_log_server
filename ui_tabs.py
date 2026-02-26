# Manager_Console/ui_tabs.py
import sqlite3
import os
from datetime import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

PROGRAM_DATA_DIR = r"C:\ProgramData\MyPrintMonitor"
DB_PATH = os.path.join(PROGRAM_DATA_DIR, "print_monitor.db")

# =========================================================
# 사용자 정보 매핑 팝업창 (Dialog)
# =========================================================
class UserMappingDialog(QDialog):
    def __init__(self, uuid, current_name, current_dept, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용자 정보 매핑 (수동 등록)")
        self.setFixedSize(350, 200)

        layout = QFormLayout(self)
        
        self.uuid_label = QLabel(uuid)
        self.uuid_label.setStyleSheet("color: gray;")
        
        self.name_input = QLineEdit(current_name if current_name != "미등록 사용자" else "")
        self.name_input.setPlaceholderText("예: 홍길동")
        
        self.dept_input = QLineEdit(current_dept if current_dept != "미배정" else "")
        self.dept_input.setPlaceholderText("예: 영업1팀")

        layout.addRow("기기 고유번호:", self.uuid_label)
        layout.addRow("👤 사용자 이름:", self.name_input)
        layout.addRow("🏢 소속 부서:", self.dept_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 저장")
        cancel_btn = QPushButton("취소")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def get_data(self):
        return self.name_input.text().strip(), self.dept_input.text().strip()


# =========================================================
# 1. 영수증 내역 탭 (LogsTab)
# =========================================================
class LogsTab(QWidget):
    refresh_requested = Signal() # 메인 윈도우에 새로고침을 요청하는 신호

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        title = QLabel("📊 실시간 인쇄 과금 대시보드")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        refresh_btn = QPushButton("🔄 데이터 새로고침")
        refresh_btn.setFixedSize(150, 40)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(8)
        self.table_logs.setHorizontalHeaderLabels([
            "인쇄 시간", "사용자명 (부서)", "문서명", "용지", "선택 색상", "스풀러 요청 페이지 ℹ️", "과금액", "비고 (경고)"
        ])
        
        self.table_logs.horizontalHeaderItem(5).setToolTip(
            "본 과금 시스템은 윈도우 OS 스풀러의 논리 페이지 기준으로 과금됩니다.\n"
            "사용자가 프린터 제조사 전용 드라이버의 '모아찍기'를 사용한 경우 실제 물리적 종이 매수와 다르게 과금될 수 있습니다.\n"
            "억울한 과금 클레임은 우클릭하여 [수동 조정]을 진행해 주세요."
        )
        
        self.table_logs.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_logs.horizontalHeader().setStretchLastSection(True) 
        self.table_logs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        self.table_logs.setColumnWidth(0, 160)
        self.table_logs.setColumnWidth(1, 160) 
        self.table_logs.setColumnWidth(2, 280)
        self.table_logs.setColumnWidth(3, 70)
        self.table_logs.setColumnWidth(4, 80)
        self.table_logs.setColumnWidth(5, 150)
        self.table_logs.setColumnWidth(6, 100)
        
        self.table_logs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_logs.customContextMenuRequested.connect(self.show_log_context_menu)
        
        layout.addWidget(self.table_logs)

    def show_log_context_menu(self, pos):
        item = self.table_logs.itemAt(pos)
        if item is None: return
        
        row = item.row()
        time_item = self.table_logs.item(row, 0) 
        if not time_item: return
            
        log_id = time_item.data(Qt.UserRole)
        if not log_id: return
            
        current_color_text = self.table_logs.item(row, 4).text()
        menu = QMenu(self)
        action_to_mono = None
        action_to_color = None
        
        if current_color_text == "컬러":
            action_to_mono = menu.addAction("🛠️ 흑백 단가로 과금 조정 (환불/롤백)")
        else:
            action_to_color = menu.addAction("🛠️ 컬러 단가로 과금 조정 (오류 정정)")
        
        action = menu.exec(self.table_logs.viewport().mapToGlobal(pos))
        
        if action == action_to_mono:
            self.adjust_billing(log_id, target_color_mode=1)
        elif action == action_to_color:
            self.adjust_billing(log_id, target_color_mode=2)

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
                
            reply = QMessageBox.question(
                self, "과금 수동 조정", 
                f"문서명: '{file_name}'\n\n관리자 직권으로 해당 인쇄물의 색상과 요금을 조정합니다.\n\n기존 청구액: {old_price:,} 원\n변경 청구액: {new_price:,} 원 ({color_name} 요금 적용)\n\n이 작업을 진행하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
                                         
            if reply == QMessageBox.Yes:
                today_str = datetime.now().strftime("%y/%m/%d %H:%M")
                audit_msg = f"[관리자 조정: {color_name} 요금으로 변경({today_str})]"
                new_remark = f"{remark} {audit_msg}" if remark else audit_msg
                
                cursor.execute("UPDATE PrintLogs SET CalculatedPrice = ?, Remark = ?, ColorType = ? WHERE LogID = ?", 
                               (new_price, new_remark, target_color_mode, log_id))
                conn.commit()
                QMessageBox.information(self, "처리 완료", f"색상이 {color_name}(으)로 변경되고 과금이 {new_price:,}원으로 성공적으로 조정되었습니다.")
                self.refresh_requested.emit() # 전체 새로고침 신호 발송
                
        except Exception as e:
            QMessageBox.critical(self, "시스템 오류", f"과금 조정 중 오류가 발생했습니다: {e}")
        finally:
            conn.close()

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.PrintTime, u.UserName, u.Department, p.FileName, p.PaperSize, p.ColorType, p.TotalPages, p.CalculatedPrice, p.Remark, p.User_UUID, p.LogID 
            FROM PrintLogs p LEFT JOIN Users u ON p.User_UUID = u.UUID ORDER BY p.LogID DESC
        ''')
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

            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, log_id)

            items = [time_item, QTableWidgetItem(display_user), QTableWidgetItem(file_name),
                     QTableWidgetItem(paper_size), QTableWidgetItem(color_str), QTableWidgetItem(pages),
                     QTableWidgetItem(price), QTableWidgetItem(remark)]

            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter if col_idx != 2 else Qt.AlignLeft|Qt.AlignVCenter)
                if remark:
                    if "⚠️" in remark: item.setBackground(QColor(255, 200, 200))
                    elif "관리자 조정" in remark: item.setBackground(QColor(220, 240, 255))
                self.table_logs.setItem(row_idx, col_idx, item)
        conn.close()


# =========================================================
# 2. 통계 탭 (StatsTab)
# =========================================================
class StatsTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        title = QLabel("📈 상세 인쇄 통계 및 과금 분석")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        refresh_btn = QPushButton("🔄 통계 새로고침")
        refresh_btn.setFixedSize(150, 40)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        group_billing = QGroupBox("💰 용지 및 색상별 정상 과금 통계")
        group_billing.setFont(QFont("Arial", 12, QFont.Bold))
        layout_billing = QVBoxLayout(group_billing)
        self.table_stats_billing = QTableWidget()
        self.table_stats_billing.setColumnCount(3)
        self.table_stats_billing.setHorizontalHeaderLabels(["구분 항목", "누적 페이지 수 (장)", "총 과금액 (원)"])
        self.table_stats_billing.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_stats_billing.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout_billing.addWidget(self.table_stats_billing)
        layout.addWidget(group_billing)

        group_exception = QGroupBox("🚨 예외 상황 통계 (취소 및 불확실한 데이터)")
        group_exception.setFont(QFont("Arial", 12, QFont.Bold))
        layout_exception = QVBoxLayout(group_exception)
        self.table_stats_exception = QTableWidget()
        self.table_stats_exception.setColumnCount(4)
        self.table_stats_exception.setHorizontalHeaderLabels(["예외 항목", "발생 건수", "관련 페이지 수", "관련 과금액 (원)"])
        self.table_stats_exception.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_stats_exception.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout_exception.addWidget(self.table_stats_exception)
        layout.addWidget(group_exception)

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try: cursor.execute("SELECT PaperSize, ColorType, TotalPages, Copies, CalculatedPrice, Remark, PrintStatus FROM PrintLogs")
        except sqlite3.OperationalError: cursor.execute("SELECT PaperSize, ColorType, TotalPages, Copies, CalculatedPrice, Remark, '완료' FROM PrintLogs")
        rows = cursor.fetchall()
        conn.close()

        stats = {
            'A4_Mono': {'pages': 0, 'price': 0}, 'A4_Color': {'pages': 0, 'price': 0},
            'A3_Mono': {'pages': 0, 'price': 0}, 'A3_Color': {'pages': 0, 'price': 0},
            'Total_Mono': {'pages': 0, 'price': 0}, 'Total_Color': {'pages': 0, 'price': 0},
            'Total_All': {'pages': 0, 'price': 0},
            'Cancelled': {'count': 0, 'pages': 0, 'price': 0}, 'Uncertain': {'count': 0, 'pages': 0, 'price': 0}
        }

        for row in rows:
            p_size, c_type, t_pages, copies, price, remark, status = row
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
                if "취소" in label: item.setForeground(QColor(150, 150, 150)) 
                elif "불확실" in label: item.setForeground(QColor(200, 50, 50)) 
                self.table_stats_exception.setItem(row_idx, i, item)


# =========================================================
# 3. 사용자 관리 탭 (UsersTab)
# =========================================================
class UsersTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("👤 사내망 연결 기기 목록 (더블클릭하여 이름 설정)")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.table_users = QTableWidget()
        self.table_users.setColumnCount(5)
        self.table_users.setHorizontalHeaderLabels(["기기 고유번호(UUID)", "사용자명 (매핑)", "부서", "상태", "마지막 생존 신고"])
        self.table_users.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_users.setColumnWidth(0, 320); self.table_users.setColumnWidth(1, 180)
        self.table_users.setColumnWidth(2, 180); self.table_users.setColumnWidth(3, 120); self.table_users.setColumnWidth(4, 180)
        
        self.table_users.cellDoubleClicked.connect(self.open_user_mapping_popup)
        layout.addWidget(self.table_users)

    def open_user_mapping_popup(self, row, column):
        uuid = self.table_users.item(row, 0).text()
        current_name = self.table_users.item(row, 1).text()
        current_dept = self.table_users.item(row, 2).text()

        dialog = UserMappingDialog(uuid, current_name, current_dept, self)
        if dialog.exec() == QDialog.Accepted:
            new_name, new_dept = dialog.get_data()
            if new_name:
                new_dept = new_dept if new_dept else "미배정"
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE Users SET UserName=?, Department=? WHERE UUID=?", (new_name, new_dept, uuid))
                conn.commit(); conn.close()
                QMessageBox.information(self, "성공", f"[{new_name}] 님의 정보가 성공적으로 등록되었습니다!")
                self.refresh_requested.emit()
            else:
                QMessageBox.warning(self, "경고", "사용자 이름은 필수 입력 항목입니다.")

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT UUID, UserName, Department, Status, LastHeartbeat FROM Users ORDER BY LastHeartbeat DESC")
        users = cursor.fetchall()
        self.table_users.setRowCount(0)
        for row_idx, row_data in enumerate(users):
            self.table_users.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                if col_idx == 4 and data: data = str(data)[:19]
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable) 
                if col_idx == 1 and data == "미등록 사용자": item.setBackground(QColor(255, 255, 150))
                self.table_users.setItem(row_idx, col_idx, item)
        conn.close()


# =========================================================
# 4. 설정 탭 (SettingsTab)
# =========================================================
class SettingsTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("⚙️ 용지별 과금 단가 설정")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        form_layout = QFormLayout()
        self.input_a4_mono = QLineEdit()
        self.input_a4_color = QLineEdit()
        self.input_a3_mono_multi = QLineEdit() 
        self.input_a3_color_multi = QLineEdit() 

        form_layout.addRow("A4 흑백 기본 단가 (원):", self.input_a4_mono)
        form_layout.addRow("A4 컬러 기본 단가 (원):", self.input_a4_color)
        form_layout.addRow("A3 흑백 요금 가중치 (배수):", self.input_a3_mono_multi)
        form_layout.addRow("A3 컬러 요금 가중치 (배수):", self.input_a3_color_multi)
        
        layout.addLayout(form_layout)

        save_btn = QPushButton("💾 정책 저장 및 적용")
        save_btn.setFixedSize(200, 50)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignCenter)
        layout.addStretch()

    def save_settings(self):
        try:
            mono, color = int(self.input_a4_mono.text()), int(self.input_a4_color.text())
            mono_multi, color_multi = float(self.input_a3_mono_multi.text()), float(self.input_a3_color_multi.text())
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE PricingPolicy SET BaseMonoPrice=?, BaseColorPrice=? WHERE PaperSize=9", (mono, color))
            cursor.execute("UPDATE PricingPolicy SET BaseMonoPrice=?, BaseColorPrice=?, Multiplier=?, ColorMultiplier=? WHERE PaperSize=8", 
                           (mono, color, mono_multi, color_multi))
            conn.commit(); conn.close()
            
            QMessageBox.information(self, "성공", "과금 정책이 성공적으로 저장되었습니다!\n새로운 요금 정책을 완벽히 적용하려면, 켜져있는 관리자 서버(server.py) 파워셸 창을 한 번 껐다 켜주세요.")
            self.refresh_requested.emit()
        except ValueError:
            QMessageBox.warning(self, "오류", "단가와 배수는 반드시 숫자로 입력해야 합니다.")

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT BaseMonoPrice, BaseColorPrice FROM PricingPolicy WHERE PaperSize=9")
        a4_policy = cursor.fetchone()
        if a4_policy:
            self.input_a4_mono.setText(str(a4_policy[0])); self.input_a4_color.setText(str(a4_policy[1]))
            
        try:
            cursor.execute("SELECT Multiplier, ColorMultiplier FROM PricingPolicy WHERE PaperSize=8")
            a3_policy = cursor.fetchone()
            if a3_policy:
                self.input_a3_mono_multi.setText(str(a3_policy[0]))
                self.input_a3_color_multi.setText(str(a3_policy[1] if a3_policy[1] is not None else a3_policy[0]))
        except sqlite3.OperationalError: pass
        conn.close()