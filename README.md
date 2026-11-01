# AI 비서 (회사용)

인터넷이나 Claude 없이 **내 PC 안에서만** 동작하는 AI 비서예요.
AI 모델은 [Ollama](https://ollama.com)로 PC에서 직접 실행하므로 회사 데이터가 밖으로 나가지 않습니다.
OpenAI 계정도 필요 없어요.

## 기능

- **대화**: 개발 아이디어, 웹페이지 구성, 코드 질문을 함께 논의하는 개발 친구. 대화 기록이 저장되고 코드 블록 복사 버튼도 있어요.
- **문서**: txt, md, pdf, docx, 코드 파일을 넣으면 요약, 회의록, 이메일 초안, 보고서 초안, 코드 리뷰를 해줘요.
- **할 일**: "내일 오후 3시 디자인 회의"처럼 말로 쓰면 할 일과 일정으로 등록돼요. 대화할 때 남은 할 일도 비서가 알고 있어요.

## 설치 (Windows)

### 1. Python 설치
[python.org](https://www.python.org/downloads/)에서 Python 3.10 이상을 설치하세요.
설치 첫 화면에서 **"Add python.exe to PATH"를 꼭 체크**하세요.

### 2. Ollama 설치 + 모델 받기
1. [ollama.com](https://ollama.com/download)에서 Windows용 Ollama를 설치하세요.
2. 명령 프롬프트(cmd)를 열고 모델을 받으세요. 한 번만 받으면 이후엔 인터넷이 필요 없어요.
   ```
   ollama pull qwen2.5-coder:7b
   ```

| 모델 | 특징 | 필요 메모리(대략) |
|---|---|---|
| `qwen2.5-coder:7b` (기본값) | 코드에 강하고 한국어도 무난함 | 8GB 이상 |
| `qwen2.5:7b` | 일반 대화와 문서 작업에 무난함 | 8GB 이상 |
| `exaone3.5:7.8b` | LG에서 만든 모델이라 한국어가 자연스러움 | 8GB 이상 |
| `qwen2.5-coder:14b` | 7b보다 똑똑하지만 느림 | 16GB 이상 |
| `qwen2.5:3b` | 사양이 낮은 PC용, 빠르지만 답이 단순함 | 4GB 이상 |

GPU가 없는 사무용 PC에서는 답변이 느릴 수 있어요. 너무 느리면 더 작은 모델을 쓰세요.

### 3. AI 비서 설치 / 실행
1. 이 폴더에서 **`install.bat`** 을 더블클릭하세요. 처음 한 번만 하면 돼요.
2. **`run.bat`** 을 더블클릭하면 브라우저에 AI 비서가 열려요. (주소: http://127.0.0.1:8765)
3. 검은 창을 닫으면 종료돼요.

다른 모델을 쓰려면 오른쪽 위 **설정**에서 모델 이름을 바꾸고 **연결 확인**을 누르세요.

## 회사 PC가 인터넷이 막혀 있다면 (오프라인 설치)

인터넷이 되는 PC에서 패키지를 미리 받아 옮기면 돼요.

1. 인터넷 되는 PC(같은 Python 버전, 예: 3.12)에서 이 폴더를 열고 실행:
   ```
   pip download -r requirements.txt -d wheels --platform win_amd64 --python-version 3.12 --only-binary=:all:
   ```
2. 생성된 `wheels` 폴더째 회사 PC의 이 폴더로 복사하세요.
3. `install.bat`을 실행하면 `wheels` 폴더에서 자동으로 설치돼요.

Ollama 모델도 인터넷 되는 PC에서 `ollama pull`로 받은 뒤
`C:\Users\사용자이름\.ollama\models` 폴더를 회사 PC의 같은 위치로 복사하면 돼요.

## 긴 문서가 잘릴 때

Ollama는 기본적으로 한 번에 읽는 글 길이(문맥)가 짧아요. 긴 문서를 다루려면
Windows 환경 변수에 `OLLAMA_CONTEXT_LENGTH=16384`를 추가하고 Ollama를 재시작하세요.
(메모리를 더 씁니다.) 설정의 **문서 최대 글자 수**도 함께 늘리세요.

## 사내 LLM 서버에 연결하기

회사에 내부 AI 서버(vLLM 등 OpenAI 호환 API)가 생기면 설정에서
**모델 서버 주소**(예: `http://사내서버:8000/v1`), 모델 이름, API 키만 바꾸면 돼요.

## 데이터 위치

대화, 할 일, 설정은 이 폴더의 `data/secretary.db` 파일 하나에 저장돼요.
백업은 이 파일만 복사하면 돼요.

## 개발자용

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest
.venv\Scripts\python -m pytest
.venv\Scripts\python -m app
```

| 경로 | 내용 |
|---|---|
| `app/main.py` | 웹 서버와 API |
| `app/llm.py` | 모델 서버 연결 (OpenAI 호환 규격) |
| `app/prompts.py` | 비서의 말투와 역할 (여기를 고치면 성격이 바뀌어요) |
| `app/db.py` | SQLite 저장소 |
| `app/documents.py` | 파일에서 글자 추출 |
| `app/static/` | 화면 (HTML/CSS/JS, 외부 라이브러리 없음) |
