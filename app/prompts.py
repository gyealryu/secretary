"""모델에게 주는 지시문(프롬프트) 모음. 말투나 역할을 바꾸고 싶으면 여기를 고치세요."""

from datetime import datetime

WEEKDAYS = "월화수목금토일"


def today_text() -> str:
    d = datetime.now()
    return f"{d:%Y-%m-%d} ({WEEKDAYS[d.weekday()]}요일) {d:%H:%M}"


def chat_system(tasks: list[dict]) -> str:
    pending = [t for t in tasks if not t["done"]][:20]
    task_lines = "\n".join(
        f"- {t['title']}" + (f" (기한: {t['due']})" if t["due"] else "") for t in pending
    ) or "- (없음)"
    return f"""당신은 사용자의 개발 친구이자 비서입니다.
- 사용자와 함께 개발 아이디어, 웹페이지 구성, 코드 설계와 구현을 논의합니다.
- 한국어로, 친근하지만 핵심 위주로 답합니다.
- 코드는 반드시 ```언어 형식의 코드 블록으로 씁니다.
- 아이디어를 들으면 장단점과 더 나은 대안을 함께 제시하고, 필요하면 되물어 봅니다.
- 모르는 것은 모른다고 말하고, 지어내지 않습니다.

현재 시각: {today_text()}
사용자의 남은 할 일:
{task_lines}
"""


DOC_MODES = {
    "summary": "다음 문서의 핵심 내용을 한국어로 요약해 주세요. 먼저 세 줄 요약을 쓰고, 이어서 주요 내용을 항목별로 정리해 주세요.",
    "minutes": "다음 내용을 회의록 형식으로 정리해 주세요. 항목: 회의 주제, 주요 논의 내용, 결정 사항, 할 일(담당자/기한이 있으면 포함).",
    "email": "다음 내용을 바탕으로 정중한 업무용 이메일 초안을 작성해 주세요. 제목과 본문을 포함해 주세요.",
    "report": "다음 내용을 바탕으로 업무 보고서 초안을 작성해 주세요. 항목: 개요, 현황, 문제점, 향후 계획.",
    "code_review": "다음 코드를 리뷰해 주세요. 버그 가능성, 개선할 점, 읽기 쉽게 고칠 부분을 우선순위대로 알려 주세요.",
    "free": "다음 문서를 참고해서 요청에 답해 주세요.",
}


def doc_prompt(mode: str, text: str, instruction: str) -> list[dict]:
    task = DOC_MODES.get(mode, DOC_MODES["free"])
    if instruction.strip():
        task += f"\n추가 요청: {instruction.strip()}"
    return [
        {"role": "system", "content": "당신은 문서 작업을 돕는 유능한 비서입니다. 한국어로 답합니다."},
        {"role": "user", "content": f"{task}\n\n--- 문서 시작 ---\n{text}\n--- 문서 끝 ---"},
    ]


def task_parse_prompt(text: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "사용자의 말에서 할 일과 일정을 뽑아 JSON으로만 답합니다. 설명은 쓰지 않습니다.\n"
                '형식: {"tasks": [{"title": "할 일 내용", "due": "YYYY-MM-DD HH:MM" 또는 "YYYY-MM-DD" 또는 null}]}\n'
                f"오늘은 {today_text()}입니다. '내일', '다음 주 월요일' 같은 표현은 실제 날짜로 바꿉니다."
            ),
        },
        {"role": "user", "content": text},
    ]
