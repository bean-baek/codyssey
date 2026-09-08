# prompt_manager.py에 쓴 파이썬 문법 정리

이 파일에 실제로 등장하는 문법만 모았습니다.
줄 번호를 눌러 코드에서 바로 확인할 수 있습니다.

---

## 0. 먼저 — 문법이 아닌 것

가장 헷갈리기 쉬운 부분입니다.

```python
choice = input("선택: ").strip()          # choice는 내가 지은 변수 이름
items = [pair for pair in numbered_prompts() ...]   # pair도 내가 지은 이름
```

`choice`, `pair`, `prompt`, `items`, `star` 는 **파이썬 키워드가 아니라 변수 이름**입니다.
`banana`로 바꿔도 프로그램은 똑같이 돌아갑니다.

```python
banana = input("선택: ").strip()   # 완전히 동일하게 동작
```

진짜 파이썬 문법(키워드)은 이런 것들입니다:
`def` `return` `if` `elif` `else` `for` `in` `while` `break` `continue`
`not` `and` `or` `is` `None` `True` `False` `import` `with` `as` `global` `lambda`

이름을 지을 때 쓴 규칙:

| 이름 | 왜 그렇게 지었나 |
| --- | --- |
| `CATEGORIES`, `DIVIDER` | 전부 대문자 = "프로그램 도중 안 바뀌는 값"이라는 관례 |
| `prompt` / `prompts` | 단수는 딕셔너리 하나, 복수는 리스트 전체 |
| `pair` | `(번호, 프롬프트)` 두 개가 짝지어진 튜플이라서 "짝" |
| `_` | 값을 받긴 받는데 안 쓸 때 (아래 6-3 참고) |

---

## 1. 자료형

### 1-1. 리스트 `[]` — 순서가 있는 여러 개

