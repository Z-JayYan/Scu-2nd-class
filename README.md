# SCU 二课签到/签退码生成器

为四川大学第二课堂活动生成签到/签退二维码，支持 Web 界面、命令行和纯前端三种方式。

## 环境准备

```bash
pip install flask requests qrcode gmssl
```

凭据配置（可选，不配置则在 Web 界面手动输入）：

在 `scu-second-class/` 下创建 `.env` 文件：

```
SCU_USERNAME=你的学号
SCU_PASSWORD=你的密码
```

## 方式 A：Web 版（推荐）

```bash
cd scu-second-class
python app.py
```

浏览器打开 `http://127.0.0.1:5000`：

1. 输入验证码 → 登录
2. 两个标签页：
   - **我的活动** — 已报名的，显示签到/签退状态、时间、地点
   - **全部活动** — 按时间 + 类型（德智体美劳）筛选，每页 25 条
3. 点击活动 → 生成签到/签退二维码

## 方式 B：命令行

```bash
cd scu-second-class
python main.py
# 或直接生成指定活动：
python main.py --id 活动ID
```

登录后选择 `[1] 我的活动` 或 `[2] 全部活动`，二维码保存到 `qrcodes/` 目录。

## 方式 C：纯前端

打开 `scu-second-class/index.html`，输入活动 ID 或 URL 直接生成二维码，无需登录。

## 认证说明

使用 SCU 统一认证（id.scu.edu.cn）登录，账号密码不会保存到服务器，仅用于获取二课平台 token。
