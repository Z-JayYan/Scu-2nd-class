"""
SCU 二课签到/签退码生成器
通过 SCU 统一认证登录 → 获取活动列表 → 生成签到/签退二维码
"""
import base64
import json
import os
import sys
import tempfile
import time
import webbrowser
from io import BytesIO

import qrcode
import requests
from gmssl import sm2

# ── Windows 中文编码兼容 ──────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 常量 ──────────────────────────────────────────────────
AUTH_BASE = "https://id.scu.edu.cn"
CCYL_API  = "https://dekt.scu.edu.cn/ccyl-api"
CLIENT_ID = "1371cbeda563697537f28d99b4744a973uDKtgYqL5B"
ENTERPRISE_ID = "scdx"
SP_CODE = (
    "bDBhREE1WDMzK3llSzZyVFZNeE81czRDd1hESTI4NWxGaFdsTnlvcGt3eVdTb2cxSjN5a1FJTDVMWTBEQkFFd2k1bWZRMy82OXN6"
    "V21ZYzFLd2NlSDdUaWlVcVJ1emxVVnF4Q3RZNWxjWlVoTEZqUktVSWVmY1ZaKzBLYUlBWDYvaU5MS1E5Y25nT1BoSzRIM0FIOWVC"
    "QjMxMXd5b0JrenNuWDBDM1BKU0FwUVVnZHdoSWYrc0hKZmEwSHRQbFZDV1o2dzFtQ3Nuci9wV1ExZHRMMytueHpLZVg5djJJcGFR"
    "bkJxZFJCQWJZWHI2dlpQNHVxNFNhcHM3Y3RkK2g1dWFuUEtNT1JZblFXRFBLUEdrcGdxNHR5eEcxclh5YXQ5a2FXN3JSZ2g2OTAx"
    "WCt0TUdTNXJDRVdNeDNTU3duTk1nNW9RSyt4WkdzSjNkR3NvVEFDMzFCQmJHUVcrVitybmszQVd0djFpUUJ5dDJySlRTajZIem1q"
    "ZFYwMjVWcVpEaUtKd1AwQzI3TUpZd3FyY1hqdkxUZkFCd3JwL3ltczdXcmlTUzhZYVJPR0QwOXk2aDJIdUlCUTAvbEJWd0xzcUZX"
    "SElxaENpR0pseG1XYTZRbWlFaklERTd6TlhBQkJLdTZGUS8rNTBBYWRkcDVrRXdBM0tqejMvd1AvTklkZW5oNll4MllINlFiNVRu"
    "cXNhZWtzUlh3d1BOQzBrMERSM0tId3dyS1hONkF6VDZwRGl3S3h1aDNLSGVmcTBRTktXUXMxTTZxeW1lcmgzYVlGWDNmVHdvUnJk"
    "WXVhbHN0aEtHKzU5TnFuVm1NbXU4dnhZQk8zKzQrdnV3aTJEaGY4VXRnV3lHeTVBcFFnWlUyQTFsWjdsR1RyNHh1TjV5dUlVc1VN"
    "NTRlbEtETTVVYWZoYnFPTXFrM2MxUHVNSHVHLzRtUFk4cmZzaXNUVkovWlhuSkhWWXpYQUJ4UDE4bGt2NXJkMFlXZHM0cFlYVVdu"
    "Ky9ZWGNKTlBDNEVrSzE3R0NVWDNxcCtiQkVyaXMzaTRXam1wWTFzYkpWZTAxYzZ0VGlxcGkvcEYyLzJPND0="
)
SIGN_URL = "https://dekt.scu.edu.cn/ccylmp/pages/main/index/signing?type={type}&state=1&id={activity_id}"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": AUTH_BASE,
    "Referer": f"{AUTH_BASE}/frontend/login",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    ),
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qrcodes")