[prompt_manager.py:16](prompt_manager.py#L16)

```python
prompts = [ {...}, {...}, {...} ]
```

순서가 있으므로 `prompts[0]`이 첫 번째, `prompts[1]`이 두 번째입니다.
번호는 **0부터** 시작하기 때문에, 화면의 "3번"을 꺼낼 때 `prompts[number - 1]`처럼 1을 뺍니다.
[prompt_manager.py:240](prompt_manager.py#L240)

### 1-2. 딕셔너리 `{}` — 이름표를 붙여 저장

[prompt_manager.py:12-43](prompt_manager.py#L12-L43) (내용을 줄여서 옮김)

```python
{
    "title": "메일라이트(MailWright) 업무 메일 어시스턴트",
    "content": "당신은 ...",
    "category": "페르소나",
    "favorite": True,
    "views": 0,
}
```

`prompt["title"]` 처럼 **키(key)** 로 값을 꺼냅니다.
리스트는 번호로, 딕셔너리는 이름으로 꺼낸다고 기억하면 됩니다.

값을 바꾸거나 새로 넣는 것도 같은 문법입니다.

```python
prompt["title"] = title          # 수정 (prompt_manager.py:309)
prompt["views"] += 1             # 원래 값 + 1 (prompt_manager.py:251)
```

### 1-3. 튜플 `()` — 바꿀 수 없는 묶음

[prompt_manager.py:240](prompt_manager.py#L240)

```python
return number, prompts[number - 1]     # (3, {...}) 튜플이 반환된다
```

괄호 없이 콤마만 찍어도 튜플이 됩니다.
리스트와 달리 한 번 만들면 내용을 바꿀 수 없어서, "두 값을 한 덩어리로 잠깐 넘길 때" 씁니다.

### 1-4. 불리언과 None

```python
"favorite": False        # True / False — 참, 거짓
return None              # "값이 없음"을 뜻하는 특별한 값
```

`None`인지 확인할 때는 `==`이 아니라 `is`를 씁니다. [prompt_manager.py:247](prompt_manager.py#L247)

```python
if selected is None:
    return
```

---

## 2. 문자열 다루기

### 2-1. f-string — 문자열 안에 값 끼워 넣기

[prompt_manager.py:165](prompt_manager.py#L165)

```python
print(f"\n'{title}' 프롬프트가 추가되었습니다! (총 {len(prompts)}개)")
```

앞에 `f`를 붙이면 `{ }` 안의 내용이 **값으로 바뀌어** 들어갑니다.
`{ }` 안에는 변수뿐 아니라 계산식, 함수 호출도 넣을 수 있습니다.

**주의:** f-string을 큰따옴표로 열었으면 안에서는 작은따옴표를 써야 합니다.
[prompt_manager.py:176](prompt_manager.py#L176)

```python
f"{number}. [{prompt['category']}] {prompt['title']}{star}"
#              작은따옴표 ↑          ↑ 큰따옴표를 또 쓰면 문자열이 거기서 끊긴다
```

### 2-2. 이스케이프 문자

```python
"\n"     # 줄바꿈
```

`print("\n=== 프롬프트 추가 ===")` 는 빈 줄 하나를 찍고 제목을 출력합니다.

### 2-3. 문자열 반복 `*`

[prompt_manager.py:11](prompt_manager.py#L11)

```python
DIVIDER = "─" * 40      # ─ 를 40번 반복한 구분선
```

### 2-4. 붙어 있는 문자열은 자동으로 이어진다

[prompt_manager.py:14-18](prompt_manager.py#L14-L18)

```python
"content": (
    "당신은 \"메일라이트(MailWright)\"입니다.\n"
    "\n"
    "[역할] B2B SaaS 고객 커뮤니케이션을...\n"
),
```

괄호 안에서 문자열을 줄바꿈해 나열하면 **하나로 이어붙여집니다**. 콤마가 없는 게 핵심입니다.
콤마를 찍으면 튜플이 되어 버립니다.

### 2-5. 자주 쓴 문자열 메서드

| 메서드 | 하는 일 | 쓴 곳 |
| --- | --- | --- |
| `.strip()` | 앞뒤 공백/엔터 제거 | [124](prompt_manager.py#L124) |
| `.lower()` | 전부 소문자로 (대소문자 구분 없는 검색) | [210](prompt_manager.py#L210) |
| `.replace("\n", " ")` | 줄바꿈을 공백으로 바꿔 한 줄로 | [291](prompt_manager.py#L291) |
| `.isdigit()` | 숫자로만 이루어졌는지 검사 | [143](prompt_manager.py#L143) |

`.isdigit()`을 먼저 확인하는 이유: 사용자가 `abc`를 넣었을 때 바로 `int("abc")`를 하면
프로그램이 에러로 죽습니다. 검사 → 변환 순서가 중요합니다.

### 2-6. 슬라이싱 `[:n]`

[prompt_manager.py:294](prompt_manager.py#L294)

```python
return one_line[:length] + "..."     # 앞에서 length 글자만 잘라내기
```

리스트에도 똑같이 씁니다. [prompt_manager.py:352](prompt_manager.py#L352)

```python
ranked[:5]      # 앞에서 5개만
```

---

## 3. 조건문

### 3-1. if / elif / else

[prompt_manager.py:435-465](prompt_manager.py#L435-L465)

```python
if choice == "1":
    add_prompt()
elif choice == "2":
    show_list()
else:
    print("[안내] 없는 번호입니다.")
```

위에서부터 검사해 **처음 맞는 하나만** 실행하고 나머지는 건너뜁니다.

### 3-2. 값 자체를 조건으로 쓰기 (truthy / falsy)

[prompt_manager.py:125](prompt_manager.py#L125), [181](prompt_manager.py#L181)

```python
if value:        # 빈 문자열 ""이 아니면 참
if not items:    # 빈 리스트 []이면 참
```

파이썬은 아래를 **거짓**으로 봅니다:

```
False    None    0    ""(빈 문자열)    [](빈 리스트)    {}(빈 딕셔너리)
```

그래서 `if len(items) == 0:` 대신 `if not items:` 라고 짧게 씁니다.

### 3-3. 연쇄 비교

[prompt_manager.py:143](prompt_manager.py#L143)

```python
if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
```

`1 <= x <= 6` 은 수학처럼 그대로 씁니다. `x >= 1 and x <= 6` 과 같은 뜻입니다.

`not`을 앞에 붙이면 통째로 뒤집힙니다. [prompt_manager.py:235](prompt_manager.py#L235)

```python
if not choice.isdigit() or not 1 <= int(choice) <= len(prompts):
    # 숫자가 아니거나, 범위를 벗어나면
```

### 3-4. 조건 표현식 (한 줄 if)

[prompt_manager.py:175](prompt_manager.py#L175), [258](prompt_manager.py#L258)

```python
star = " ⭐" if prompt["favorite"] else ""
```

`(참일 때 값) if (조건) else (거짓일 때 값)` 순서입니다. 아래와 같은 뜻입니다.

```python
if prompt["favorite"]:
    star = " ⭐"
else:
    star = ""
```

### 3-5. `in` — 포함되어 있는지

[prompt_manager.py:215](prompt_manager.py#L215), [389](prompt_manager.py#L389)

```python
if keyword in prompt["title"].lower()     # 문자열 안에 들어 있나
if prompt["category"] not in categories   # 리스트 안에 없나
```

> `in`은 여기서처럼 "포함 검사"로도 쓰이고, `for x in 리스트`처럼 반복문에서도 쓰입니다.
> 같은 단어지만 역할이 다릅니다.

### 3-6. `not` 으로 참/거짓 뒤집기

[prompt_manager.py:274](prompt_manager.py#L274)

```python
prompt["favorite"] = not prompt["favorite"]
```

즐겨찾기 토글이 이 한 줄로 되는 이유입니다. True면 False로, False면 True로 바뀝니다.

---

## 4. 반복문

### 4-1. for — 정해진 개수만큼

[prompt_manager.py:185](prompt_manager.py#L185)

```python
for number, prompt in items:
    print(format_summary(number, prompt))
```

### 4-2. while True — 조건이 만족될 때까지 무한 반복

[prompt_manager.py:123-127](prompt_manager.py#L123-L127)

```python
while True:
    value = input(label).strip()
    if value:
        return value           # 값이 들어오면 여기서 빠져나감
    print("[안내] 값을 입력해 주세요.")
```

`while True`는 그냥 두면 영원히 돕니다. 반드시 `return`이나 `break`로 빠져나갈 길을 만들어야 합니다.

### 4-3. break / continue

[prompt_manager.py:463](prompt_manager.py#L463)

```python
break        # 반복문을 완전히 끝낸다 (0번 종료)
```

[prompt_manager.py:397-398](prompt_manager.py#L397-L398)

```python
if prompt["category"] != category:
    continue      # 이번 것만 건너뛰고 다음 반복으로
```

### 4-4. enumerate — 번호를 같이 꺼내기

[prompt_manager.py:133](prompt_manager.py#L133)

```python
for number, name in enumerate(CATEGORIES, start=1):
    print(f"{number}. {name}")
```

`enumerate`는 `(번호, 값)` 짝을 만들어 줍니다.
`start=1`을 주면 0이 아니라 1부터 셉니다. 사람이 보는 목록은 1번부터 시작하니까요.

```
enumerate(["텍스트 생성", "이미지 생성"], start=1)
→ (1, "텍스트 생성"), (2, "이미지 생성")
```

이걸 리스트로 만들어 둔 것이 `numbered_prompts()`입니다. [prompt_manager.py:170](prompt_manager.py#L170)

```python
return list(enumerate(prompts, start=1))
# → [(1, {...}), (2, {...}), (3, {...}), ...]
```

---

## 5. 리스트 컴프리헨션 — `pair for pair`의 정체

### 5-1. 기본 모양

[prompt_manager.py:201](prompt_manager.py#L201)

```python
items = [pair for pair in numbered_prompts() if pair[1]["category"] == category]
```

읽는 순서는 **가운데 → 오른쪽 → 왼쪽**입니다.

```
[  pair          for pair in numbered_prompts()      if pair[1]["category"] == category  ]
   ③ 넣을 것        ① 하나씩 꺼내서 pair라 부르고        ② 이 조건을 통과하면
```

for문으로 풀어 쓰면 똑같은 코드입니다.

```python
items = []
for pair in numbered_prompts():
    if pair[1]["category"] == category:
        items.append(pair)
```

`pair`는 `(3, {"title": "여백 쿠션...", ...})` 같은 튜플이므로
`pair[0]`은 번호, `pair[1]`은 딕셔너리입니다.
그래서 `pair[1]["category"]`가 "그 프롬프트의 카테고리"가 됩니다.

### 5-2. 꺼내면서 이름을 나눠 붙이기

[prompt_manager.py:212-216](prompt_manager.py#L212-L216)

```python
items = [
    (number, prompt)
    for number, prompt in numbered_prompts()
    if keyword in prompt["title"].lower() or keyword in prompt["content"].lower()
]
```

`for number, prompt in ...` 으로 받으면 `pair[0]`, `pair[1]` 대신
`number`, `prompt`라는 읽기 쉬운 이름을 쓸 수 있습니다.
조건이 길어질 때 이 방식이 훨씬 잘 읽힙니다.

> 위 두 개는 스타일 차이일 뿐 성능·동작은 같습니다.
> 조건이 짧으면 `pair`, 길면 풀어서 — 정도로 골랐습니다.

---

## 6. 함수

### 6-1. def / 매개변수 / return

[prompt_manager.py:173-176](prompt_manager.py#L173-L176)

```python
def format_summary(number, prompt):
    """목록 한 줄을 '번호. [카테고리] 제목 ⭐' 형태로 만든다."""
    star = " ⭐" if prompt["favorite"] else ""
    return f"{number}. [{prompt['category']}] {prompt['title']}{star}"
```

- `"""..."""` 는 **독스트링** — 이 함수가 뭘 하는지 적는 설명문입니다.
- `return`은 값을 돌려주면서 함수를 **즉시 끝냅니다**.
- `return`이 없는 함수는 자동으로 `None`을 돌려줍니다 (`print`만 하는 함수들).

### 6-2. 기본값이 있는 매개변수

[prompt_manager.py:289](prompt_manager.py#L289)

```python
def preview(text, length=30):
```

`preview(내용)` 이라고만 부르면 `length`는 30이 됩니다.
`preview(내용, 50)` 처럼 주면 50이 됩니다.

### 6-3. 여러 값 반환과 언패킹

[prompt_manager.py:240](prompt_manager.py#L240)

```python
return number, prompts[number - 1]     # 두 개를 한 번에 돌려준다
```

받는 쪽 [prompt_manager.py:250](prompt_manager.py#L250)

```python
number, prompt = selected      # 튜플을 두 변수로 풀어 담는다 (언패킹)
```

번호가 필요 없을 때는 `_`를 씁니다. [prompt_manager.py:273](prompt_manager.py#L273)

```python
_, prompt = selected     # 첫 번째 값은 안 쓴다는 표시
```

`_`도 사실은 그냥 변수 이름입니다. "이건 버리는 값"이라는 **관례**일 뿐입니다.

### 6-4. 조기 return (early return)

[prompt_manager.py:246-248](prompt_manager.py#L246-L248)

```python
selected = select_prompt("번호 입력: ")
if selected is None:
    return              # 잘못된 번호면 여기서 끝
number, prompt = selected
```

`else`로 감싸는 대신 **문제 상황을 먼저 걸러내고 빠져나가면** 들여쓰기가 깊어지지 않습니다.

### 6-5. 함수가 함수를 부르기

```python
show_list()  →  print_prompts()  →  format_summary()
```

기능을 잘게 나눠 두면 `print_prompts()` 하나를 목록 / 카테고리별 / 즐겨찾기 세 곳에서
그대로 재사용할 수 있습니다.

### 6-6. global — 함수 밖 변수를 바꿀 때

[prompt_manager.py:366](prompt_manager.py#L366)

```python
def load_from_json():
    global prompts
    ...
    prompts = json.load(file)     # prompts를 통째로 다른 리스트로 교체
```

주의할 점이 있습니다.

```python
prompts.append(...)      # 내용만 바꾸는 것 → global 필요 없음
prompts = [...]          # 변수 자체를 갈아끼우는 것 → global 필요함
```

그래서 `add_prompt()`에는 `global`이 없고 `load_from_json()`에만 있습니다.

---

## 7. 리스트·딕셔너리 관련 함수

| 문법 | 하는 일 | 쓴 곳 |
| --- | --- | --- |
| `len(x)` | 개수 세기 | [165](prompt_manager.py#L165) |
| `list.append(값)` | 맨 뒤에 추가 | [156](prompt_manager.py#L156) |
| `list.pop(위치)` | 그 위치의 값을 빼내며 삭제 | [335](prompt_manager.py#L335) |
| `int(문자열)` | 문자 "3" → 숫자 3 | [144](prompt_manager.py#L144) |
| `sorted(...)` | 정렬한 **새 리스트**를 만든다 | [351](prompt_manager.py#L351) |

### 7-1. sorted + key + lambda

[prompt_manager.py:351](prompt_manager.py#L351)

```python
ranked = sorted(viewed, key=lambda pair: pair[1]["views"], reverse=True)
```

- `key=` : **무엇을 기준으로** 정렬할지 정합니다.
- `lambda pair: pair[1]["views"]` : 이름 없는 짧은 함수입니다. 아래와 같은 뜻입니다.

  ```python
  def 기준(pair):
      return pair[1]["views"]
  ```

  `pair`를 받아서 조회수를 돌려줍니다. 즉 "조회수를 기준으로 정렬해라".
- `reverse=True` : 큰 것부터 (내림차순).

### 7-2. 중첩 언패킹

[prompt_manager.py:352](prompt_manager.py#L352)

```python
for rank, (number, prompt) in enumerate(ranked[:5], start=1):
```

`ranked`의 원소가 이미 `(번호, 딕셔너리)` 튜플인데 `enumerate`가 순위를 또 붙여서
`(순위, (번호, 딕셔너리))` 모양이 됩니다.
그래서 괄호를 한 겹 더 써서 안쪽까지 한 번에 풀어 담습니다.

---

## 8. 파일 다루기

### 8-1. with open — 열고 자동으로 닫기

[prompt_manager.py:359-360](prompt_manager.py#L359-L360)

```python
with open(DATA_FILE, "w", encoding="utf-8") as file:
    json.dump(prompts, file, ensure_ascii=False, indent=2)
```

- `"w"` 쓰기 / `"r"` 읽기
- `encoding="utf-8"` — 한글이 깨지지 않게 하는 설정
- `with ... as file:` — 블록이 끝나면 파일을 **자동으로 닫아 줍니다**

### 8-2. json

```python
json.dump(prompts, file, ensure_ascii=False, indent=2)   # 파이썬 → 파일
prompts = json.load(file)                                # 파일 → 파이썬
```

- `ensure_ascii=False` — 한글을 `안`처럼 바꾸지 않고 그대로 저장
- `indent=2` — 사람이 읽기 좋게 2칸 들여쓰기

### 8-3. os

| 문법 | 하는 일 | 쓴 곳 |
| --- | --- | --- |
| `os.path.exists(경로)` | 파일이 있는지 확인 | [369](prompt_manager.py#L369) |
| `os.makedirs(경로, exist_ok=True)` | 폴더 만들기 (이미 있어도 에러 안 남) | [385](prompt_manager.py#L385) |
| `os.path.join("export", "파일.md")` | OS에 맞는 경로로 합치기 | [393](prompt_manager.py#L393) |

---

## 9. 프로그램의 뼈대

### 9-1. import

[prompt_manager.py:7-8](prompt_manager.py#L7-L8)

```python
import json
import os
```

파이썬에 기본으로 들어 있는 표준 라이브러리라 따로 설치할 필요가 없습니다.
(미션 제약인 "외부 라이브러리 없이"에 어긋나지 않습니다.)

### 9-2. `if __name__ == "__main__":`

[prompt_manager.py:468-469](prompt_manager.py#L468-L469)

```python
if __name__ == "__main__":
    main()
```

- 이 파일을 **직접 실행**하면 → `__name__`이 `"__main__"`이 되어 `main()`이 돌아갑니다.
- 다른 파일에서 `import prompt_manager` 하면 → 함수 정의만 읽히고 프로그램은 안 켜집니다.

### 9-3. 주석과 상수

```python
# 이전 미션에서 실제로 작성했던 프롬프트를 기본 데이터로 등록한다.   ← 주석
CATEGORIES = [...]                                              ← 상수 (대문자 관례)
```

파이썬에는 진짜 상수가 없습니다. 대문자는 "바꾸지 말자"는 **약속**일 뿐입니다.

---

## 10. 한눈에 보기

| 분류 | 이 파일에서 쓴 것 |
| --- | --- |
| 자료형 | 리스트, 딕셔너리, 튜플, 문자열, 정수, 불리언, None |
| 조건 | `if` `elif` `else`, 조건 표현식, `not` `and` `or` `in` `is`, 연쇄 비교 |
| 반복 | `for`, `while True`, `break`, `continue`, `enumerate` |
| 함수 | `def`, 기본값 매개변수, `return`, 다중 반환, 언패킹, `lambda`, `global` |
| 자료구조 처리 | 리스트 컴프리헨션, `append`, `pop`, `len`, `sorted(key=...)`, 슬라이싱 |
| 문자열 | f-string, `strip`, `lower`, `replace`, `isdigit`, `*` 반복, 암묵적 연결 |
| 파일 | `with open`, `json.dump/load`, `os.path.exists`, `os.makedirs`, `os.path.join` |
| 구조 | `import`, 독스트링, 주석, `if __name__ == "__main__"` |
