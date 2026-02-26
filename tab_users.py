import sqlite3
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from constants import DB_PATH

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