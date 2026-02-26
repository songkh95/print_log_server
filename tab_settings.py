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
        
        # --- 2. 🌟 [신규] 인쇄 사전 승인(통제) 조건 설정 영역 ---
        group_control = QGroupBox("🛑 인쇄 사전 승인(통제) 기준 설정 (전사 공통 기본값)")
        group_control.setFont(QFont("Arial", 12, QFont.Bold))
        form_control = QFormLayout(group_control)
        
        self.input_color_limit = QLineEdit()
        self.input_color_limit.setPlaceholderText("예: 10 (0 입력 시 무조건 승인 대기, 빈칸은 제한 없음)")
        self.input_mono_limit = QLineEdit()
        self.input_mono_limit.setPlaceholderText("예: 50 (0 입력 시 무조건 승인 대기, 빈칸은 제한 없음)")

        form_control.addRow("🎨 컬러 인쇄 대기 기준 (몇 장 이상일 때 승인 요청):", self.input_color_limit)
        form_control.addRow("◼️ 흑백 인쇄 대기 기준 (몇 장 이상일 때 승인 요청):", self.input_mono_limit)
        
        layout.addWidget(group_control)

        # --- 저장 버튼 ---
        save_btn = QPushButton("💾 정책 일괄 저장 및 적용")
        save_btn.setFixedSize(250, 50)
        save_btn.clicked.connect(self.save_settings)
        
        layout.addSpacing(20)
        layout.addWidget(save_btn, alignment=Qt.AlignCenter)
        layout.addStretch()

    def save_settings(self):
        try:
            # 단가 데이터 파싱
            mono = int(self.input_a4_mono.text())
            color = int(self.input_a4_color.text())
            mono_multi = float(self.input_a3_mono_multi.text())
            color_multi = float(self.input_a3_color_multi.text())
            
            # 🌟 통제 데이터 파싱 (안 적혀 있으면 엄청 큰 숫자로 예외처리하여 사실상 제한 없음 처리)
            color_limit_text = self.input_color_limit.text().strip()
            mono_limit_text = self.input_mono_limit.text().strip()
            
            color_limit = int(color_limit_text) if color_limit_text else 999999
            mono_limit = int(mono_limit_text) if mono_limit_text else 999999
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 요금 업데이트
            cursor.execute("UPDATE PricingPolicy SET BaseMonoPrice=?, BaseColorPrice=? WHERE PaperSize=9", (mono, color))
            cursor.execute("UPDATE PricingPolicy SET BaseMonoPrice=?, BaseColorPrice=?, Multiplier=?, ColorMultiplier=? WHERE PaperSize=8", 
                           (mono, color, mono_multi, color_multi))
                           
            # 🌟 통제 업데이트
            cursor.execute("UPDATE PrintControlPolicy SET ColorLimit=?, MonoLimit=? WHERE ID=1", (color_limit, mono_limit))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "성공", "정책이 성공적으로 저장되었습니다!\n새로운 정책을 완벽히 적용하려면, 켜져있는 관리자 서버(server.py) 파워셸 창을 한 번 껐다 켜주세요.")
            self.refresh_requested.emit()
        except ValueError:
            QMessageBox.warning(self, "오류", "단가, 배수, 제한 장수는 반드시 숫자로만 입력해야 합니다.")

    def load_data(self):
        if not os.path.exists(DB_PATH): return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 요금 로드
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
        except sqlite3.OperationalError: pass
        
        # 🌟 통제 로드
        try:
            cursor.execute("SELECT ColorLimit, MonoLimit FROM PrintControlPolicy WHERE ID=1")
            control_policy = cursor.fetchone()
            if control_policy:
                # 999999(제한 없음)일 경우 빈칸으로 표시
                c_lim = "" if control_policy[0] == 999999 else str(control_policy[0])
                m_lim = "" if control_policy[1] == 999999 else str(control_policy[1])
                self.input_color_limit.setText(c_lim)
                self.input_mono_limit.setText(m_lim)
        except sqlite3.OperationalError: pass
        
        conn.close()