# Manager_Console/tab_settings.py
import sqlite3
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from constants import DB_PATH

class SettingsTab(QWidget):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # --- 1. 요금 정책 설정 영역 ---
        group_pricing = QGroupBox("💰 용지별 과금 단가 설정")
        group_pricing.setFont(QFont("Arial", 12, QFont.Bold))
        form_pricing = QFormLayout(group_pricing)
        
        self.input_a4_mono = QLineEdit()
        self.input_a4_color = QLineEdit()
        self.input_a3_mono_multi = QLineEdit() 
        self.input_a3_color_multi = QLineEdit() 

        form_pricing.addRow("A4 흑백 기본 단가 (원):", self.input_a4_mono)
        form_pricing.addRow("A4 컬러 기본 단가 (원):", self.input_a4_color)
        form_pricing.addRow("A3 흑백 요금 가중치 (배수):", self.input_a3_mono_multi)
        form_pricing.addRow("A3 컬러 요금 가중치 (배수):", self.input_a3_color_multi)
        
        layout.addWidget(group_pricing)

        # --- 2. 🌟 [복구] 전사 공통 정책 통제 영역 ---
        group_control = QGroupBox("🛑 전사 공통 인쇄 통제 (승인 필요 조건)")
        group_control.setFont(QFont("Arial", 12, QFont.Bold))
        form_control = QFormLayout(group_control)
        
        self.input_control_mono = QLineEdit()
        self.input_control_mono.setPlaceholderText("빈칸 시 무제한")
        self.input_control_color = QLineEdit()
        self.input_control_color.setPlaceholderText("빈칸 시 무제한")
        
        form_control.addRow("흑백 인쇄 최대 허용(장) :", self.input_control_mono)
        form_control.addRow("컬러 인쇄 최대 허용(장) :", self.input_control_color)
        
        layout.addWidget(group_control)
        
        # --- 3. 저장 버튼 영역 ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_save = QPushButton("💾 전체 설정 저장")
        btn_save.setFixedSize(180, 45)
        btn_save.setStyleSheet("font-size: 14px; font-weight: bold;")
        btn_save.clicked.connect(self.save_data)
        
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.load_data()

    def save_data(self):
        if not os.path.exists(DB_PATH): return
        try:
            mono = int(self.input_a4_mono.text().strip())
            color = int(self.input_a4_color.text().strip())
            mono_multi = int(self.input_a3_mono_multi.text().strip())
            color_multi = int(self.input_a3_color_multi.text().strip())
            
            # 제한 없음(빈칸) 처리 -> DB에는 999999로 저장
            c_val = self.input_control_color.text().strip()
            m_val = self.input_control_mono.text().strip()
            control_color = int(c_val) if c_val.isdigit() else 999999
            control_mono = int(m_val) if m_val.isdigit() else 999999

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 🌟 새 ORM 컬럼명으로 저장 (base_mono_price, color_limit 등)
            cursor.execute("UPDATE PricingPolicy SET base_mono_price=?, base_color_price=? WHERE paper_size=9", (mono, color))
            cursor.execute("UPDATE PricingPolicy SET base_mono_price=?, base_color_price=?, multiplier=?, color_multiplier=? WHERE paper_size=8", (mono, color, mono_multi, color_multi))
            
            cursor.execute("UPDATE PrintControlPolicy SET color_limit=?, mono_limit=? WHERE id=1", (control_color, control_mono))
            
            conn.commit(); conn.close()
            
            QMessageBox.information(self, "성공", "과금 단가 및 전사 정책이 성공적으로 저장되었습니다!\n에이전트들이 통신 주기(10초)마다 변경된 정책을 자동으로 가져갑니다.")
            self.refresh_requested.emit()
        except ValueError:
            QMessageBox.warning(self, "오류", "단가, 배수 및 한도는 반드시 숫자로 입력해야 합니다.")

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 요금 로드 (새 ORM 컬럼)
        try:
            cursor.execute("SELECT base_mono_price, base_color_price FROM PricingPolicy WHERE paper_size=9")
            a4_policy = cursor.fetchone()
            if a4_policy:
                self.input_a4_mono.setText(str(a4_policy[0])); self.input_a4_color.setText(str(a4_policy[1]))
                
            cursor.execute("SELECT multiplier, color_multiplier FROM PricingPolicy WHERE paper_size=8")
            a3_policy = cursor.fetchone()
            if a3_policy:
                self.input_a3_mono_multi.setText(str(a3_policy[0])); self.input_a3_color_multi.setText(str(a3_policy[1] if a3_policy[1] is not None else a3_policy[0]))
        except sqlite3.OperationalError: pass
        
        # 🌟 통제 로드 (새 ORM 컬럼)
        try:
            cursor.execute("SELECT color_limit, mono_limit FROM PrintControlPolicy WHERE id=1")
            control_policy = cursor.fetchone()
            if control_policy:
                # 999999(제한 없음)일 경우 빈칸으로 표시
                c_lim = "" if control_policy[0] == 999999 else str(control_policy[0])
                m_lim = "" if control_policy[1] == 999999 else str(control_policy[1])
                self.input_control_color.setText(c_lim)
                self.input_control_mono.setText(m_lim)
        except sqlite3.OperationalError: pass
        
        conn.close()