# ── .env 文件加载（优先级高于默认值）────────────────────────
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_FILE):
    for _line in open(_ENV_FILE, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            _key, _val = _key.strip(), _val.strip()
            if _key in ("SCU_USERNAME", "SCU_PASSWORD") and _val:
                os.environ[_key] = _val

# 默认账号（环境变量 / .env / 默认值 → 自动提示输入）
DEFAULT_USERNAME = os.environ.get("SCU_USERNAME", "")
DEFAULT_PASSWORD = os.environ.get("SCU_PASSWORD", "")


# ── SM2 加密 ──────────────────────────────────────────────
def encrypt_sm2_c1c2c3(plaintext: str, public_key_b64: str) -> str:
    """SM2 C1C2C3 模式加密，输出 base64(04||C1||C2||C3)"""
    pub_bytes = base64.b64decode(public_key_b64)
    pub_hex = pub_bytes.hex()  # 可能带 04 前缀，CryptSM2 会自动处理

    # mode=0 → C1C2C3；只加密，不需要私钥
    sm2_obj = sm2.CryptSM2(private_key="", public_key=pub_hex, mode=0)
    cipher_bytes = sm2_obj.encrypt(plaintext.encode())
    # encrypt 返回 C1||C2||C3（C1 不含 04 前缀），服务端要求补 04
    result = b"\x04" + cipher_bytes
    return base64.b64encode(result).decode()


# ── HTTP 工具 ─────────────────────────────────────────────
def parse_json(resp: requests.Response, label: str = "") -> dict:
    try:
        return resp.json()
    except Exception:
        raise RuntimeError(f"[{label}] JSON 解析失败: {resp.text[:300]}")


def api_post(url: str, json_body: dict, headers: dict = None, label: str = "") -> dict:
    h = {**HEADERS, **(headers or {})}
    r = requests.post(url, headers=h, json=json_body, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"[{label}] HTTP {r.status_code}: {r.text[:300]}")
    return parse_json(r, label)


def api_get(url: str, headers: dict = None, label: str = "", allow_redirects: bool = True) -> requests.Response:
    h = {**HEADERS, **(headers or {})}
    r = requests.get(url, headers=h, timeout=15, allow_redirects=allow_redirects)
    if r.status_code != 200 and allow_redirects:
        raise RuntimeError(f"[{label}] HTTP {r.status_code}: {r.text[:300]}")
    return r


# ── SCU 认证 ──────────────────────────────────────────────
def captcha_data() -> tuple[str, str]:
    """获取验证码，返回 (code, image_base64)，不弹浏览器"""
    ts = int(time.time() * 1000)
    url = f"{AUTH_BASE}/api/public/bff/v1.2/one_time_login/captcha?_enterprise_id={ENTERPRISE_ID}&timestamp={ts}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    data = parse_json(resp, "captcha")["data"]
    img_b64 = data.get("captcha") or data.get("image") or data.get("img") or data["captchaImage"]
    code = data["code"]
    if not img_b64 or not code:
        raise RuntimeError(f"验证码字段缺失: {json.dumps(data, ensure_ascii=False)}")
    return str(code), img_b64


def fetch_captcha() -> tuple[str, str]:
    """获取验证码，返回 (code, image_base64)，同时弹浏览器显示图片"""
    code, img_b64 = captcha_data()
    img_bytes = base64.b64decode(img_b64)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(img_bytes)
    tmp.close()
    webbrowser.open(tmp.name)
    print(f"[验证码图片已打开: {tmp.name}]")
    return code, img_b64


def get_sm2_key() -> tuple[str, str]:
    """获取 SM2 公钥，返回 (public_key_base64, sm2_code)"""
    data = api_post(f"{AUTH_BASE}/api/public/bff/v1.2/sm2_key", {}, label="sm2_key")
    d = data["data"]
    return str(d["publicKey"]), str(d["code"])


def login_scu(username: str, password: str, captcha_code: str, captcha_text: str) -> str:
    """SCU 统一认证登录，返回 access_token"""
    public_key, sm2_code = get_sm2_key()
    encrypted_pw = encrypt_sm2_c1c2c3(password, public_key)

    payload = {
        "client_id": CLIENT_ID,
        "grant_type": "password",
        "scope": "read",
        "username": username,
        "password": encrypted_pw,
        "_enterprise_id": ENTERPRISE_ID,
        "sm2_code": sm2_code,
        "cap_code": captcha_code,
        "cap_text": captcha_text,
    }
    result = api_post(f"{AUTH_BASE}/api/public/bff/v1.2/rest_token", payload, label="rest_token")
    if result.get("success") is not True:
        raise RuntimeError(f"登录失败: {result.get('msg', result)}")

    token = result["data"]["access_token"]
    return str(token)


# ── CCYL 认证 ─────────────────────────────────────────────
def get_ccyl_oauth_code(access_token: str) -> str:
    """通过 SCU access_token 获取 CCYL OAuth code"""
    url = (
        f"{AUTH_BASE}/api/bff/v1.2/commons/sp_logged"
        f"?access_token={access_token}"
        f"&sp_code={SP_CODE}"
        f"&application_key=scdxplugin_cas_apereo17"
    )
    # 手动跟踪重定向，因为 requests 可能不会暴露最终 URL
    resp = requests.get(url, headers={**HEADERS, "Accept": "text/html,*/*"}, allow_redirects=True, timeout=30)

    final_url = resp.url
    if "code=" in str(final_url):
        from urllib.parse import urlparse, parse_qs
        return parse_qs(urlparse(str(final_url)).query)["code"][0]

    # 兜底：从响应体中提取
    import re
    body = resp.text
    m = re.search(r'url=([^"\'>\s]+)', body, re.IGNORECASE)
    if m and "code=" in m.group(1):
        from urllib.parse import urlparse, parse_qs
        return parse_qs(urlparse(m.group(1)).query)["code"][0]

    raise RuntimeError(f"OAuth 未返回 code，最终 URL: {final_url}")


def login_ccyl(oauth_code: str) -> tuple[str, dict]:
    """CCYL 登录，返回 (token, user)"""
    headers = {"Origin": "https://dekt.scu.edu.cn", "Referer": "https://dekt.scu.edu.cn"}
    data = api_post(
        f"{CCYL_API}/app/auth/loginByUc",
        {"code": oauth_code},
        headers=headers,
        label="ccyl_login",
    )
    if data["code"] != 0:
        raise RuntimeError(f"CCYL 登录失败: {data.get('msg', data)}")
    return str(data["token"]), data["user"]


# ── 活动操作 ──────────────────────────────────────────────
def _ccyl_headers(token: str) -> dict:
    return {"Origin": "https://dekt.scu.edu.cn", "Referer": "https://dekt.scu.edu.cn", "token": token}


def list_my_activities(token: str, page_size: int = 100) -> list[dict]:
    """获取我的活动列表（自动翻页，取全部）"""
    all_items = []
    page = 1

    while True:
        data = api_post(
            f"{CCYL_API}/app/activity/list-mine",
            {"pn": page, "time": str(int(time.time() * 1000)), "ps": page_size},
            headers=_ccyl_headers(token),
            label="list-mine",
        )
        if data["code"] != 0:
            raise RuntimeError(f"获取活动列表失败: {data.get('msg', data)}")

        content = data.get("content", [])
        all_items.extend(content)

        # 判断是否还有下一页
        total = data.get("totalElements") or data.get("total") or data.get("count")
        if total is not None and len(all_items) >= int(total):
            break
        if len(content) < page_size:
            break
        page += 1

    return all_items


def search_activity_library(token: str, name: str = "", page_size: int = 100) -> list[dict]:
    """搜索活动库（所有可报名的活动），自动翻页取全部"""
    all_items = []
    page = 1

    while True:
        data = api_post(
            f"{CCYL_API}/app/activity/list-activity-library",
            {"pn": page, "time": str(int(time.time() * 1000)), "ps": page_size, "name": name,
             "level": "", "scoreType": "", "org": "", "order": "", "status": "", "quality": ""},
            headers=_ccyl_headers(token),
            label="list-activity-library",
        )
        if data["code"] != 0:
            raise RuntimeError(f"搜索活动失败: {data.get('msg', data)}")

        items = data.get("list", data.get("content", []))
        all_items.extend(items)

        total = data.get("totalElements") or data.get("total") or data.get("count")
        if total is not None and len(all_items) >= int(total):
            break
        if len(items) < page_size:
            break
        page += 1

    return all_items


# ── 二维码生成 ────────────────────────────────────────────
def generate_qrcode(url: str, label: str) -> str:
    """生成二维码图片，返回文件路径"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    safe_label = "".join(c for c in label if c.isalnum() or c in "._- ")
    filename = f"{safe_label}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    img.save(filepath)
    return filepath


def print_qrcode_terminal(url: str):
    """在终端打印 ASCII 二维码"""
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.make()
    qr.print_ascii()


# ── 快速模式：已有活动ID直接生成 ─────────────────────────
def quick_generate(activity_id: str):
    """直接通过活动 ID 生成二维码（跳过登录）"""
    in_url = SIGN_URL.format(type="in", activity_id=activity_id)
    out_url = SIGN_URL.format(type="out", activity_id=activity_id)

    print(f"  签到 URL: {in_url}")
    print(f"  签退 URL: {out_url}")
    print(f"\n  生成二维码中...")
    in_file = generate_qrcode(in_url, f"签到_{activity_id}")
    out_file = generate_qrcode(out_url, f"签退_{activity_id}")

    print(f"  ✅ 签到码: {in_file}")
    print(f"  ✅ 签退码: {out_file}")
    webbrowser.open(OUTPUT_DIR)
    print(f"  已打开二维码文件夹: {OUTPUT_DIR}")


# ── 完整登录模式 ──────────────────────────────────────────
def full_login_flow():
    """登录 → 获取活动列表 → 选择活动 → 生成二维码"""
    # 1. 登录
    print("\n[1/4] SCU 统一认证登录")
    username = DEFAULT_USERNAME or input("请输入学号: ").strip()
    password = DEFAULT_PASSWORD or input("请输入密码: ").strip()
    if not username or not password:
        print("  ❌ 学号和密码不能为空")
        sys.exit(1)
    print(f"  学号: {username}")

    captcha_code, _ = fetch_captcha()
    captcha_text = input("请输入验证码: ").strip()

    print("  登录中...")
    try:
        access_token = login_scu(username, password, captcha_code, captcha_text)
        print("  ✅ SCU 认证成功")
    except Exception as e:
        print(f"  ❌ SCU 登录失败: {e}")
        sys.exit(1)

    # 2. CCYL OAuth
    print("\n[2/4] 获取二课授权...")
    try:
        oauth_code = get_ccyl_oauth_code(access_token)
        ccyl_token, user = login_ccyl(oauth_code)
        print(f"  ✅ 二课登录成功，用户: {user.get('realname', user.get('userName', '?'))}")
    except Exception as e:
        print(f"  ❌ 二课授权失败: {e}")
        sys.exit(1)

    # 3-4. 活动选择 & 二维码生成（循环，可返回重复提取）
    while True:
        print("\n[3/4] 获取活动列表...")
        print("  [1] 我的活动（已报名的）")
        print("  [2] 搜索活动库（全部活动）")
        mode = input("  请选择 (1/2，默认1，输入 q 退出): ").strip() or "1"
        if mode.lower() == "q":
            print("  已退出")
            break

        try:
            if mode == "2":
                keyword = input("  输入关键词搜索（直接回车=全部）: ").strip()
                print("  正在获取活动库（自动翻页）...")
                print("  ⚠️  活动库中的项目是【模板】，需先报名才会生成活动ID")
                activities = search_activity_library(ccyl_token, keyword)
                is_library = True
            else:
                keyword = input("  输入关键词过滤（直接回车=全部）: ").strip()
                print("  正在获取我的活动（自动翻页）...")
                activities = list_my_activities(ccyl_token)
                if keyword:
                    activities = [a for a in activities if keyword.lower() in (a.get("activityName", "") or "").lower()]
                    print(f"  过滤后 {len(activities)} 个活动")
                is_library = False

            if not activities:
                if mode == "2":
                    print("  ⚠️  未找到匹配的活动")
                else:
                    print("  ⚠️  没有已报名的活动，试试选择 [2] 搜索活动库")
                continue
        except Exception as e:
            print(f"  ❌ 获取活动失败: {e}")
            continue

        # 选择活动
        print(f"\n  共 {len(activities)} 个活动:")
        for i, a in enumerate(activities):
            if is_library:
                # 活动库：只有 activityLibraryId + name，无 activityId
                aid = a.get("activityLibraryId", "?")
                name = a.get("name", "?")
                sign_info = "需报名"
            else:
                # 我的活动：有完整字段
                aid = a.get("activityId", "?")
                name = a.get("activityName", "?")
                is_sign_in = a.get("isSignIn")
                is_sign_out = a.get("isSignOut")
                sign_in = "签到✓" if is_sign_in == "1" else ("签到✗" if is_sign_in == "0" else "?")
                sign_out = "签退✓" if is_sign_out == "1" else ("签退✗" if is_sign_out == "0" else "?")
                sign_info = f"{sign_in} {sign_out}"
            print(f"  [{i}] {name}  ({sign_info})  ID: {aid}")

        print("\n[4/4] 生成二维码")
        if is_library:
            print("  ⚠️  活动库项目没有签到ID，请先报名后从【我的活动】中生成")
            input("  按 Enter 返回列表...")
            continue

        choice = input(f"请选择活动序号 (0-{len(activities)-1})，或直接输入活动ID，输入 b 返回: ").strip()

        if choice.lower() == "b":
            continue

        activity_id = None
        if choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(activities):
                activity_id = activities[idx].get("activityId")
            else:
                activity_id = choice
        else:
            activity_id = choice

        if not activity_id:
            print("❌ 无效的活动 ID")
            continue

        quick_generate(activity_id)
        print()


# ── 入口 ──────────────────────────────────────────────────
def main():
    # 命令行参数支持：python main.py --id 活动ID
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg in ("-h", "--help"):
                print("用法:")
                print("  python main.py                  交互式登录，获取活动列表并生成二维码")
                print("  python main.py --id <活动ID>     跳过登录，直接生成签到/签退二维码")
                return
            if arg == "--id" or arg == "-i":
                idx = sys.argv.index(arg)
                if idx + 1 < len(sys.argv):
                    quick_generate(sys.argv[idx + 1])
                    return
            if arg.startswith("--id="):
                quick_generate(arg.split("=", 1)[1])
                return

    print("=" * 60)
    print("  SCU 二课签到/签退码生成器")
    print("=" * 60)
    full_login_flow()


if __name__ == "__main__":
    main()
