import os
import requests
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify
import logging
from typing import List, Dict, Optional
import hashlib

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 환경 변수
DART_API_KEY = os.environ.get('DART_API_KEY')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# 공시 중복 방지를 위한 캐시 (메모리 기반)
sent_disclosures = set()

def get_korean_time():
    """현재 한국 시간 반환"""
    return datetime.now(KST)

def is_business_hours():
    """영업시간 체크 (평일 08:00-18:00)"""
    now = get_korean_time()
    
    # 주말 체크
    if now.weekday() >= 5:  # 토요일(5), 일요일(6)
        logger.info(f"주말입니다: {now.strftime('%A')}")
        return False
    
    # 시간 체크
    current_hour = now.hour
    if 8 <= current_hour < 18:
        return True
    
    logger.info(f"영업시간 외: {now.strftime('%H:%M')}")
    return False

def get_dart_disclosures(minutes: int = 30) -> List[Dict]:
    """DART API로부터 최근 공시 가져오기"""
    if not DART_API_KEY:
        logger.error("DART_API_KEY가 설정되지 않았습니다")
        return []
    
    try:
        # DART OpenAPI 엔드포인트
        url = "https://opendart.fss.or.kr/api/list.json"
        
        # 현재 시간 기준 날짜
        today = get_korean_time().strftime('%Y%m%d')
        
        params = {
            'crtfc_key': DART_API_KEY,
            'bgn_de': today,  # 시작일
            'end_de': today,  # 종료일
            'page_no': '1',
            'page_count': '100'  # 최대 100개
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') != '000':
            logger.warning(f"DART API 상태 코드: {data.get('status')}, 메시지: {data.get('message')}")
            return []
        
        disclosures = data.get('list', [])
        
        # 최근 30분 이내 공시만 필터링
        recent_disclosures = []
        cutoff_time = get_korean_time() - timedelta(minutes=minutes)
        
        for disclosure in disclosures:
            # rcept_dt: 접수일시 (예: "20240118 16:32")
            rcept_dt = disclosure.get('rcept_dt', '')
            if rcept_dt:
                try:
                    # 문자열을 datetime으로 변환
                    disclosure_time = datetime.strptime(rcept_dt, '%Y%m%d %H:%M')
                    disclosure_time = disclosure_time.replace(tzinfo=KST)
                    
                    if disclosure_time >= cutoff_time:
                        recent_disclosures.append(disclosure)
                except ValueError:
                    logger.error(f"날짜 파싱 오류: {rcept_dt}")
        
        logger.info(f"전체 공시: {len(disclosures)}개, 최근 {minutes}분 공시: {len(recent_disclosures)}개")
        return recent_disclosures
        
    except requests.exceptions.RequestException as e:
        logger.error(f"DART API 요청 실패: {e}")
        return []
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        return []

def summarize_disclosure(disclosure: Dict) -> str:
    """공시 내용 2줄 요약"""
    report_nm = disclosure.get('report_nm', '')
    corp_name = disclosure.get('corp_name', '')
    
    # 공시 유형별 간단 요약
    if '증자' in report_nm or '감자' in report_nm:
        summary = f"자본금 변동 공시. {report_nm}에 대한 결정사항입니다."
    elif '배당' in report_nm:
        summary = f"배당 관련 공시. 주주 배당에 대한 중요 정보입니다."
    elif '실적' in report_nm or '매출' in report_nm:
        summary = f"실적 공시. 회사의 재무성과에 대한 정보입니다."
    elif '임원' in report_nm or '대표이사' in report_nm:
        summary = f"경영진 변동 공시. 회사 임원진 관련 변경사항입니다."
    elif '합병' in report_nm or '인수' in report_nm:
        summary = f"M&A 관련 공시. 기업 인수합병 관련 중요 정보입니다."
    elif '계약' in report_nm:
        summary = f"주요 계약 공시. 회사의 중요 계약 체결 정보입니다."
    elif '소송' in report_nm:
        summary = f"소송 관련 공시. 법적 분쟁에 대한 정보입니다."
    else:
        summary = f"{report_nm}. 회사의 주요 경영사항에 대한 공시입니다."
    
    return summary

def format_disclosure_message(disclosures: List[Dict]) -> str:
    """공시 정보를 텔레그램 메시지 형식으로 포맷팅"""
    if not disclosures:
        return None
    
    now = get_korean_time()
    message = f"📊 <b>DART 공시 알림</b>\n"
    message += f"🕐 {now.strftime('%Y-%m-%d %H:%M')} KST\n"
    message += f"━━━━━━━━━━━━━━━━━━\n\n"
    
    for idx, disclosure in enumerate(disclosures, 1):
        corp_name = disclosure.get('corp_name', '미상')
        report_nm = disclosure.get('report_nm', '제목 없음')
        rcept_no = disclosure.get('rcept_no', '')
        rcept_dt = disclosure.get('rcept_dt', '')
        
        # 공시 URL
        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
        
        # 요약 생성
        summary = summarize_disclosure(disclosure)
        
        message += f"<b>{idx}. {corp_name}</b>\n"
        message += f"📄 {report_nm}\n"
        message += f"⏰ {rcept_dt}\n"
        message += f"💡 {summary}\n"
        message += f"🔗 <a href='{dart_url}'>공시 상세보기</a>\n\n"
    
    message += f"━━━━━━━━━━━━━━━━━━\n"
    message += f"총 {len(disclosures)}개의 새로운 공시"
    
    return message

def send_telegram_message(message: str) -> Dict:
    """텔레그램 메시지 전송"""
    if not BOT_TOKEN or not CHAT_ID:
        logger.error(f"환경변수 누락 - BOT_TOKEN: {bool(BOT_TOKEN)}, CHAT_ID: {bool(CHAT_ID)}")
        return {"status": "error", "message": "환경변수 누락"}
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            logger.info("✅ 텔레그램 메시지 전송 성공")
            return {"status": "success", "message": "전송 성공"}
        else:
            error_msg = response_data.get('description', '알 수 없는 오류')
            logger.error(f"❌ 텔레그램 API 오류: {error_msg}")
            return {"status": "error", "message": error_msg}
            
    except Exception as e:
        logger.error(f"텔레그램 전송 실패: {e}")
        return {"status": "error", "message": str(e)}

def check_and_send_disclosures():
    """공시 확인 및 전송 (중복 제거)"""
    if not is_business_hours():
        return {"status": "skip", "message": "영업시간 외"}
    
    # 최근 30분 공시 가져오기
    disclosures = get_dart_disclosures(minutes=30)
    
    if not disclosures:
        logger.info("새로운 공시가 없습니다")
        return {"status": "success", "message": "새로운 공시 없음"}
    
    # 중복 제거
    new_disclosures = []
    for disclosure in disclosures:
        # 고유 ID 생성 (접수번호 사용)
        rcept_no = disclosure.get('rcept_no', '')
        if rcept_no and rcept_no not in sent_disclosures:
            new_disclosures.append(disclosure)
            sent_disclosures.add(rcept_no)
    
    if not new_disclosures:
        logger.info("모든 공시가 이미 전송되었습니다")
        return {"status": "success", "message": "중복 공시"}
    
    # 메시지 포맷팅 및 전송
    message = format_disclosure_message(new_disclosures)
    if message:
        result = send_telegram_message(message)
        if result['status'] == 'success':
            logger.info(f"✅ {len(new_disclosures)}개 공시 전송 완료")
        return result
    
    return {"status": "success", "message": "처리 완료"}

# Flask 라우트
@app.route('/')
def home():
    """홈 페이지"""
    now = get_korean_time()
    return jsonify({
        "service": "DART 공시 알림 봇",
        "status": "running",
        "time": now.strftime('%Y-%m-%d %H:%M:%S KST'),
        "business_hours": is_business_hours()
    })

@app.route('/health')
def health():
    """헬스 체크"""
    return jsonify({"status": "healthy"})

@app.route('/test-connection')
def test_connection():
    """연결 테스트"""
    now = get_korean_time()
    
    # 환경변수 체크
    config_status = {
        "DART_API_KEY": "✅ 설정됨" if DART_API_KEY else "❌ 미설정",
        "BOT_TOKEN": "✅ 설정됨" if BOT_TOKEN else "❌ 미설정",
        "CHAT_ID": "✅ 설정됨" if CHAT_ID else "❌ 미설정"
    }
    
    # 테스트 메시지 전송
    test_message = f"🔔 <b>DART 공시 알림 봇 연결 테스트</b>\n\n"
    test_message += f"✅ 봇이 정상적으로 연결되었습니다!\n"
    test_message += f"🕐 한국시간: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
    test_message += f"📊 영업시간: {'예' if is_business_hours() else '아니오'}\n\n"
    test_message += f"<b>환경변수 상태:</b>\n"
    for key, status in config_status.items():
        test_message += f"• {key}: {status}\n"
    
    result = send_telegram_message(test_message)
    
    return jsonify({
        "test": "connection",
        "config": config_status,
        "telegram": result,
        "time": now.strftime('%Y-%m-%d %H:%M:%S KST')
    })

@app.route('/check-disclosures')
def check_disclosures():
    """수동으로 공시 확인 (테스트용)"""
    result = check_and_send_disclosures()
    return jsonify(result)

@app.route('/cron/check-disclosures')
def cron_check_disclosures():
    """Cloud Scheduler에서 호출하는 엔드포인트"""
    result = check_and_send_disclosures()
    return jsonify(result)

@app.route('/test-dart')
def test_dart():
    """DART API 테스트"""
    if not DART_API_KEY:
        return jsonify({"status": "error", "message": "DART_API_KEY not set"})
    
    disclosures = get_dart_disclosures(minutes=60)  # 최근 1시간
    
    return jsonify({
        "status": "success",
        "count": len(disclosures),
        "disclosures": disclosures[:5] if disclosures else []  # 최대 5개만 표시
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
