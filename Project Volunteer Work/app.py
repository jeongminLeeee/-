from flask import Flask, render_template, request, redirect, session, jsonify
import json, os, datetime, calendar
import holidays
app = Flask(__name__)
app.secret_key = "1234"

# 파일 경로
DATA_FILE = "data/users.json"
TASK_FILE = "data/tasks.json"
USER_CAL_FILE = "data/user_calendar.json"

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
    today = datetime.datetime.today()
    for t in filtered_tasks:
        deadline = datetime.datetime.strptime(t["date"], "%Y-%m-%d")
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
import os, json

@app.route("/task/<int:task_id>")
def task_detail(task_id):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "data", "tasks.json")  # 🔥 핵심

    with open(file_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    task = next((t for t in tasks if t["id"] == task_id), None)

    return render_template("task_detail.html", task=task)
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)