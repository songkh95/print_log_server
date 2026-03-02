# Manager_Console/tab_users.py
import sqlite3
import os
from datetime import datetime, timedelta
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal, QSettings
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
        # 🌟 [Phase 6 UX 향상] 설정 저장을 위한 QSettings 객체 초기화
        self.settings = QSettings("MyPrintMonitor", "ManagerConsole_Users")
        
        layout = QVBoxLayout(self)
        
        # --- 상단 컨트롤 패널 ---
        top_layout = QHBoxLayout()
        title_label = QLabel("👤 사내망 연결 기기 목록 (더블클릭하여 설정)")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        
        btn_refresh = QPushButton("🔄 기기 상태 갱신")
        btn_refresh.setFixedSize(160, 40)
        btn_refresh.setStyleSheet("font-weight: bold; font-size: 13px; background-color: #e0f7fa; border-radius: 5px;")
        btn_refresh.clicked.connect(self.load_data)
        
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(btn_refresh)
        layout.addLayout(top_layout)

        # --- 메인 테이블 ---
        self.table_users = QTableWidget()
        self.table_users.setColumnCount(6)
        self.table_users.setHorizontalHeaderLabels([
            "기기 고유번호(UUID)", "사용자명 (매핑)", "부서", "상태", "마지막 생존 신고", "통제 정책(승인 기준)"
        ])
        
        # 🌟 [UX 업데이트] 사용자가 컬럼 폭을 조정하고, 이를 영구 저장/복원
        header = self.table_users.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        saved_state = self.settings.value("users_header_state")
        if saved_state:
            header.restoreState(saved_state)
        else:
            # 최초 구동 시의 기본 폭 설정
            self.table_users.setColumnWidth(0, 320)
            self.table_users.setColumnWidth(1, 130)
            self.table_users.setColumnWidth(2, 130)
            self.table_users.setColumnWidth(3, 100)
            self.table_users.setColumnWidth(4, 180)
        
        self.table_users.cellDoubleClicked.connect(self.open_user_mapping_popup)
        self.table_users.setAlternatingRowColors(True)
        layout.addWidget(self.table_users)
        
        self.load_data()

    def open_user_mapping_popup(self, row, column):
        uuid = self.table_users.item(row, 0).text()
        current_name = self.table_users.item(row, 1).text()
        current_dept = self.table_users.item(row, 2).text()
        
        raw_limits = self.table_users.item(row, 5).data(Qt.UserRole)
        c_limit, m_limit = raw_limits if raw_limits else (None, None)

        dialog = UserMappingDialog(uuid, current_name, current_dept, c_limit, m_limit, self)
        if dialog.exec() == QDialog.Accepted:
            new_name, new_dept, new_c, new_m = dialog.get_data()
            if new_name:
                new_dept = new_dept if new_dept else "미배정"
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE Users 
                        SET os_user=?, department=?, color_limit=?, mono_limit=? 
                        WHERE uuid=?
                    """, (new_name, new_dept, new_c, new_m, uuid))
                    conn.commit()
                    conn.close()
                    QMessageBox.information(self, "성공", f"[{new_name}] 님의 정보가 저장되었습니다!")
                    self.load_data() 
                except Exception as e:
                    QMessageBox.warning(self, "저장 실패", f"DB 업데이트 중 오류 발생: {e}")
            else:
                QMessageBox.warning(self, "경고", "사용자 이름은 필수 입력 항목입니다.")

    # ====================================================================
    # 🌟 [불도저 로직] 어떤 에러가 나도 화면이 하얗게 멈추지 않도록 극도로 견고하게 설계
    # ====================================================================
    def load_data(self):
        if not os.path.exists(DB_PATH): 
            print("⚠️ [UI] DB 파일을 찾을 수 없습니다.")
            return
            
        try:
            conn = sqlite3.connect(DB_PATH)
            # 데이터를 가져올 때 Dict 형태로 반환되도록 하여 인덱스 에러 방지
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()
            
            # 먼저 새 스키마(os_user, color_limit 등)로 시도
            try:
                cursor.execute("SELECT * FROM Users ORDER BY last_heartbeat DESC")
                users = cursor.fetchall()
            except sqlite3.OperationalError:
                # 새 스키마가 없으면 옛날 스키마(UserName, ColorLimit 등)로 재시도
                cursor.execute("SELECT * FROM Users ORDER BY LastHeartbeat DESC")
                users = cursor.fetchall()

            self.table_users.setRowCount(0)
            now = datetime.now()
            
            for row_idx, row_data in enumerate(users):
                self.table_users.insertRow(row_idx)
                
                # 딕셔너리처럼 접근하여 대소문자나 옛날/새 컬럼명 모두 유연하게 처리
                row_dict = dict(row_data)
                
                uuid = row_dict.get('uuid') or row_dict.get('UUID', '알수없음')
                name = row_dict.get('os_user') or row_dict.get('UserName', '미등록 사용자')
                dept = row_dict.get('department') or row_dict.get('Department', '미배정')
                hb = row_dict.get('last_heartbeat') or row_dict.get('LastHeartbeat')
                c_lim = row_dict.get('color_limit') or row_dict.get('ColorLimit')
                m_lim = row_dict.get('mono_limit') or row_dict.get('MonoLimit')
                
                status = "🔴 오프라인"
                hb_str = "-"
                
                if hb:
                    try:
                        hb_time = datetime.strptime(str(hb)[:19], "%Y-%m-%d %H:%M:%S")
                        if now - hb_time < timedelta(minutes=5):
                            status = "🟢 온라인"
                        hb_str = str(hb)[:19]
                    except: pass
                
                pol_texts = []
                if c_lim is not None: pol_texts.append(f"컬러:{'무제한' if c_lim>=999999 else str(c_lim)+'장'}")
                if m_lim is not None: pol_texts.append(f"흑백:{'무제한' if m_lim>=999999 else str(m_lim)+'장'}")
                display_policy = ", ".join(pol_texts) if pol_texts else "🏢 전사 공통"
                
                items = [
                    QTableWidgetItem(str(uuid)), QTableWidgetItem(str(name)), QTableWidgetItem(str(dept)),
                    QTableWidgetItem(status), QTableWidgetItem(hb_str), QTableWidgetItem(display_policy)
                ]
                
                items[5].setData(Qt.UserRole, (c_lim, m_lim))
                
                for col_idx, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable) 
                    
                    if col_idx == 1 and name == "미등록 사용자": item.setBackground(QColor(255, 255, 150))
                    if col_idx == 5 and pol_texts: item.setBackground(QColor(220, 240, 255))
                    
                    self.table_users.setItem(row_idx, col_idx, item)
                    
        except Exception as e:
            QMessageBox.critical(self, "데이터 로드 실패", f"기기 목록을 불러오는 중 오류가 발생했습니다.\n{e}")
        finally:
            if 'conn' in locals(): conn.close()

    # 🌟 [보안/UX] 프로그램 종료 시 테이블 헤더 상태 저장
    def closeEvent(self, event):
        self.settings.setValue("users_header_state", self.table_users.horizontalHeader().saveState())
        super().closeEvent(event)