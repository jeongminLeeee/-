from flask import Flask, render_template, request, redirect, session, jsonify
import json, os, datetime, calendar
import holidays
import os
from werkzeug.utils import secure_filename
app = Flask(__name__)
app.secret_key = "my_super_secret_key_1234"

from admin import admin_bp
app.register_blueprint(admin_bp)

ADMIN_ID = "jack22"
ADMIN_PASSWORD = "293025"

# 파일 경로
DATA_FILE = "data/users.json"
TASK_FILE = "data/tasks.json"
USER_CAL_FILE = "data/user_calendar.json"
USER_SCHEDULE_FILE = "data/user_schedule.json"
PROFILE_FILE = "data/profile.json"
CHAT_PATH = "data/chat.json"
SCHOOL_FILE = "data/school_schedule.json"
EVENT_FILE = "data/event_calendar.json"
HOME_FILE = "data/home_content.json"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
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

def load_tasks():
    with open(TASK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def admin_only():
    return session.get("role") == "admin"


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

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

def load_home():
    file_path = "data/home.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
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

        end_str = p.get("end") or p["start"]
        end_date = datetime.datetime.strptime(
            end_str, "%Y-%m-%d"
        ).date()

        # 🔥 스케줄 전용 D-day
        if start_date <= today <= end_date:
            d_day = 0
            status = 0   # 진행중

        elif today < start_date:
            d_day = (start_date - today).days
            status = 1   # 예정

        else:
            d_day = (today - end_date).days  # 🔥 D+
            status = 2   # 끝남

        schedules.append({
            "id": p["id"],
            "title": p["title"],
            "date": p["start"],
            "end": p.get("end", ""),
            "type": "personal",
            "color": "#97E054",
            "d_day": d_day,
            "status": status   # 🔥 추가
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
                "color": "#2DC8F2",
                "d_day": d_day
            })
    

    # -----------------------------
    # 🔥 학교 행사 추가 (여기에 넣기!)
    # -----------------------------
    event_data = load_event_calendar()
    selected_event_ids = event_data.get(user, [])

    all_events = load_school_events()

    for e in all_events:
        if str(e["id"]) in selected_event_ids:

            start_date = datetime.datetime.strptime(
                e["start_date"], "%Y-%m-%d"
            ).date()

            d_day = (start_date - today).days

            schedules.append({
                "id": e["id"],
                "title": f'📢 {e["name"]}',
                "date": e["start_date"],
                "end": e["end_date"],
                "type": "event",   # 🔥 중요
                "color": "#F7955D",  # 🔥 주황색
                "d_day": d_day
            })
            

    # -----------------------------
    # 🔥 정렬
    # -----------------------------
    if sort == "deadline":
        schedules.sort(key=lambda x: (
            x.get("status", 1),  # 🔥 끝난 일정 뒤로
            x["d_day"]
        ))

    elif sort == "name":
        schedules.sort(key=lambda x: (
            x.get("status", 1),
            x["title"].lower()
        ))

    else:
        schedules.sort(key=lambda x: (
            x.get("status", 1),
            -datetime.datetime.strptime(
                x["date"], "%Y-%m-%d"
            ).timestamp()
        ))

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

TASK_FILE = "data/tasks.json"

def load_tasks():
    with open(TASK_FILE, "r", encoding="utf-8") as f:
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
    home_data = load_home()
    return render_template("index.html", home=home_data)

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'  # 이미지 저장 폴더 설정
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 확장자 체크 함수
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/admin/upload_image", methods=["POST"])
def upload_image():
    if session.get("role") != "admin":
        return jsonify({"success": False}), 403

    # 파일이 제출되지 않았으면
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "파일이 없습니다."})

    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"success": False, "message": "잘못된 파일 형식입니다."})

    part = request.form.get('part')

    # 파일 저장 경로 설정
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    # 파일 저장
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    file.save(file_path)

    # home.json 파일에서 경로 업데이트
    file_url = f"/static/uploads/{filename}"

    home_file_path = 'data/home.json'
    if os.path.exists(home_file_path):
        with open(home_file_path, 'r', encoding='utf-8') as f:
            home = json.load(f)
    else:
        home = {}

    # 수정하려는 part에 해당하는 이미지를 업데이트
    home.setdefault("parts", {})
    home["parts"].setdefault(str(part), {})

    home["parts"][str(part)]["image"] = file_url

    # home.json 파일에 저장
    with open(home_file_path, 'w', encoding='utf-8') as f:
        json.dump(home, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})

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

            # 관리자 계정 확인
            if username == ADMIN_ID and password == ADMIN_PASSWORD:
                session["role"] = "admin"  # 관리자 권한 부여
            else:
                session["role"] = "user"   # 일반 사용자

            return redirect("/")
        error = "아이디 또는 비밀번호가 틀렸습니다."
    return render_template("login.html", error=error)


