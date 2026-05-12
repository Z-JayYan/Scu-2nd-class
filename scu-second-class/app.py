"""
SCU 二课 Web 版 — Flask 后端
"""
import base64
import os
import secrets
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

import qrcode
from flask import Flask, render_template, request, jsonify, session

from main import (
    captcha_data, login_scu, get_ccyl_oauth_code, login_ccyl,
    list_my_activities, search_activity_library, SIGN_URL,
    DEFAULT_USERNAME, DEFAULT_PASSWORD,
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

_executor = ThreadPoolExecutor(max_workers=2)


def _gen_qr_b64(url: str) -> str:
    """生成二维码，返回 base64 data URL"""
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _require_auth():
    if not session.get("ccyl_token"):
        return jsonify(success=False, error="未登录")
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/captcha", methods=["GET", "POST"])
def api_captcha():
    try:
        code, img_b64 = captcha_data()
        session["captcha_code"] = code
        return jsonify(success=True, image=f"data:image/png;base64,{img_b64}")
    except Exception as e:
        return jsonify(success=False, error=str(e))


@app.post("/api/login")
def api_login():
    data = request.get_json(force=True)
    captcha_text = data.get("captcha_text", "").strip()
    captcha_code = session.pop("captcha_code", "")

    if not captcha_text:
        return jsonify(success=False, error="请输入验证码")

    try:
        token = login_scu(DEFAULT_USERNAME, DEFAULT_PASSWORD, captcha_code, captcha_text)
        oauth_code = get_ccyl_oauth_code(token)
        ccyl_token, user = login_ccyl(oauth_code)
        session["ccyl_token"] = ccyl_token
        session["user_name"] = user.get("realname", user.get("userName", "?"))
        return jsonify(success=True, user_name=session["user_name"])
    except Exception as e:
        return jsonify(success=False, error=f"登录失败: {e}")


@app.post("/api/activities/mine")
def api_activities_mine():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True) or {}
    keyword = data.get("keyword", "").strip()

    try:
        activities = list_my_activities(session["ccyl_token"])
        if keyword:
            activities = [
                a for a in activities
                if keyword.lower() in (a.get("activityName") or "").lower()
            ]
        items = [
            {
                "activity_id": a.get("activityId"),
                "name": a.get("activityName", "?"),
                "sign_in": a.get("isSignIn") == "1",
                "sign_out": a.get("isSignOut") == "1",
            }
            for a in activities
        ]
        return jsonify(success=True, activities=items)
    except Exception as e:
        return jsonify(success=False, error=str(e))


@app.post("/api/activities/library")
def api_activities_library():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True) or {}
    keyword = data.get("keyword", "").strip()

    try:
        activities = search_activity_library(session["ccyl_token"], keyword)
        items = [
            {
                "library_id": a.get("activityLibraryId", "?"),
                "name": a.get("name", "?"),
            }
            for a in activities
        ]
        return jsonify(success=True, activities=items, is_library=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))


@app.post("/api/qrcode")
def api_qrcode():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(force=True)
    activity_id = data.get("activity_id", "").strip()
    activity_name = data.get("activity_name", "").strip()

    if not activity_id:
        return jsonify(success=False, error="缺少活动 ID")

    in_url = SIGN_URL.format(type="in", activity_id=activity_id)
    out_url = SIGN_URL.format(type="out", activity_id=activity_id)

    # 并行生成两个二维码
    fut_in = _executor.submit(_gen_qr_b64, in_url)
    fut_out = _executor.submit(_gen_qr_b64, out_url)

    return jsonify(
        success=True,
        url_in=in_url,
        url_out=out_url,
        qr_in=fut_in.result(),
        qr_out=fut_out.result(),
        activity_name=activity_name,
    )


@app.get("/api/me")
def api_me():
    if session.get("ccyl_token"):
        return jsonify(success=True, logged_in=True, user_name=session.get("user_name"))
    return jsonify(success=True, logged_in=False)


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    app.run(host="127.0.0.1", port=5000, debug=False)
