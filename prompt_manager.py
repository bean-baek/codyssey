"""나만의 프롬프트 관리 — 콘솔 프로그램

이전 미션에서 작성한 프롬프트를 카테고리별로 보관하고,
검색 / 상세 보기 / 즐겨찾기로 관리한다.
"""

CATEGORIES = ["텍스트 생성", "이미지 생성", "영상 생성", "페르소나", "자동화", "기타"]
DIVIDER = "─" * 40

# 이전 미션(GenAI 기초 1~3)에서 실제로 작성했던 프롬프트를 기본 데이터로 등록한다.
prompts = [
    {
        "title": "메일라이트(MailWright) 업무 메일 어시스턴트",
        "content": (
            "당신은 \"메일라이트(MailWright)\"입니다.\n"
            "\n"
            "[역할] B2B SaaS 고객 커뮤니케이션을 15년간 담당해 온 CS 리드입니다.\n"
            "사과문, 정책 안내, 협의 요청 메일의 초안을 작성합니다.\n"
            "\n"
            "[목표] 주니어 담당자가 그대로 복사해 보내도 사고가 나지 않는 초안을 만든다.\n"
            "사고란 (a) 확인되지 않은 수치·정책을 단정해 적는 것,\n"
            "(b) 수신자 격에 맞지 않는 톤, (c) 요청받은 필수 항목 누락을 말한다.\n"
            "\n"
            "[출력 형식] 아래 5개 블록을 이 순서, 이 제목 그대로 출력한다.\n"
            "1. 제목 3안 (정보 전달형 / 관계 배려형 / 긴급 촉구형)\n"
            "2. 본문 — 인사 → 핵심 용건 1문장 → 배경·근거 → 요청 사항 → 마무리\n"
            "   한 문장 40자 내외, 전체 600자 이내(임원 수신이면 400자 이내)\n"
            "3. 다음 액션 — 발신 전 사람이 할 일을 체크박스로 최대 4개\n"
            "4. 확인 필요 — 항목 / 어디서 확인 / 확인 전 발송 시 위험\n"
            "5. 이번 턴 반영 근거 — 핵심 근거 3개만, 각 30자 이내\n"
            "\n"
            "[안전장치] 메일 성패를 좌우하는 정보가 없으면 초안 전에 확인 질문을 최대 3개 한다.\n"
            "사용자가 \"미정\"이라 답하면 추측하지 말고 본문에 [○○ 확인 후 기입] 자리표시자를 넣는다.\n"
            "\n"
            "[사실 처리] 금액·비율·날짜·SLA 수치·법령은 사용자가 명시한 것만 본문에 쓴다.\n"
            "없는 수치는 [출처 확인 필요: 항목명]으로 표기하고 임의로 채우지 않는다.\n"
            "\n"
            "[우선순위] 사실 정확성 > 형식 준수 > 친절함 > 분량"
        ),
        "category": "페르소나",
        "favorite": True,
        "views": 0,
    },
    {
        "title": "서비스 장애 사과 메일 초안 요청",
        "content": (
            "[수신자] 그린모빌리티 물류플랫폼팀 담당자\n"
            "[관계·직급] 2년차 계약 고객사, 실무 담당자\n"
            "[메일 목적] 어제 발생한 서비스 장애에 대한 사과 및 후속 조치 안내\n"
            "[확인된 사실]\n"
            "- 장애 일시: 2026-07-26 14:10 ~ 16:35 (KST)\n"
            "- 원인: 데이터베이스 이중화 전환 중 설정 오류\n"
            "- 영향: 대시보드 조회 불가. 데이터 유실은 없음(백업 검증 완료)\n"
            "- 조치: 전환 절차에 사전 검증 단계 추가 완료\n"
            "[톤] 정중하되 변명하지 않는 담백한 사과\n"
            "[필수 포함] 재발 방지 대책, 담당자 연락 창구\n"
            "[금지어] 최선을 다하겠습니다, 불편을 드려 죄송합니다(3회 초과 반복)"
        ),
        "category": "텍스트 생성",
        "favorite": False,
        "views": 0,
    },
    {
        "title": "여백 쿠션 제품 리빌 컷 (veo 3.1)",
        "content": (
            "Cinematic macro video shot of a pure white, minimalist cushion foundation "
            "compact resting on a clean surface. The camera slowly pans around the product "
            "while soft, natural studio light sweeps across the cover, revealing a "
            "beautifully detailed, trendy debossed Korean geometric lattice pattern. "
            "The shadows move realistically, emphasizing the precise 3D texture of the "
            "debossed design. Photorealistic, ultra-high definition, clean white aesthetic.\n"
            "\n"
            "[수정 이유] '패턴이 있는 쿠션'이라고만 쓰면 평면 인쇄물처럼 왜곡된다.\n"
            "debossed / camera slowly pans / light sweeps across 를 넣어\n"
            "입체감·질감·조명 변화를 모델이 계산하도록 유도했다."
        ),
        "category": "영상 생성",
        "favorite": True,
        "views": 0,
    },
    {
        "title": "여백 글래스 스킨 모델 비주얼",
        "content": (
            "High-end beauty commercial still. Elegant Korean female model with flawless, "
            "highly dewy glass skin. Wearing a modern white hanbok-inspired outfit with "
            "thin collar detail. Soft natural sunlight creates stunning highlights on her "
            "glowing skin. Pure white background, generous negative space on the right, "
            "minimalist composition, photorealistic, 8k."
        ),
        "category": "이미지 생성",
        "favorite": False,
        "views": 0,
    },
    {
        "title": "뉴스레터 구독 웹훅 분기 워크플로우 설계",
        "content": (
            "다음 자동화 시나리오를 Make와 n8n 각각의 노드 구성으로 설계해 주세요.\n"
            "\n"
            "[워크플로우] 웹사이트 뉴스레터 구독 폼 제출(Webhook)\n"
            "→ 이메일 값 존재 여부 분기\n"
            "→ (존재) 매월 1일 뉴스레터 발송\n"
            "→ (누락) 관리자에게 경고 메일 발송\n"
            "\n"
            "[요구사항]\n"
            "- 각 도구의 트리거/분기/액션 노드를 실제 노드명으로 적을 것\n"
            "- UI, 설정 난이도, 연동 범위, 무료 플랜, 실행 로그를 표로 비교할 것\n"
            "- 어떤 팀에 어떤 도구가 적합한지 한 문단으로 결론 낼 것"
        ),
        "category": "자동화",
        "favorite": False,
        "views": 0,
    },
]


