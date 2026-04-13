from flask import Blueprint, request, jsonify, session
import json, datetime, os

# 🔥 블루프린트 생성
admin_bp = Blueprint("admin", __name__)

# 🔥 파일 경로
TASK_FILE = "data/tasks.json"

# 🔥 관리자 체크
def is_admin():
    return session.get("role") == "admin"

@admin_bp.route("/admin/add_task", methods=["POST"])
def add_task():
    if not is_admin():
        return jsonify({"success": False}), 403

    data = request.get_json()

    # 파일 읽기
    if os.path.exists(TASK_FILE):
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    else:
        tasks = []

    # 추가
    tasks.append({
        "id": int(datetime.datetime.now().timestamp()),
        "title": data["title"],
        "subject": data["subject"],
        "date": data["date"],
        "grade": data["grade"],
        "class": data["class"],
        "context": data.get("context", ""),
        "img": data.get("img", "")
    })

    # 저장
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    return jsonify({"success": True})