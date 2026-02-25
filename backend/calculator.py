# Manager_Console/backend/calculator.py
import sqlite3
from models import DB_PATH

def calculate_price(paper_size_code, color_mode_code, total_pages, copies):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 🌟 [변경] DB에 새로 추가될 ColorMultiplier(컬러 가중치)를 함께 가져옵니다.
        cursor.execute("SELECT BaseColorPrice, BaseMonoPrice, Multiplier, ColorMultiplier FROM PricingPolicy WHERE PaperSize = ?", (paper_size_code,))
        policy = cursor.fetchone()
        if not policy:
            cursor.execute("SELECT BaseColorPrice, BaseMonoPrice, Multiplier, ColorMultiplier FROM PricingPolicy WHERE PaperSize = 9")
            policy = cursor.fetchone()
            if not policy: return 0
            
        base_color, base_mono, mono_multi, color_multi = policy
        if color_multi is None: color_multi = mono_multi
        
    except sqlite3.OperationalError:
        # 만약 아직 DB가 구버전이라 에러가 나면 기존 방식(가중치 1개)으로 동작하도록 안전장치
        cursor.execute("SELECT BaseColorPrice, BaseMonoPrice, Multiplier FROM PricingPolicy WHERE PaperSize = ?", (paper_size_code,))
        policy = cursor.fetchone()
        if not policy:
            cursor.execute("SELECT BaseColorPrice, BaseMonoPrice, Multiplier FROM PricingPolicy WHERE PaperSize = 9")
            policy = cursor.fetchone()
            if not policy: return 0
        base_color, base_mono, mono_multi = policy
        color_multi = mono_multi
        
    conn.close()
    
    # 색상에 따른 단가 및 가중치 각각 적용
    if color_mode_code == 2:
        base_price = base_color
        final_multi = color_multi
    else:
        base_price = base_mono
        final_multi = mono_multi
    
    final_price = int(base_price * final_multi * total_pages * copies)
    
    return final_price