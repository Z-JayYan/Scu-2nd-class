# CLAUDE.md

## 项目概述

SCU 二课签到/签退码生成器 —— 为四川大学第二课堂活动生成签到/签退二维码。支持 Web 界面、命令行和纯前端三种方式。

## 使用方式

### 方式 A：Web 版（推荐）

双击 `scu-second-class/run_web.bat`，浏览器自动打开 `http://127.0.0.1:5000`。
- 验证码嵌在页面内，直接输入 → 登录 → 点击活动 → 生成二维码
- 账号已内置，只需输入验证码
- 支持活动关键词过滤
- 二维码直接在页面上显示

### 方式 B：命令行版

```bash
# 双击运行
scu-second-class/run.bat

# 或命令行
D:\Software\Anaconda\envs\scu-plus\python.exe main.py --id 活动ID
```
- 账号已内置直接回车，仅需输验证码
- 支持循环生成：生成完后输入 `b` 返回列表，输入 `q` 退出
- 二维码保存到 `qrcodes/` 并自动打开文件夹

### 方式 C：纯前端（已知活动 ID，无需登录）

打开 `scu-second-class/index.html`，输入活动 ID 或 URL 直接生成。

## 技术栈

- **Python** 3.12（conda 环境 `scu-plus`）
- **Flask** Web 后端
- 关键依赖：`gmssl`（SM2 密码加密）、`requests`（HTTP）、`qrcode`（二维码生成）

## 项目结构

```
scu-second-class/
├── app.py              # Flask 后端（Web 版核心）
├── templates/
│   └── index.html      # Web 前端页面
├── main.py             # Python CLI 版（Web 版复用其认证/API 函数）
├── index.html          # 纯前端版（已知 ID 直接用）
├── run_web.bat         # Web 版启动脚本
├── run.bat             # CLI 版启动脚本
└── qrcodes/            # CLI 版二维码输出目录
```

## 认证链路

SCU 统一认证 (id.scu.edu.cn)
→ captcha_data() 获取验证码 base64
→ SM2 C1C2C3 加密密码
→ POST rest_token 获取 access_token
→ OAuth sp_logged 跳转获取 code
→ CCYL 登录 loginByUc 获取 token
→ list-mine 获取已报名活动（有 activityId，可生成二维码）
→ SIGN_URL (`dekt.scu.edu.cn/ccylmp/pages/main/index/signing`) 生成签到/签退链接

## 关键差异

| 接口 | 返回字段 | 说明 |
|------|---------|------|
| `list-mine` | `activityId`, `activityName`, `isSignIn`, `isSignOut` | 已报名的活动实例，可生成二维码 |
| `list-activity-library` | `activityLibraryId`, `name` | 活动模板，无 activityId，需先报名 |

## API 关键接口

| 步骤 | URL | 说明 |
|------|-----|------|
| 验证码 | `GET id.scu.edu.cn/api/.../captcha` | 返回 base64 图片 |
| SM2 公钥 | `POST id.scu.edu.cn/api/.../sm2_key` | 返回加密公钥 |
| 登录 | `POST id.scu.edu.cn/api/.../rest_token` | SM2 加密密码提交 |
| CCYL OAuth | `GET id.scu.edu.cn/api/.../commons/sp_logged` | SSO → code |
| CCYL 登录 | `POST dekt.scu.edu.cn/ccyl-api/app/auth/loginByUc` | code → token |
| 我的活动 | `POST dekt.scu.edu.cn/ccyl-api/app/activity/list-mine` | 已报名活动（有签到 ID） |
| 活动库 | `POST dekt.scu.edu.cn/ccyl-api/app/activity/list-activity-library` | 活动模板（无签到 ID） |

## 修复记录

- **域名**：`zjczs.scu.edu.cn` → `dekt.scu.edu.cn`（微信 60003 安全域名错误）
- **分页**：活动列表自动翻页取全部
- **活动库问题**：`list-activity-library` 返回模板，无 `activityId`，不可直接生成二维码
- **SM2 加密**：C1C2C3 模式，需补 04 前缀，mode=0