# -----------------------------
# 로그아웃
# -----------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    if session.get("role") != "admin":
        return "접근 금지", 403

    users = load_users()
    tasks = load_tasks()

    # 🔥 유저 삭제
    if request.method == "POST":
        action = request.form.get("action")

        if action == "delete_user":
            username = request.form.get("username")

            if username in users:
                del users[username]
                save_users(users)

        # 🔥 수행평가 추가
        elif action == "add_task":
            new_task = {
                "id": int(datetime.datetime.now().timestamp()),
                "title": request.form.get("title"),
                "subject": request.form.get("subject"),
                "grade": request.form.get("grade"),
                "class": request.form.get("class"),
                "date": request.form.get("date"),
                "context": request.form.get("context", ""),
                "img": ""
            }

            tasks.append(new_task)

            with open(TASK_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)

        return redirect("/admin")

    return render_template("admin.html", users=users, tasks=tasks)

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





# ---( 리뷰)--------------------------


def load_chat():
    if not os.path.exists(CHAT_PATH):
        return {}
    with open(CHAT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_chat(data):
    with open(CHAT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------
# 채팅 / 댓글 분리
# -------------------------
def split_chat(comments):
    main = []
    replies = {}

    for c in comments:
        cid, parent, content = c

        if parent == "":
            main.append(c)
        else:
            replies.setdefault(parent, []).append(c)

    return main, replies


# -------------------------
# 채팅 페이지
# -------------------------
@app.route("/chat")
def chat_home():
    chat = load_chat()

    all_posts = []

    for user, comments in chat.items():
        for c in comments:
            cid, parent, content = c

            if parent == "":
                all_posts.append({
                    "id": cid,
                    "user": user,
                    "content": content
                })

    # 최신순 정렬
    all_posts = sorted(all_posts, key=lambda x: x["id"], reverse=True)

    # 댓글 따로
    replies = {}
    for user, comments in chat.items():
        for c in comments:
            cid, parent, content = c
            if parent != "":
                replies.setdefault(parent, []).append({
                    "id": cid,
                    "content": content,
                    "user": user
                })

    return render_template(
        "chat.html",
        posts=all_posts,
        replies=replies
    )

    

@app.route("/add_post", methods=["POST"])
def add_post():
 
    if "user" not in session:
        return jsonify({"success": False})

    user = session["user"]
    data = request.get_json()
    content = data.get("content")

    chat = load_chat()

    if user not in chat:
        chat[user] = []

    # 🔥 ID 생성
    max_id = 0
    for u in chat:
        for c in chat[u]:
            if c[0] > max_id:
                max_id = c[0]

    new_id = max_id + 1

    # 저장
    chat[user].append([
        new_id,
        "",
        content
    ])

    save_chat(chat)

    return jsonify({"success": True})

@app.route("/add_reply/<int:post_id>", methods=["POST"])
def add_reply(post_id):
    if "user" not in session:
        return jsonify({"success": False})

    user = session["user"]
    data = request.get_json()
    content = data.get("content")

    chat = load_chat()

    if user not in chat:
        chat[user] = []

    # 🔥 고유 ID 생성 (추천 방식)
    import time
    new_id = int(time.time() * 1000)

    # 저장 (parent = post_id)
    chat[user].append([
        new_id,
        post_id,
        content
    ])

    save_chat(chat)

    return jsonify({
        "success": True,
        "reply_id": new_id
    })

@app.route("/user/<username>")
def user_posts(username):
    chat = load_chat()

    user_posts = []
    user_replies = []

    for user, comments in chat.items():
        for c in comments:
            cid, parent, content = c

            # 글
            if parent == "" and user == username:
                user_posts.append({
                    "id": cid,
                    "user": user,
                    "content": content
                })

            # 댓글
            if parent != "" and user == username:
                user_replies.append({
                    "post_id": parent,
                    "content": content
                })

    return render_template(
        "user.html",
        username=username,
        posts=user_posts,
        replies=user_replies
    )


@app.route("/edit_reply", methods=["POST"])
def edit_reply():
    data = request.json
    target_id = data["id"]
    new_content = data["content"]
    user = session.get("user")   # 🔥 추가

    chat = load_chat()

    for u in chat:
        if u != user:  # 🔥 본인만 수정
            continue

        for item in chat[u]:
           if str(item[0]) == str(target_id):
                item[2] = new_content

    save_chat(chat)

    return jsonify(success=True)

@app.route("/delete_item", methods=["POST"])
def delete_item():
    data = request.json
    target_id = data["id"]

    chat = load_chat()

    user = session.get("user")
    role = session.get("role")

    delete_ids = set([target_id])

    # 🔥 게시글이면 댓글까지 삭제
    for u in chat:
        for c in chat[u]:
            cid, parent, content = c
            if str(parent) == str(target_id):
                delete_ids.add(cid)

    # 🔥 삭제 실행 (관리자는 전체 삭제 가능)
    for u in chat:
        new_list = []

        for c in chat[u]:
            cid, parent, content = c

            if role == "admin":
                # 🔥 관리자: 무조건 삭제 가능
                if cid not in delete_ids:
                    new_list.append(c)
            else:
                # 🔥 일반유저: 본인 글만 삭제 가능
                if u == user and cid not in delete_ids:
                    new_list.append(c)

        chat[u] = new_list

    save_chat(chat)

    return jsonify(success=True)

@app.route("/edit_post", methods=["POST"])
def edit_post():
    data = request.json
    target_id = data["id"]
    new_content = data["content"]
    user = session.get("user")

    chat = load_chat()

    for u in chat:

        if u != user:   # 본인 글만 수정
            continue

        for item in chat[u]:
            cid, parent, content = item

            if cid == target_id and parent == "":
                item[2] = new_content

    save_chat(chat)

    return jsonify(success=True)
# -------------------------
# 학교 행사
# -------------------------

def load_school_events():
    with open(SCHOOL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    



def load_event_calendar():
    try:
        with open(EVENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_event_calendar(data):
    with open(EVENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


@app.route("/school_event")
def school_event_page():

    events = load_school_events()
    today = datetime.date.today()

    result = []

    for e in events:
        start = datetime.datetime.strptime(e["start_date"], "%Y-%m-%d").date()
        end = datetime.datetime.strptime(e["end_date"], "%Y-%m-%d").date()

        if today < start:
            # 시작 전 → D-
            d_day = (start - today).days

        elif start <= today <= end:
            # 🔥 진행 중 → D-Day 유지
            d_day = 0

        else:
            # 🔥 종료 후 → D+
            d_day = -(today - end).days

        result.append({
            "id": e["id"],
            "title": e["name"],
            "start": e["start_date"],
            "end": e["end_date"],
            "description": e["description"],
            "d_day": d_day
        })

    # 최신순 정렬
    result.sort(
        key=lambda x: datetime.datetime.strptime(x["start"], "%Y-%m-%d"),
        reverse=True
    )

    return render_template("school_event.html", events=result)

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    events = load_school_events()

    event = next((e for e in events if e["id"] == event_id), None)

    if not event:
        return "행사 없음", 404

    prev = request.args.get("from", "school_event")  # 🔥 추가

    return render_template(
        "event_detail.html",
        event=event,
        prev=prev   # 🔥 추가
    )

@app.route("/get_user_events")
def get_user_events():
    if "user" not in session:
        return jsonify({"tasks": []})

    data = load_event_calendar()
    user = session["user"]

    ids = data.get(user, [])  # ["5", "1"] 이런 형태

    return jsonify({
        "tasks": ids   # 🔥 그대로 반환
    })
@app.route("/add_event", methods=["POST"])

def add_event():
    
    if "user" not in session:
        return jsonify({"msg": "로그인 필요"}), 401

    event_id = request.json.get("event_id")
    user = session["user"]

    data = load_event_calendar()

    if user not in data:
        data[user] = []

    # 중복 방지
    event_id = str(request.json.get("event_id"))  # 문자열로 통일

    data = load_event_calendar()

    if user not in data:
        data[user] = []

    # 중복 방지
    if event_id in data[user]:
        return jsonify({"msg": "이미 추가됨"})

    data[user].append(event_id)  # 🔥 핵심: 그냥 문자열 저장
    save_event_calendar(data)

    return jsonify({"success": True})

@app.route("/remove_event", methods=["POST"])
def remove_event():
    if "user" not in session:
        return "", 401

    user = session["user"]
    event_id = str(request.json.get("event_id"))  # 🔥 무조건 문자열

    data = load_event_calendar()

    if user in data:
        print("삭제 전:", data[user])

        # 🔥 문자열 기준으로 정확히 제거
        data[user] = [
            str(e) for e in data[user]
            if str(e) != str(event_id)
        ]

        print("삭제 후:", data[user])

    save_event_calendar(data)

    return jsonify({"success": True})

@app.route("/get_user_events_full")
def get_user_events_full():
    if "user" not in session:
        return jsonify([])

    user = session["user"]

    # 유저가 추가한 행사 ID 목록
    data = load_event_calendar()
    selected_ids = data.get(user, [])

    # 전체 행사
    events = load_school_events()

    result = []

    for e in events:
        if str(e["id"]) in selected_ids:
            result.append({
                "id": e["id"],
                "title": e["name"],
                "start": e["start_date"],
                "end": e["end_date"]
            })

    return jsonify(result)

@app.route("/delete_user", methods=["POST"])
def delete_user():
    if session.get("role") != "admin":
        return jsonify({"success": False}), 403

    data = request.get_json()
    username = data["username"]

    users = load_users()

    if username in users:
        del users[username]

    save_users(users)

    return jsonify({"success": True})


@app.route("/admin/update_home", methods=["POST"])
def update_home():
    if session.get("role") != "admin":
        return jsonify({"success": False}), 403

    data = request.get_json()
    part = data.get('part')
    content = data.get('content')

    file_path = "data/home.json"

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            home = json.load(f)
    else:
        home = {}

    # 🔥 parts 구조 보장
    home.setdefault("parts", {})
    home["parts"].setdefault(str(part), {})

    # 🔥 여기 핵심 (기존 이미지 유지 + 글만 변경)
    home["parts"][str(part)] = {
        "text": content,
        "image": home["parts"][str(part)].get("image", "")
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(home, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})

@app.route("/admin/update_notice", methods=["POST"])
def update_notice():
    if session.get("role") != "admin":
        return jsonify({"success": False}), 403
    
    data = request.get_json()
    notice_content = data.get("notice")

    # 파일 경로
    file_path = "data/home.json"
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            home = json.load(f)
    else:
        home = {}
    
    # 공지 내용 수정
    home["notice"] = notice_content

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(home, f, ensure_ascii=False, indent=4)
    
    return jsonify({"success": True})

@app.route("/admin/update_intro", methods=["POST"])
def update_intro():
    if session.get("role") != "admin":
        return jsonify({"success": False}), 403
    
    data = request.get_json()
    intro_content = data.get("intro")

    # 파일 경로
    file_path = "data/home.json"
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            home = json.load(f)
    else:
        home = {}

    # 소개 내용 수정
    home["intro"] = intro_content

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(home, f, ensure_ascii=False, indent=4)
    
    return jsonify({"success": True})

@app.route("/admin/update_intro_image", methods=["POST"])
def update_intro_image():
    if session.get("role") != "admin":
        return jsonify({"success": False}), 403

    file = request.files["image"]
    filename = secure_filename(file.filename)

    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    file_url = f"/static/uploads/{filename}"

    home = load_home()
    home["intro_image"] = file_url

    with open("data/home.json", "w", encoding="utf-8") as f:
        json.dump(home, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)