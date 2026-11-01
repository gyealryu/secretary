"""실행: python -m app  (Windows에서는 run.bat 더블클릭)"""

import os
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"  # 내 PC에서만 접속 가능 (다른 사람은 접속 불가)
PORT = int(os.environ.get("SECRETARY_PORT", "8765"))


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    print(f"AI 비서를 시작합니다: {url}")
    print("이 창을 닫으면 AI 비서가 종료됩니다.")
    if os.environ.get("SECRETARY_NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
