# CLAUDE.md

## 项目概述

SCU 二课签到/签退码生成器 —— 为四川大学第二课堂活动生成签到/签退二维码。支持 Web 界面、命令行和纯前端三种方式。

## 使用方式

### 方式 A：Web 版（推荐）

双击 `scu-second-class/run_web.bat`，浏览器自动打开 `http://127.0.0.1:5000`。

- 验证码嵌在页面内，直接输入 → 登录 → 选择标签页 → 点击活动 → 生成二维码
- 两个标签页：
  - **我的活动**：已报名的，显示签到/签退状态、时间、地点，按 startTime 降序
  - **全部活动**：含时间、学时、所属库、地点、能力类型（德智体美劳），每页 25 条分页浏览，支持类型筛选
- 二维码直接在页面上显示

### 方式 B：命令行版

```bash
# 双击运行
scu-second-class/run.bat

# 或命令行
D:\Software\Anaconda\envs\scu-plus\python.exe main.py --id 活动ID
```

- 登录后可选：
  - \[1] 我的活动（已报名的）
  - \[2] 全部活动（含时间/学时/地点，可直接生成二维码）
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
├── main.py             # 核心逻辑（CLI + Web 共用函数）
├── index.html          # 纯前端版（已知 ID 直接用）
├── run_web.bat         # Web 版启动脚本
├── run.bat             # CLI 版启动脚本
└── qrcodes/            # CLI 版二维码输出目录
```

## 核心函数（main.py）

| 函数                                                | 说明                            |
| ------------------------------------------------- | ----------------------------- |
| `list_my_activities(token)`                              | 获取已报名活动（分页自动翻，按 startTime 降序）     |
| `list_all_activities(token)`                             | 获取全部活动详情（活动库 → 逐个库查详情，30 线程并发，Session 复用连接） |
| `filter_and_sort_activities(acts, keyword, days, type)`  | 关键词 + 天数 + 类型过滤 + 按时间排序（排除昨天前）    |
| `fetch_activity_lib_list(token)`                         | 获取 SIGNUPING + DOING 状态的活动库列表        |
| `fetch_activity_detail(token, lib_list)`                 | 并发获取各活动库详情（qualityName → activityType） |
| `quick_generate(activity_id)`                            | 跳过登录，直接生成签到/签退二维码                  |

## 认证链路

SCU 统一认证 (id.scu.edu.cn)
→ captcha\_data() 获取验证码 base64
→ SM2 C1C2C3 加密密码
→ login\_scu() POST rest\_token，用 requests.Session 保持 cookie，返回 (token, session)
→ get\_ccyl\_oauth\_code() 复用 session 手动跟随 CAS 重定向获取 code
→ CCYL 登录 loginByUc 获取 token
→ list-mine 获取已报名活动（有 activityId，可生成二维码）
→ SIGN\_URL (`dekt.scu.edu.cn/ccylmp/pages/main/index/signing`) 生成签到/签退链接

## 数据来源对比

| 来源   | 接口                                              | 返回                                                                                 | 能生成二维码 |
| ---- | ----------------------------------------------- | ---------------------------------------------------------------------------------- | :----: |
| 我的活动 | `list-mine`                                     | activityId, activityName, isSignIn, isSignOut, startTime, activityAddress            |    ✅   |
| 全部活动 | `list-activity-library` → `get-lib-detail/{id}` | activityId, activityName, classHour, statusName, start/end time, 所属库, 地点, 能力类型 |    ✅   |

## Web API 端点

| 端点                          | 说明                                                                 |
| --------------------------- | ------------------------------------------------------------------ |
| `GET /api/captcha`          | 获取验证码图片                                                            |
| `POST /api/login`           | 登录                                                                 |
| `POST /api/activities/mine` | 我的活动                                                               |
| `POST /api/activities/all`  | 全部活动（支持 `keyword`, `days_ahead`, `type`, `page`, `page_size`，分页返回 `total` 和 `types` 列表） |
| `POST /api/qrcode`          | 生成二维码（base64 图片）                                                   |
| `GET /api/config`           | 凭据配置状态                                                             |
| `GET /api/me`               | 当前登录用户                                                             |

## 修复记录

- **域名**：`zjczs.scu.edu.cn` → `dekt.scu.edu.cn`（微信 60003 安全域名错误）
- **全部活动浏览**：集成 SCU-2ndClass-AutoScraper 的活动发现功能，通过 `get-lib-detail` 获取具体活动实例（含时间、学时）
- **并发加载**：`fetch_activity_detail` 30 线程 + 共享 Session 复用 TCP 连接，从 ~25s 优化到 ~7s
- **分页**：Web 端"全部活动"每页 25 条，避免一次性渲染过多 DOM
- **SM2 加密**：C1C2C3 模式，需补 04 前缀，mode=0
- **CAS 认证**：`login_scu` 返回 `requests.Session` 保持 cookie，`get_ccyl_oauth_code` 复用 session 避免 CAS 登录页拦截
- **能力类型**：从活动库 `qualityName` 提取德智体美劳分类，前端支持类型下拉筛选
- **地点显示**：全部活动和我的活动均显示 `activityAddress`
- **时间过滤**：`filter_and_sort_activities` 增加下界过滤，排除昨天之前的历史活动

