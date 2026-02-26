# Manager_Console/tab_users.py
import sqlite3
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from constants import DB_PATH

class UserMappingDialog(QDialog):
    def __init__(self, uuid, current_name, current_dept, c_limit, m_limit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용자 정보 및 예외 정책 매핑")
        self.setFixedSize(400, 280)

        layout = QFormLayout(self)
        self.uuid_label = QLabel(uuid)
        self.uuid_label.setStyleSheet("color: gray;")
        
        self.name_input = QLineEdit(current_name if current_name != "미등록 사용자" else "")
        self.name_input.setPlaceholderText("예: 홍길동")
        
        self.dept_input = QLineEdit(current_dept if current_dept != "미배정" else "")
        self.dept_input.setPlaceholderText("예: 영업1팀")
        
        # 🌟 [신규] 예외 한도 입력칸
        self.c_limit_input = QLineEdit(str(c_limit) if c_limit is not None else "")
        self.c_limit_input.setPlaceholderText("빈칸 시 '전사 공통 정책' 적용 (무제한은 999999)")
        
        self.m_limit_input = QLineEdit(str(m_limit) if m_limit is not None else "")
        self.m_limit_input.setPlaceholderText("빈칸 시 '전사 공통 정책' 적용")

        layout.addRow("기기 고유번호:", self.uuid_label)
        layout.addRow("👤 사용자 이름:", self.name_input)
        layout.addRow("🏢 소속 부서:", self.dept_input)
        layout.addRow("🎨 컬러 예외 한도 (장):", self.c_limit_input)
        layout.addRow("◼️ 흑백 예외 한도 (장):", self.m_limit_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 저장")
        cancel_btn = QPushButton("취소")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def get_data(self):
        c_val = self.c_limit_input.text().strip()
        m_val = self.m_limit_input.text().strip()
        c_limit = int(c_val) if c_val.isdigit() else None
        m_limit = int(m_val) if m_val.isdigit() else None
        
        return self.name_input.text().strip(), self.dept_input.text().strip(), c_limit, m_limit


class UsersTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("👤 사내망 연결 기기 목록 (더블클릭하여 설정)")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.table_users = QTableWidget()
        self.table_users.setColumnCount(6) # 컬럼 1개 추가
        self.table_users.setHorizontalHeaderLabels([
            "기기 고유번호(UUID)", "사용자명 (매핑)", "부서", "상태", "마지막 생존 신고", "통제 정책(승인 기준)"
        ])
        self.table_users.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_users.horizontalHeader().setStretchLastSection(True)
        self.table_users.setColumnWidth(0, 320); self.table_users.setColumnWidth(1, 130)
        self.table_users.setColumnWidth(2, 130); self.table_users.setColumnWidth(3, 80); self.table_users.setColumnWidth(4, 180)
        
        self.table_users.cellDoubleClicked.connect(self.open_user_mapping_popup)
        layout.addWidget(self.table_users)

    def open_user_mapping_popup(self, row, column):
        uuid = self.table_users.item(row, 0).text()
        current_name = self.table_users.item(row, 1).text()
        current_dept = self.table_users.item(row, 2).text()
        
        # UserRole에 숨겨둔 raw limit 데이터 가져오기
        raw_limits = self.table_users.item(row, 5).data(Qt.UserRole)
        c_limit, m_limit = raw_limits if raw_limits else (None, None)

        dialog = UserMappingDialog(uuid, current_name, current_dept, c_limit, m_limit, self)
        if dialog.exec() == QDialog.Accepted:
            new_name, new_dept, new_c, new_m = dialog.get_data()
            if new_name:
                new_dept = new_dept if new_dept else "미배정"
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Users 
                    SET UserName=?, Department=?, ColorLimit=?, MonoLimit=? 
                    WHERE UUID=?
                """, (new_name, new_dept, new_c, new_m, uuid))
                conn.commit()
                conn.close()
                QMessageBox.information(self, "성공", f"[{new_name}] 님의 정보와 정책이 성공적으로 저장되었습니다!")
                self.refresh_requested.emit()
            else:
                QMessageBox.warning(self, "경고", "사용자 이름은 필수 입력 항목입니다.")

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT UUID, UserName, Department, Status, LastHeartbeat, ColorLimit, MonoLimit FROM Users ORDER BY LastHeartbeat DESC")
        except sqlite3.OperationalError:
            cursor.execute("SELECT UUID, UserName, Department, Status, LastHeartbeat, NULL, NULL FROM Users ORDER BY LastHeartbeat DESC")
            
        users = cursor.fetchall()
        self.table_users.setRowCount(0)
        
        for row_idx, row_data in enumerate(users):
            self.table_users.insertRow(row_idx)
            
            uuid, name, dept, status, hb, c_lim, m_lim = row_data
            if hb: hb = str(hb)[:19]
            
            # 🌟 [신규] 정책 표시 문자열 조립
            pol_texts = []
            if c_lim is not None: pol_texts.append(f"컬러:{'무제한' if c_lim>=999999 else str(c_lim)+'장'}")
            if m_lim is not None: pol_texts.append(f"흑백:{'무제한' if m_lim>=999999 else str(m_lim)+'장'}")
            display_policy = ", ".join(pol_texts) if pol_texts else "🏢 전사 공통"
            
            items = [
                QTableWidgetItem(uuid), QTableWidgetItem(name), QTableWidgetItem(dept),
                QTableWidgetItem(status), QTableWidgetItem(str(hb)), QTableWidgetItem(display_policy)
            ]
            
            # raw data 숨겨두기
            items[5].setData(Qt.UserRole, (c_lim, m_lim))
            
            for col_idx, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable) 
                
                if col_idx == 1 and name == "미등록 사용자": item.setBackground(QColor(255, 255, 150))
                # 공통 정책이 아닌 예외 정책이 적용된 유저는 푸른색으로 하이라이트
                if col_idx == 5 and pol_texts: item.setBackground(QColor(220, 240, 255))
                
                self.table_users.setItem(row_idx, col_idx, item)
                
        conn.close()