def input_required(label):
    """빈 값이 들어오면 다시 물어보고, 값이 채워질 때까지 반복한다."""
    while True:
        value = input(label).strip()
        if value:
            return value
        print("[안내] 값을 입력해 주세요.")


def choose_category():
    """미리 정의된 카테고리를 고르거나 직접 입력받는다."""
    print("\n카테고리 선택:")
    for number, name in enumerate(CATEGORIES, start=1):
        print(f"{number}. {name}")
    print("0. 직접 입력")

    while True:
        choice = input("선택: ").strip()

        if choice == "0":
            return input_required("카테고리 이름: ")

        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            return CATEGORIES[int(choice) - 1]

        print("[안내] 목록에 있는 번호를 입력해 주세요.")


def add_prompt():
    """새 프롬프트를 입력받아 목록에 추가한다."""
    print("\n=== 프롬프트 추가 ===")
    title = input_required("제목: ")
    content = input_required("내용: ")
    category = choose_category()

    prompts.append(
        {
            "title": title,
            "content": content,
            "category": category,
            "favorite": False,
            "views": 0,
        }
    )
    print(f"\n'{title}' 프롬프트가 추가되었습니다! (총 {len(prompts)}개)")


def numbered_prompts():
    """전체 목록 기준 번호를 붙여 (번호, 프롬프트) 쌍의 리스트로 만든다."""
    return list(enumerate(prompts, start=1))


