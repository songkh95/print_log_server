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