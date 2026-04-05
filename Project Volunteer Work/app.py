from flask import Flask, render_template, request, redirect, session, jsonify
import json, os, datetime, calendar
import holidays
app = Flask(__name__)
app.secret_key = "my_super_secret_key_1234"

# 파일 경로
DATA_FILE = "data/users.json"
TASK_FILE = "data/tasks.json"
USER_CAL_FILE = "data/user_calendar.json"
USER_SCHEDULE_FILE = "data/user_schedule.json"
PROFILE_FILE = "data/profile.json"
# 폴더 자동 생성
os.makedirs("data", exist_ok=True)

for f, default in [
    (DATA_FILE, {}),
    (TASK_FILE, []),
    (USER_CAL_FILE, {})
]:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as file:
            json.dump(default, file, ensure_ascii=False, indent=4)


def load_profiles():
    """
    profile.json을 읽어서 딕셔너리 반환.
    파일이 없거나 잘못된 경우 빈 딕셔너리 반환
    """
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# -----------------------------
# 모든 템플릿에 profile 자동 주입
# -----------------------------
@app.context_processor
def inject_profile():
    """
    Jinja2 템플릿에서 {{ profile }} 사용 가능
    예: {{ profile.get(session['user'], '기본이미지.png') }}
    """
    profile = load_profiles()
    return dict(profile=profile)

# -----------------------------
# 프로필 업데이트 API
# -----------------------------
from flask import request, jsonify

@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "user" not in session:
        return jsonify({"success": False, "msg": "로그인 필요"}), 401

    user = session["user"]
    data = request.get_json()
    img = data.get("img")

    profiles = load_profiles()
    profiles[user] = img

    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})

# 🔥 내 일정 페이지
# -----------------------------
@app.route("/my_schedule")
def my_schedule():

    if "user" not in session:
        return render_template("my_schedule.html", schedules=[], sort="latest")

    user = session["user"]
    schedules = []

    # 🔥 오늘 날짜 (D-day 정확 계산용)
    today = datetime.date.today()

    # 🔥 정렬 옵션
    sort = request.args.get("sort", "latest")

    # -----------------------------
    # 🔥 개인 일정
    # -----------------------------
    try:
        with open(USER_SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            personal = data.get(user, [])
    except:
        personal = []

    for p in personal:

        start_date = datetime.datetime.strptime(
            p["start"], "%Y-%m-%d"
        ).date()

        d_day = (start_date - today).days

        schedules.append({
            "id": p["id"],
            "title": p["title"],
            "date": p["start"],
            "end": p.get("end", ""),
            "type": "personal",
            "color": "#10b981",
            "d_day": d_day
        })

    # -----------------------------
    # 🔥 수행평가
    # -----------------------------
    with open(USER_CAL_FILE, "r", encoding="utf-8") as f:
        user_cal = json.load(f)

    selected_ids = user_cal.get(user, [])
    all_tasks = load_tasks()

    for t in all_tasks:

        if str(t["id"]) in selected_ids:

            deadline = datetime.datetime.strptime(
                t["date"], "%Y-%m-%d"
            ).date()

            d_day = (deadline - today).days

            schedules.append({
                "id": t["id"],
                "title": f'{t["subject"]} - {t["title"]}',
                "date": t["date"],
                "end": "",
                "type": "task",
                "color": "#3b82f6",
                "d_day": d_day
            })

    # -----------------------------
    # 🔥 정렬
    # -----------------------------
    if sort == "deadline":
        schedules.sort(key=lambda x: x["d_day"])

    elif sort == "name":
        schedules.sort(key=lambda x: x["title"].lower())

    else:  # 최신순
        schedules.sort(
            key=lambda x: datetime.datetime.strptime(
                x["date"], "%Y-%m-%d"
            ),
            reverse=True
        )

    # -----------------------------
    # 🔥 페이지 반환
    # -----------------------------
    return render_template(
        "my_schedule.html",
        schedules=schedules,
        sort=sort
    )



@app.route("/update_personal_schedule", methods=["POST"])
def update_personal_schedule():

    if "user" not in session:
        return jsonify({"success": False})

    user = session["user"]
    data = request.get_json()
    schedule_id = str(data["id"])

    with open(USER_SCHEDULE_FILE, "r", encoding="utf-8") as f:
        schedules = json.load(f)

    for s in schedules.get(user, []):
        if str(s["id"]) == schedule_id:
            s["title"] = data["title"]
            s["start"] = data["start"]
            s["end"] = data["end"]
            s["description"] = data["description"]

    with open(USER_SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})

