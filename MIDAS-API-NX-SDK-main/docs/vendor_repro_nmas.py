"""MIDAS NX Open API — `POST /db/NMAS` 크래시 재현 (독립 실행 스크립트)

docs/vendor_report_ko.md 의 A-1 항목에 대한 재현 코드입니다.

의존성은 `requests` 하나이며, 이 저장소의 SDK를 사용하지 않습니다. 검증 대상이
SDK가 아니라 제품 동작이므로, 중간 계층 없이 원본 HTTP 요청만 보냅니다.

사용법:
    pip install requests
    python vendor_repro_nmas.py <MAPI-Key>              # Civil NX (기본값)
    python vendor_repro_nmas.py <MAPI-Key> --product gen  # Gen NX

    또는 MIDAS_MAPI_KEY 환경변수에 키를 넣고 인자 없이 실행

⚠️ 경고 — 이 스크립트는 MIDAS Civil NX와 Gen NX 둘 다 종료시킵니다. 두 제품
모두에서 9회 재현(Civil 6회, Gen 3회 — 그중 하나는 실무 모델에서도 재현)됐고,
한 번도 예외 없이 죽었습니다.

    - 저장하지 않은 작업이 있는 문서에 대해 실행하지 마십시오. `/doc/NEW` 를
      호출하지는 않지만, 프로그램이 비정상 종료되므로 미저장 내용은 사라집니다.
    - 종료 후 라이선스가 반환되지 않습니다. 프로그램을 다시 실행하여
      New Project 를 누르고 정상 종료해야 회수됩니다.
    - 실행 전 대상 제품에서 Open API 연결이 되어 있어야 합니다.

설계 의도 (두 가지 대안 원인을 배제하기 위한 구성입니다):

    1. `/doc/NEW` 를 호출하지 않습니다. 미저장 문서에서 `/doc/NEW` 는 저장 확인
       대화상자를 띄우고, 모달이 열려 있으면 해당 호출뿐 아니라 API 세션 전체가
       멈춥니다. 이 스크립트에는 그 경로가 없습니다.
    2. 대상 호출 직전에 쓰기 2건과 읽기 2건을 수행하고 각각의 소요시간을
       출력합니다. 모달이 열려 있었다면 이 4건도 함께 멈췄어야 합니다.

    또한 절점 번호 9001 이상만 사용하므로 열려 있는 문서의 기존 내용은 건드리지
    않습니다.
"""
import argparse
import json
import os
import sys
import time

import requests

TIMEOUT = 15.0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("key", nargs="?", default=None)
    parser.add_argument("--product", choices=["civil", "gen"], default="civil")
    args = parser.parse_args()
    host = "https://moa-engineers.midasit.com:443"
    base = f"{host}/{args.product}"

    key = args.key or os.getenv("MIDAS_MAPI_KEY", "")
    if not key:
        print("MAPI Key를 인자로 넘기거나 MIDAS_MAPI_KEY 환경변수에 설정하십시오.")
        return 2

    headers = {"Content-Type": "application/json", "MAPI-Key": key}
    start = time.time()

    def call(label, method, endpoint, body=None, *, root=False):
        """요청 1건을 보내고 소요시간과 결과를 출력한다. 타임아웃이면 False.

        root=True 는 제품 세그먼트(/gen, /civil)를 붙이지 않습니다.
        /mapikey/verify 만 호스트 루트에서 서비스되며, 제품 세그먼트를 붙이면
        404 를 반환합니다 (2026-09-16 양 제품에서 확인).
        """
        t = time.time()
        try:
            response = requests.request(
                method, (host if root else base) + endpoint,
                headers=headers, json=body, timeout=TIMEOUT
            )
        except requests.exceptions.ReadTimeout:
            print(f"[{time.time() - start:5.1f}s] TIMEOUT  {label:38} "
                  f"({time.time() - t:.2f}s)")
            return False
        body_text = json.dumps(response.json(), ensure_ascii=False)[:70]
        print(f"[{time.time() - start:5.1f}s] {response.status_code}      {label:38} "
              f"({time.time() - t:.2f}s)  {body_text}")
        return True

    print(f"대상: {base}")
    if not call("연결 확인", "GET", "/mapikey/verify", root=True):
        return 2

    print("\n--- 준비: 절점 생성 (9001 이상만 사용) ---")
    call("POST /db/NODE 9001,9002", "POST", "/db/NODE",
         {"Assign": {"9001": {"X": 50, "Y": 50, "Z": 0},
                     "9002": {"X": 50, "Y": 50, "Z": 3}}})

    print("\n--- 대조군: 대상 호출 직전에 쓰기/읽기가 정상 동작함을 확인 ---")
    call("POST /db/SKEW 9001", "POST", "/db/SKEW",
         {"Assign": {"9001": {"iMETHOD": 1, "ANGLE_X": 0, "ANGLE_Y": 0,
                              "ANGLE_Z": 30}}})
    call("POST /db/CONS 9002", "POST", "/db/CONS",
         {"Assign": {"9002": {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111111"}]}}})
    call("GET  /db/NMAS (대상 테이블)", "GET", "/db/NMAS")
    call("GET  /db/NODE", "GET", "/db/NODE")

    print("\n--- 대상 호출 ---")
    alive = call("POST /db/NMAS 9001", "POST", "/db/NMAS",
                 {"Assign": {"9001": {"mX": 1.0, "mY": 1.0, "mZ": 1.0}}})

    print("\n--- 호출 이후 상태 ---")
    call("GET /mapikey/verify (릴레이가 응답)", "GET", "/mapikey/verify", root=True)
    app_alive = call("GET /db/NODE (제품이 응답)", "GET", "/db/NODE")

    print()
    if alive and app_alive:
        print("결과: 재현되지 않았습니다. POST /db/NMAS 가 정상 응답했습니다.")
        return 0

    print("결과: 재현되었습니다.")
    print("  - POST /db/NMAS 가 응답하지 않았습니다.")
    print("  - 직전 대조군 호출 4건은 모두 정상 응답했으므로, 모달 대화상자에 의한")
    print("    세션 차단으로는 설명되지 않습니다.")
    print("  - GET /mapikey/verify 는 여전히 connected 를 반환하는 반면")
    print("    GET /db/NODE 는 타임아웃됩니다 (릴레이만 응답).")
    print()
    print(f"{'Civil NX' if args.product == 'civil' else 'Gen NX'} 화면에 라이선스 관련 대화상자가 표시되어 있을 것입니다.")
    print("라이선스 회수를 위해: 프로그램 재실행 → New Project → 정상 종료")
    return 1


if __name__ == "__main__":
    sys.exit(main())