def format_summary(number, prompt):
    """목록 한 줄을 '번호. [카테고리] 제목 ⭐' 형태로 만든다."""
    star = " ⭐" if prompt["favorite"] else ""
    return f"{number}. [{prompt['category']}] {prompt['title']}{star}"


def print_prompts(items, empty_message):
    """(번호, 프롬프트) 쌍 목록을 출력한다. 번호는 항상 전체 목록 기준이다."""
    if not items:
        print(empty_message)
        return

    for number, prompt in items:
        print(format_summary(number, prompt))
    print(f"\n총 {len(items)}개의 프롬프트")


def show_list():
    """저장된 모든 프롬프트를 번호와 함께 출력한다."""
    print("\n=== 프롬프트 목록 ===")
    print_prompts(numbered_prompts(), "[안내] 등록된 프롬프트가 없습니다.")


def show_by_category():
    """카테고리를 선택받아 해당 카테고리의 프롬프트만 출력한다."""
    print("\n=== 카테고리별 조회 ===")
    category = choose_category()

    items = [pair for pair in numbered_prompts() if pair[1]["category"] == category]

    print(f"\n[{category}] 카테고리 프롬프트:")
    print_prompts(items, f"[안내] '{category}' 카테고리에는 아직 프롬프트가 없습니다.")


def search_prompt():
    """키워드가 제목 또는 내용에 들어 있는 프롬프트를 찾아 출력한다."""
    print("\n=== 프롬프트 검색 ===")
    keyword = input_required("검색어: ").lower()

    items = [
        (number, prompt)
        for number, prompt in numbered_prompts()
        if keyword in prompt["title"].lower() or keyword in prompt["content"].lower()
    ]

    print("\n검색 결과:")
    if not items:
        print(f"[안내] '{keyword}'와 일치하는 프롬프트가 없습니다.")
        return

    for number, prompt in items:
        print(format_summary(number, prompt))
    print(f"\n{len(items)}개의 프롬프트를 찾았습니다.")


def select_prompt(label):
    """번호를 입력받아 (번호, 프롬프트)를 돌려준다. 잘못된 번호면 None."""
    if not prompts:
        print("[안내] 등록된 프롬프트가 없습니다.")
        return None

    choice = input(label).strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(prompts):
        print(f"[안내] 1 ~ {len(prompts)} 사이의 번호를 입력해 주세요.")
        return None

    number = int(choice)
    return number, prompts[number - 1]


def show_detail():
    """번호로 프롬프트 하나를 골라 전체 내용을 출력한다."""
    print("\n=== 프롬프트 상세 보기 ===")
    selected = select_prompt("번호 입력: ")
    if selected is None:
        return

    number, prompt = selected
    prompt["views"] += 1

    print()
    print(DIVIDER)
    print(f"번호: {number}")
    print(f"제목: {prompt['title']}")
    print(f"카테고리: {prompt['category']}")
    print(f"즐겨찾기: {'⭐' if prompt['favorite'] else '없음'}")
    print(f"조회수: {prompt['views']}회")
    print(DIVIDER)
    print("내용:")
    print(prompt["content"])
    print(DIVIDER)


def toggle_favorite():
    """번호로 고른 프롬프트의 즐겨찾기를 켜거나 끈다."""
    print("\n=== 즐겨찾기 관리 ===")
    selected = select_prompt("프롬프트 번호 입력: ")
    if selected is None:
        return

    _, prompt = selected
    prompt["favorite"] = not prompt["favorite"]

    if prompt["favorite"]:
        print(f"\n'{prompt['title']}' 프롬프트를 즐겨찾기에 추가했습니다! ⭐")
    else:
        print(f"\n'{prompt['title']}' 프롬프트를 즐겨찾기에서 해제했습니다.")


def show_favorites():
    """즐겨찾기로 표시한 프롬프트만 모아서 출력한다."""
    print("\n=== 즐겨찾기 목록 ===")
    items = [pair for pair in numbered_prompts() if pair[1]["favorite"]]
    print_prompts(items, "[안내] 즐겨찾기한 프롬프트가 없습니다.")