# -----------------------------
# 🔥 개인 일정 추가
# -----------------------------
@app.route("/add_personal_schedule", methods=["POST"])
def add_personal_schedule():
    if "user" not in session:
        return jsonify({"success": False}), 401

    data = request.get_json()
    user = session["user"]

    with open(USER_SCHEDULE_FILE, "r", encoding="utf-8") as f:
        schedules = json.load(f)

    if user not in schedules:
        schedules[user] = []

    schedules[user].append({
        "id": int(datetime.datetime.now().timestamp()),
        "title": data["title"],
        "start": data["start"],
        "end": data["end"],
        "description": data.get("description", ""),
        "category": "개인일정"
    })

    with open(USER_SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})


@app.route("/personal_schedule/<int:schedule_id>")
def personal_schedule_detail(schedule_id):

    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    if not os.path.exists(USER_SCHEDULE_FILE):
        return "데이터 없음"

    with open(USER_SCHEDULE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    schedules = data.get(user, [])

    for s in schedules:
        if s["id"] == schedule_id:
            return render_template(
                "personal_schedule_detail.html",
                schedule=s
            )

    return "일정을 찾을 수 없음"

# -----------------------------
# 🔥 개인 일정 불러오기 (캘린더용)
# -----------------------------
@app.route("/get_personal_schedule")
def get_personal_schedule():
    if "user" not in session:
        return jsonify([])

    user = session["user"]

    with open(USER_SCHEDULE_FILE, "r", encoding="utf-8") as f:
        schedules = json.load(f)

    return jsonify(schedules.get(user, []))


# -----------------------------
# 🔥 일정 삭제
# -----------------------------
@app.route("/delete_personal_schedule", methods=["POST"])
def delete_personal_schedule():
    if "user" not in session:
        return jsonify({"success": False})

    user = session["user"]
    data = request.get_json()
    schedule_id = str(data.get("id"))  # 🔥 문자열로 통일

    with open(USER_SCHEDULE_FILE, "r", encoding="utf-8") as f:
        schedules = json.load(f)

    # 🔥 핵심: id 비교를 문자열로 맞춤
    new_list = []
    for s in schedules.get(user, []):
        if str(s["id"]) != schedule_id:
            new_list.append(s)

    schedules[user] = new_list

    with open(USER_SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})


@app.route("/delete_task", methods=["POST"])
def delete_task():
    if "user" not in session:
        return jsonify({"success": False})

    user = session["user"]
    data = request.get_json()
    task_id = str(data["id"])

    with open(USER_CAL_FILE, "r", encoding="utf-8") as f:
        user_tasks = json.load(f)

    print("삭제 전:", user_tasks.get(user, []))

    if user in user_tasks:
        user_tasks[user] = [
            t for t in user_tasks[user]
            if t != task_id
        ]

    print("삭제 후:", user_tasks.get(user, []))

    with open(USER_CAL_FILE, "w", encoding="utf-8") as f:
        json.dump(user_tasks, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})



