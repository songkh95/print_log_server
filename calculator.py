# Manager_Console/calculator.py
from models import SessionLocal, PricingPolicy

def calculate_price(paper_size: int, color_mode: int, total_pages: int, copies: int) -> int:
    """
    용지 크기(A4, A3 등)와 색상 모드(흑백/컬러)를 기반으로 DB의 요금 정책을 조회하여 최종 과금액을 계산합니다.
    """
    db = SessionLocal()
    try:
        # 1. 과금 정책 DB에서 안전하게 가져오기
        policy = db.query(PricingPolicy).filter(PricingPolicy.paper_size == paper_size).first()
        
        # 2. 정책이 없을 경우를 대비한 안전망 (Fallback)
        if not policy:
            # DB에 정책이 없을 경우의 기본 하드코딩 값 (A4 기준)
            base_price = 150 if color_mode == 2 else 50
            multiplier = 2 if paper_size == 8 else 1 # 8은 A3
        else:
            # 3. 색상 모드에 따른 단가 및 배수 적용 (1: 흑백, 2: 컬러)
            if color_mode == 2:
                base_price = policy.base_color_price
                multiplier = policy.color_multiplier
            else:
                base_price = policy.base_mono_price
                multiplier = policy.multiplier

        # 4. 최종 금액 계산: (기본단가 * 가중치배수) * 출력페이지수 * 인쇄매수
        total_price = (base_price * multiplier) * total_pages * copies
        return total_price
        
    except Exception as e:
        print(f"⚠️ [계산기 오류] 과금액 산출 중 문제 발생: {e}")
        return 0
    finally:
        # 작업이 끝나면 반드시 세션을 반납하여 메모리 누수 방지
        db.close()