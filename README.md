# dart-disclosure-bot-appengine

# DART 공시 알림 봇 📊

한국 전자공시시스템(DART)의 공시를 실시간으로 모니터링하고 텔레그램으로 알림을 보내는 봇입니다.

## 🚀 주요 기능

- ✅ 30분마다 DART 공시 자동 확인
- ✅ 모든 기업의 모든 공시 모니터링
- ✅ 공시 2줄 자동 요약
- ✅ 텔레그램 실시간 알림
- ✅ 평일 08:00-18:00 운영
- ✅ 중복 공시 필터링

## 📋 설정 가이드

### 1. 사전 준비

#### DART API 키 발급
1. [DART OpenAPI](https://opendart.fss.or.kr/) 접속
2. 회원가입 및 로그인
3. 인증키 발급 메뉴에서 API 키 발급

#### Google Cloud 프로젝트 설정
```bash
# Google Cloud CLI 설치 후
gcloud projects create dart-disclosure-bot
gcloud config set project dart-disclosure-bot

# App Engine 활성화
gcloud app create --region=asia-northeast3

# 필요한 API 활성화
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
```

#### 서비스 계정 생성
```bash
# 서비스 계정 생성
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions"

# 권한 부여
gcloud projects add-iam-policy-binding dart-disclosure-bot \
    --member="serviceAccount:github-actions@dart-disclosure-bot.iam.gserviceaccount.com" \
    --role="roles/appengine.appAdmin"

gcloud projects add-iam-policy-binding dart-disclosure-bot \
    --member="serviceAccount:github-actions@dart-disclosure-bot.iam.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.editor"

# 키 생성 (JSON)
gcloud iam service-accounts keys create key.json \
    --iam-account=github-actions@dart-disclosure-bot.iam.gserviceaccount.com
```

### 2. GitHub 설정

#### Repository Secrets 설정
GitHub 저장소 → Settings → Secrets and variables → Actions

필수 Secrets:
- `GCP_PROJECT_ID`: Google Cloud 프로젝트 ID
- `GCP_SA_KEY`: 서비스 계정 JSON 키 (위에서 생성한 key.json 내용)
- `DART_API_KEY`: DART OpenAPI 키
- `BOT_TOKEN`: 텔레그램 봇 토큰
- `CHAT_ID`: 텔레그램 채팅 ID

### 3. 배포

```bash
# 저장소 클론
git clone https://github.com/YOUR_USERNAME/dart-disclosure-bot.git
cd dart-disclosure-bot

# 파일 추가
# main.py, requirements.txt, app.yaml, cron.yaml, .github/workflows/deploy.yml

# 커밋 및 푸시
git add .
git commit -m "Initial commit: DART disclosure bot"
git push origin main
```

GitHub Actions가 자동으로 App Engine에 배포합니다.

## 🧪 테스트

### 연결 테스트
```
https://YOUR_PROJECT_ID.appspot.com/test-connection
```

### DART API 테스트
```
https://YOUR_PROJECT_ID.appspot.com/test-dart
```

### 수동 공시 확인
```
https://YOUR_PROJECT_ID.appspot.com/check-disclosures
```

## 📱 텔레그램 메시지 예시

```
📊 DART 공시 알림
🕐 2024-01-15 14:30 KST
━━━━━━━━━━━━━━━━━━

1. 삼성전자
📄 주요사항보고서(유상증자결정)
⏰ 20240115 14:25
💡 자본금 변동 공시. 유상증자 결정에 대한 중요 정보입니다.
🔗 공시 상세보기

2. SK하이닉스
📄 분기보고서
⏰ 20240115 14:20
💡 실적 공시. 회사의 재무성과에 대한 정보입니다.
🔗 공시 상세보기

━━━━━━━━━━━━━━━━━━
총 2개의 새로운 공시
```

## 🔧 유지보수

### 로그 확인
```bash
gcloud app logs tail -s default
```

### 스케줄러 확인
```bash
gcloud scheduler jobs list
```

### 수동 실행
```bash
gcloud scheduler jobs run dart-disclosure-check
```

## 📊 모니터링

Google Cloud Console에서:
1. App Engine → Dashboard: 요청 및 에러 모니터링
2. Cloud Scheduler → Jobs: 스케줄 실행 상태
3. Logging → Logs Explorer: 상세 로그 확인

## 🛠️ 커스터마이징

### 공시 필터링 추가
`main.py`의 `get_dart_disclosures()` 함수에서:
```python
# 특정 기업만 필터링
if disclosure.get('corp_name') in ['삼성전자', 'SK하이닉스']:
    recent_disclosures.append(disclosure)

# 특정 공시 유형만 필터링  
if '주요사항' in disclosure.get('report_nm', ''):
    recent_disclosures.append(disclosure)
```

### 알림 주기 변경
`cron.yaml`에서:
```yaml
schedule: every 10 minutes from 09:00 to 15:30  # 10분마다, 장시간만
```

## 📝 라이센스

MIT License
