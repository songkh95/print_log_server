# Manager_Console/main.py
import sys
import sqlite3
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

# --- [수정] DB_PATH 및 폴더 생성 로직 ---
PROGRAM_DATA_DIR = r"C:\ProgramData\MyPrintMonitor"
DB_PATH = os.path.join(PROGRAM_DATA_DIR, "print_monitor.db")

# 서버(server.py)보다 UI를 먼저 실행할 경우를 대비해 폴더를 미리 생성해 둡니다.
os.makedirs(PROGRAM_DATA_DIR, exist_ok=True)
# ------------------------------------------

# =========================================================
# 🌟 [신규] 사용자 정보 매핑 팝업창 (Dialog)
# =========================================================
class UserMappingDialog(QDialog):
    def __init__(self, uuid, current_name, current_dept, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용자 정보 매핑 (수동 등록)")
        self.setFixedSize(350, 200)

        layout = QFormLayout(self)
        
        self.uuid_label = QLabel(uuid)
        self.uuid_label.setStyleSheet("color: gray;")
        
        # '미등록 사용자'면 빈칸으로 띄워주고, 등록되어 있으면 기존 이름 표시
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
# 메인 윈도우 UI
# =========================================================
class ManagerConsoleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("프린트 과금 및 모니터링 시스템 - 통합 관리자 콘솔")
        self.resize(1150, 700)
        self.setStyleSheet("font-size: 14px;")
        
        self.upgrade_db_schema()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_logs = QWidget()
        self.tab_users = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_logs, "🖨️ 인쇄 영수증 내역")
        self.tabs.addTab(self.tab_users, "👤 기기 및 사용자 관리")
        self.tabs.addTab(self.tab_settings, "⚙️ 과금 정책 설정")

        self.init_tab_logs()
        self.init_tab_users()
        self.init_tab_settings()

        self.load_all_data()

    def upgrade_db_schema(self):
        # DB 파일이 없으면 여기서 생성될 수 있으므로 폴더가 반드시 있어야 합니다.
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE PricingPolicy ADD COLUMN ColorMultiplier REAL DEFAULT 2.0")
            cursor.execute("UPDATE PricingPolicy SET ColorMultiplier = 1.0 WHERE PaperSize = 9")
            cursor.execute("UPDATE PricingPolicy SET ColorMultiplier = Multiplier WHERE PaperSize = 8")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        conn.close()

    def init_tab_logs(self):
        layout = QVBoxLayout(self.tab_logs)
        
        top_layout = QHBoxLayout()
        title = QLabel("📊 실시간 인쇄 과금 대시보드")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        refresh_btn = QPushButton("🔄 데이터 새로고침")
        refresh_btn.setFixedSize(150, 40)
        refresh_btn.clicked.connect(self.load_all_data)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(8)
        self.table_logs.setHorizontalHeaderLabels([
            "인쇄 시간", "사용자명 (부서)", "문서명", "용지", "색상", "페이지", "과금액", "비고 (경고)"
        ])
        
        self.table_logs.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_logs.setColumnWidth(0, 160)
        self.table_logs.setColumnWidth(1, 160) # 사용자명 칸
        self.table_logs.setColumnWidth(2, 280)
        self.table_logs.setColumnWidth(3, 70)
        self.table_logs.setColumnWidth(4, 70)
        self.table_logs.setColumnWidth(5, 70)
        self.table_logs.setColumnWidth(6, 100)
        self.table_logs.setColumnWidth(7, 160)
        
        layout.addWidget(self.table_logs)

    def init_tab_users(self):
        layout = QVBoxLayout(self.tab_users)
        
        title = QLabel("👤 사내망 연결 기기 목록 (더블클릭하여 이름 설정)")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.table_users = QTableWidget()
        self.table_users.setColumnCount(5)
        self.table_users.setHorizontalHeaderLabels([
            "기기 고유번호(UUID)", "사용자명 (매핑)", "부서", "상태", "마지막 생존 신고"
        ])
        
        self.table_users.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_users.setColumnWidth(0, 320)
        self.table_users.setColumnWidth(1, 180)
        self.table_users.setColumnWidth(2, 180)
        self.table_users.setColumnWidth(3, 120)
        self.table_users.setColumnWidth(4, 180)
        
        # 🌟 [신규] 더블클릭 이벤트 연결
        self.table_users.cellDoubleClicked.connect(self.open_user_mapping_popup)

        layout.addWidget(self.table_users)

    # 🌟 [신규] 더블클릭 시 실행되는 함수
    def open_user_mapping_popup(self, row, column):
        uuid = self.table_users.item(row, 0).text()
        current_name = self.table_users.item(row, 1).text()
        current_dept = self.table_users.item(row, 2).text()

        dialog = UserMappingDialog(uuid, current_name, current_dept, self)
        
        if dialog.exec() == QDialog.Accepted:
            new_name, new_dept = dialog.get_data()
            if new_name:
                if not new_dept: new_dept = "미배정"
                
                # DB 업데이트
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE Users SET UserName=?, Department=? WHERE UUID=?", (new_name, new_dept, uuid))
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "성공", f"[{new_name}] 님의 정보가 성공적으로 등록되었습니다!")
                self.load_all_data() # 새로고침
            else:
                QMessageBox.warning(self, "경고", "사용자 이름은 필수 입력 항목입니다.")

    def init_tab_settings(self):
        layout = QVBoxLayout(self.tab_settings)
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

    def load_all_data(self):
        if not os.path.exists(DB_PATH): return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 🌟 [변경] JOIN 쿼리: 영수증에 UUID 대신 사용자 테이블의 이름과 부서를 가져옵니다!
        cursor.execute('''
            SELECT p.PrintTime, u.UserName, u.Department, p.FileName, p.PaperSize, p.ColorType, p.TotalPages, p.CalculatedPrice, p.Remark, p.User_UUID 
            FROM PrintLogs p 
            LEFT JOIN Users u ON p.User_UUID = u.UUID 
            ORDER BY p.LogID DESC
        ''')
        logs = cursor.fetchall()
        self.table_logs.setRowCount(0)
        for row_idx, row_data in enumerate(logs):
            self.table_logs.insertRow(row_idx)
            time_str = row_data[0][:19]
            
            # 사용자명 처리 (미등록이거나 정보가 없으면 UUID 축약 표기)
            user_name = row_data[1]
            dept = row_data[2]
            uuid_str = row_data[9]
            if user_name and user_name != "미등록 사용자":
                display_user = f"{user_name} ({dept})"
            else:
                display_user = uuid_str[:13] + "..."
                
            file_name = row_data[3]
            paper_size = "A4" if row_data[4] == 9 else ("A3" if row_data[4] == 8 else str(row_data[4]))
            color_str = "컬러" if row_data[5] == 2 else "흑백"
            pages = f"{row_data[6]}장"
            price = f"{row_data[7]:,}원"
            remark = row_data[8]

            items = [QTableWidgetItem(time_str), QTableWidgetItem(display_user), QTableWidgetItem(file_name),
                     QTableWidgetItem(paper_size), QTableWidgetItem(color_str), QTableWidgetItem(pages),
                     QTableWidgetItem(price), QTableWidgetItem(remark)]

            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter if col_idx != 2 else Qt.AlignLeft|Qt.AlignVCenter)
                if "⚠️" in remark: item.setBackground(QColor(255, 200, 200))
                self.table_logs.setItem(row_idx, col_idx, item)

        cursor.execute("SELECT UUID, UserName, Department, Status, LastHeartbeat FROM Users ORDER BY LastHeartbeat DESC")
        users = cursor.fetchall()
        self.table_users.setRowCount(0)
        for row_idx, row_data in enumerate(users):
            self.table_users.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                # 생존신고 시간 축약
                if col_idx == 4 and data: data = str(data)[:19]
                
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignCenter)
                # 수정 불가(읽기 전용) 모드로 변경하여 더블클릭 시 팝업만 뜨게 함
                item.setFlags(item.flags() ^ Qt.ItemIsEditable) 
                
                if col_idx == 1 and data == "미등록 사용자": item.setBackground(QColor(255, 255, 150))
                self.table_users.setItem(row_idx, col_idx, item)

        cursor.execute("SELECT BaseMonoPrice, BaseColorPrice FROM PricingPolicy WHERE PaperSize=9")
        a4_policy = cursor.fetchone()
        if a4_policy:
            self.input_a4_mono.setText(str(a4_policy[0]))
            self.input_a4_color.setText(str(a4_policy[1]))
            
        try:
            cursor.execute("SELECT Multiplier, ColorMultiplier FROM PricingPolicy WHERE PaperSize=8")
            a3_policy = cursor.fetchone()
            if a3_policy:
                self.input_a3_mono_multi.setText(str(a3_policy[0]))
                self.input_a3_color_multi.setText(str(a3_policy[1] if a3_policy[1] is not None else a3_policy[0]))
        except sqlite3.OperationalError:
            pass

        conn.close()

    def save_settings(self):
        try:
            mono = int(self.input_a4_mono.text())
            color = int(self.input_a4_color.text())
            mono_multi = float(self.input_a3_mono_multi.text())
            color_multi = float(self.input_a3_color_multi.text())
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE PricingPolicy SET BaseMonoPrice=?, BaseColorPrice=? WHERE PaperSize=9", (mono, color))
            cursor.execute("UPDATE PricingPolicy SET BaseMonoPrice=?, BaseColorPrice=?, Multiplier=?, ColorMultiplier=? WHERE PaperSize=8", 
                           (mono, color, mono_multi, color_multi))
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "성공", "과금 정책이 성공적으로 저장되었습니다!\n새로운 요금 정책을 완벽히 적용하려면, 켜져있는 관리자 서버(server.py) 파워셸 창을 한 번 껐다 켜주세요.")
        except ValueError:
            QMessageBox.warning(self, "오류", "단가와 배수는 반드시 숫자로 입력해야 합니다.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ManagerConsoleWindow()
    window.show()
    sys.exit(app.exec())