# -----------------------------
# 유저
# -----------------------------
def load_users():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# -----------------------------
# 수행평가
# -----------------------------
def load_tasks():
    with open(TASK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# 홈
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------
# 로그인
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_users()
        if username in users and users[username] == password:
            session["user"] = username
            return redirect("/")
        else:
            error = "아이디 또는 비밀번호가 틀렸습니다."
    return render_template("login.html", error=error)


# -----------------------------
# 로그아웃
# -----------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


# -----------------------------
# 회원가입
# -----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_users()
        if username in users:
            error = "이미 존재하는 아이디입니다."
        else:
            users[username] = password
            save_users(users)
            return redirect("/login")
    return render_template("signup.html", error=error)


# -----------------------------
# 수행평가 페이지
# -----------------------------
@app.route("/tasks", methods=["GET", "POST"])
def tasks_page():
    tasks_list = load_tasks()
    filtered_tasks = tasks_list.copy()

    grade = request.form.get("grade") if request.method == "POST" else None
    class_num = request.form.get("class") if request.method == "POST" else None
    sort = request.form.get("sort") if request.method == "POST" else None

    # 필터
    if grade and grade != "전체":
        filtered_tasks = [t for t in filtered_tasks if str(t["grade"]) == grade]

    if class_num and class_num != "전체":
        filtered_tasks = [t for t in filtered_tasks if str(t["class"]) == class_num]

    # D-day
    today = datetime.date.today()
    for t in filtered_tasks:
        deadline = datetime.datetime.strptime(t["date"], "%Y-%m-%d").date()
        t["d_day"] = (deadline - today).days

    # 정렬
    if sort == "deadline":
        filtered_tasks.sort(key=lambda x: x["d_day"])
    elif sort == "name":
        filtered_tasks.sort(key=lambda x: x["subject"])

    return render_template("tasks.html", tasks=filtered_tasks)


# -----------------------------
# 나의 캘린더
# -----------------------------
@app.route("/my_calendar")
def my_calendar():
    year = datetime.datetime.now().year

    kr_holidays = holidays.KR(years=year)

    holiday_dict = {}

    for date, name in kr_holidays.items():
        holiday_dict[str(date)] = name

    return render_template("my_calendar.html", holidays=holiday_dict)


# -----------------------------
# 캘린더 추가
# -----------------------------
@app.route("/add_task", methods=["POST"])
def add_task():
    if "user" not in session:
        return jsonify({"success": False, "message": "로그인 필요"}), 401
    data = request.get_json()
    task_id = str(data.get("task_id"))
    user = session["user"]

    with open(USER_CAL_FILE, "r", encoding="utf-8") as f:
        user_tasks = json.load(f)

    if user not in user_tasks:
        user_tasks[user] = []

    if task_id not in user_tasks[user]:
        user_tasks[user].append(task_id)

    with open(USER_CAL_FILE, "w", encoding="utf-8") as f:
        json.dump(user_tasks, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})


# -----------------------------
# 캘린더 제거
# -----------------------------
@app.route("/remove_task", methods=["POST"])
def remove_task():
    if "user" not in session:
        return jsonify({"success": False, "message": "로그인 필요"}), 401
    data = request.get_json()
    task_id = str(data.get("task_id"))
    user = session["user"]

    with open(USER_CAL_FILE, "r", encoding="utf-8") as f:
        user_tasks = json.load(f)

    if user in user_tasks and task_id in user_tasks[user]:
        user_tasks[user].remove(task_id)

    with open(USER_CAL_FILE, "w", encoding="utf-8") as f:
        json.dump(user_tasks, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})



@app.route("/get_holidays")
def get_holidays():
    year = int(request.args.get("year"))

    kr_holidays = holidays.KR(years=year)

    holiday_dict = {}
    for date, name in kr_holidays.items():
        holiday_dict[str(date)] = name

    return jsonify(holiday_dict)




# -----------------------------
# 사용자 캘린더 목록
# -----------------------------
@app.route("/get_user_tasks")
def get_user_tasks():
    if "user" not in session:
        return jsonify({"tasks": []})

    user = session["user"]

    # 유저 캘린더
    with open(USER_CAL_FILE, "r", encoding="utf-8") as f:
        user_tasks = json.load(f)

    selected_ids = user_tasks.get(user, [])

    # 전체 수행평가
    all_tasks = load_tasks()

    result = []
    for t in all_tasks:
        if str(t["id"]) in selected_ids:
            result.append({
                "id": t["id"],
                "title": t["subject"] + " - " + t["title"],
                "date": t["date"]
            })

    return jsonify({"tasks": result})


# -----------------------------
# 자세히 보기 창

@app.route("/task/<int:task_id>")
def task_detail(task_id):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "data", "tasks.json")

    with open(file_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    task = next((t for t in tasks if t["id"] == task_id), None)

    # 🔥 어디서 왔는지 확인
    prev = request.args.get("from", "tasks")

    return render_template("task_detail.html", task=task, prev=prev)
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)