def preview(text, length=30):
    """여러 줄 내용을 한 줄로 줄여 미리보기 문자열을 만든다."""
    one_line = text.replace("\n", " ")
    if len(one_line) <= length:
        return one_line
    return one_line[:length] + "..."


def edit_prompt():
    """번호로 고른 프롬프트의 제목/내용/카테고리를 고친다."""
    print("\n=== 프롬프트 수정 ===")
    selected = select_prompt("수정할 프롬프트 번호: ")
    if selected is None:
        return

    _, prompt = selected
    print("\n(엔터만 누르면 기존 값을 그대로 둡니다)")

    title = input(f"제목 [{prompt['title']}]: ").strip()
    if title:
        prompt["title"] = title

    content = input(f"내용 [{preview(prompt['content'])}]: ").strip()
    if content:
        prompt["content"] = content

    answer = input(f"카테고리를 바꿀까요? 현재 [{prompt['category']}] (y/N): ").strip()
    if answer.lower() == "y":
        prompt["category"] = choose_category()

    print(f"\n'{prompt['title']}' 프롬프트를 수정했습니다.")


def delete_prompt():
    """번호로 고른 프롬프트를 확인 후 목록에서 지운다."""
    print("\n=== 프롬프트 삭제 ===")
    selected = select_prompt("삭제할 프롬프트 번호: ")
    if selected is None:
        return

    number, prompt = selected
    answer = input(f"'{prompt['title']}' 프롬프트를 정말 삭제할까요? (y/N): ").strip()
    if answer.lower() != "y":
        print("\n삭제를 취소했습니다.")
        return

    prompts.pop(number - 1)
    print(f"\n'{prompt['title']}' 프롬프트를 삭제했습니다. (남은 {len(prompts)}개)")


def show_top_viewed():
    """상세 보기로 많이 열어 본 순서대로 프롬프트를 정렬해 보여준다."""
    print("\n=== 조회수 TOP ===")
    if not prompts:
        print("[안내] 등록된 프롬프트가 없습니다.")
        return

    viewed = [pair for pair in numbered_prompts() if pair[1]["views"] > 0]
    if not viewed:
        print("[안내] 아직 상세 보기로 열어 본 프롬프트가 없습니다.")
        return

    ranked = sorted(viewed, key=lambda pair: pair[1]["views"], reverse=True)
    for rank, (number, prompt) in enumerate(ranked[:5], start=1):
        print(f"{rank}위 (조회 {prompt['views']}회) {format_summary(number, prompt)}")


def show_menu():
    """메인 메뉴를 출력한다."""
    print()
    print("=== 나만의 프롬프트 관리 ===")
    print("1. 프롬프트 추가")
    print("2. 프롬프트 목록")
    print("3. 카테고리별 조회")
    print("4. 프롬프트 검색")
    print("5. 프롬프트 상세 보기")
    print("6. 즐겨찾기 관리")
    print("7. 즐겨찾기 목록")
    print("8. 프롬프트 수정")
    print("9. 프롬프트 삭제")
    print("10. 조회수 TOP")
    print("0. 종료")


def main():
    """메뉴를 반복 출력하며 사용자의 선택을 처리한다."""
    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "1":
            add_prompt()
        elif choice == "2":
            show_list()
        elif choice == "3":
            show_by_category()
        elif choice == "4":
            search_prompt()
        elif choice == "5":
            show_detail()
        elif choice == "6":
            toggle_favorite()
        elif choice == "7":
            show_favorites()
        elif choice == "8":
            edit_prompt()
        elif choice == "9":
            delete_prompt()
        elif choice == "10":
            show_top_viewed()
        elif choice == "0":
            print("\n프로그램을 종료합니다.")
            break
        else:
            print("\n[안내] 없는 번호입니다. 메뉴의 번호 중에서 선택해 주세요.")


if __name__ == "__main__":
    main()
