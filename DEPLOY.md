# 배포 가이드 (수강생용)

이 대시보드를 본인 GitHub·Streamlit Cloud 계정으로 그대로 배포하는 방법입니다.

## 왜 이런 구조인가

이 대시보드의 "상담원 관점: 직원만족도와 고객 경험" 섹션은 BigQuery `cx_data.agents`를 직접 조회합니다. 로컬에서는 `gcloud auth application-default login`으로 만든 ADC(Application Default Credentials)가 있어서 바로 되지만, **Streamlit Community Cloud에는 이 로그인 정보가 없습니다.** 인증 정보가 없으면 BigQuery 클라이언트가 인증 방법을 계속 찾아 헤매다가 에러도 없이 무한정 "Running" 상태로 멈춥니다.

그래서 배포 환경에서는 **서비스 계정 키를 Streamlit Cloud Secrets에 등록**해서 `app.py`가 그 키로 직접 인증하도록 합니다 (`load_agents()`가 `st.secrets["gcp_service_account"]`가 있으면 그걸로, 없으면 로컬 ADC로 인증). 이 시크릿 등록 없이 배포하면 "상담원 관점" 섹션에서 다시 무한 로딩이 발생합니다 — 아래 6번 단계가 **선택이 아니라 필수**입니다.

## 1. 사전 준비

- GitHub 계정
- Streamlit Community Cloud 계정 (share.streamlit.io, GitHub 계정으로 로그인)
- BigQuery `project-e6454811-8996-4412-983` 프로젝트에 서비스 계정을 만들 수 있는 권한이 있는 Google 계정 (IAM 정책상 막혀 있을 수 있음 — 6번 참고)

## 2. 로컬에서 실행해보기

```
pip install -r requirements.txt
streamlit run app.py
```

`gcloud auth application-default login`으로 로그인되어 있어야 "상담원 관점" 섹션이 정상적으로 뜹니다.

## 3. GitHub에 올리기

```
git init
git add .
git commit -m "Initial commit"
```

GitHub CLI가 있다면:
```
gh repo create <본인계정>/customer-churn-dashboard --public --source=. --remote=origin --push
```
없다면 GitHub 웹에서 새 저장소를 만들고 안내되는 명령어로 push하면 됩니다.

## 4. Streamlit Community Cloud 배포

1. https://share.streamlit.io 접속 → GitHub 계정으로 로그인
2. **"Create app"** → **"Deploy a public app from GitHub"**
3. Repository: `<본인계정>/customer-churn-dashboard`, Branch: `main`, Main file path: `app.py`
4. **Deploy 누르기 전에 "Advanced settings" 클릭 → Python version을 3.12로 선택** (중요, 아래 트러블슈팅 참고)
5. **Deploy**

## 5. BigQuery 서비스 계정 만들기

```
gcloud iam service-accounts create streamlit-bq-reader --display-name="Streamlit BigQuery Reader" --project=project-e6454811-8996-4412-983

gcloud projects add-iam-policy-binding project-e6454811-8996-4412-983 \
  --member="serviceAccount:streamlit-bq-reader@project-e6454811-8996-4412-983.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding project-e6454811-8996-4412-983 \
  --member="serviceAccount:streamlit-bq-reader@project-e6454811-8996-4412-983.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud iam service-accounts keys create sa_key.json \
  --iam-account=streamlit-bq-reader@project-e6454811-8996-4412-983.iam.gserviceaccount.com
```

**키 생성이 `FAILED_PRECONDITION: Key creation is not allowed on this service account` 에러로 막히면**: 조직 정책 `iam.disableServiceAccountKeyCreation`이 켜져 있는 것입니다. GCP 콘솔 → IAM 및 관리자 → 조직 정책 → 이 제약조건 페이지로 이동해서 "정책 관리" → "상위 정책 재정의" → 규칙 추가 → 적용을 "사용 안함"으로 설정 → 저장 후 키 생성을 다시 시도하세요. (프로젝트 Owner라도 이 정책이 조직 레벨에서 강제되어 있으면 이 화면 자체가 막혀 있을 수 있고, 그 경우 조직 관리자에게 요청해야 합니다.)

`sa_key.json`은 절대 git에 커밋하지 마세요 (저장소 밖에 두거나 즉시 삭제).

## 6. Streamlit Cloud에 Secrets 등록 (필수)

`sa_key.json`의 값을 아래 형식으로 옮겨서, Streamlit Cloud → Manage app → Settings → Secrets에 붙여넣기:

```toml
[gcp_service_account]
type = "service_account"
project_id = "project-e6454811-8996-4412-983"
private_key_id = "..."
private_key = "..."
client_email = "streamlit-bq-reader@project-e6454811-8996-4412-983.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

Save → 자동 재시작 → "상담원 관점" 섹션이 정상적으로 뜨는지 확인.

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 배포 로그가 `Using Python 3.14.x environment`에서 멈추거나 매우 느림 | Streamlit Cloud가 강제하는 최신 Python과 `requirements.txt`의 구버전 패키지 간 wheel 미지원 | 앱 **삭제 후 재배포**하면서 Advanced settings에서 Python 3.12 선택 (`runtime.txt`는 현재 Streamlit 버그로 무시되니 반드시 이 화면에서 지정) |
| `ModuleNotFoundError: statsmodels` | `trendline="ols"`가 내부적으로 statsmodels를 쓰는데 requirements.txt에 빠짐 | `requirements.txt`에 `statsmodels` 추가 확인 |
| "상담원 관점" 섹션이 계속 "Running"에서 안 넘어감 | Secrets 미등록 — 배포 환경에 BigQuery 인증 정보가 전혀 없어 인증 시도가 멈춰있는 상태 | 5~6번 단계대로 서비스 계정 키를 만들어 Secrets에 등록 |
| 서비스 계정 키 생성이 조직 정책으로 막힘 | `iam.disableServiceAccountKeyCreation` 조직 정책 | 5번의 정책 재정의 방법 참고. 본인 계정이 프로젝트 Owner라도 조직 레벨 강제 정책이면 조직 관리자 문의 필요 |
| BigQuery Secrets 등록했는데도 안 됨 | 서비스 계정에 `BigQuery Job User` 역할 누락 | IAM에서 역할 추가 후 Reboot |
