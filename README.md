# ⚡️ 95598 Data Fetcher

本项目用于自动获取国家电网（95598）的电费和用电量数据，并通过 MQTT 协议发布。支持数据持久化存储到 SQLite 数据库。

**核心功能：**
1. **自动抓取**：定时从国网获取每日用电量、电费余额、年度/月度统计数据。
2. **MQTT 发布**：将获取的数据发布到 MQTT Broker，方便对接各种智能家居平台或数据分析工具。
3. **数据持久化**：支持将历史数据保存到本地 SQLite 数据库。
4. **智能验证码识别**：内置本地神经网络模型，支持动态分辨率适配和滑动偏移微调，无需依赖外部 API。

## 数据指标

程序会发布以下数据到 MQTT：

| 数据项 | 说明 | 单位 |
| :--- | :--- | :--- |
| `balance` | 电费余额 | CNY |
| `last_daily_usage` | 最近一天用电量 | kWh |
| `yearly_usage` | 今年总用电量 | kWh |
| `yearly_charge` | 今年总电费 | CNY |
| `month_usage` | 最近一个月用电量 | kWh |
| `month_charge` | 上月总电费 | CNY |

## 运行模式

### 1. Docker Run

如果你熟悉 Docker，可以直接使用镜像运行，环境隔离更省心。

**运行容器：**

推荐使用 `.env` 文件管理配置：

```bash
docker run -d \
  --name 95598-mqtt \
  --restart unless-stopped \
  -v $(pwd)/data:/data \
  -v $(pwd)/errors:/app/errors \
  --env-file .env \
  ghcr.io/goxofy/95598-mqtt:main
```

### 2. Docker Compose

本项目提供了 `docker-compose.yml`，你可以直接使用 Compose 启动：

```bash
docker-compose up -d
```

### 3. 本地运行

如果你想在本地直接运行 Python 脚本：

**准备工作：**
1. 注册[国家电网账户](https://www.95598.cn/osgweb/login)，绑定户号。
2. 确保环境中有 Python 3.x。
3. 安装了 Google Chrome 浏览器。

**安装依赖：**

```bash
pip install -r requirements.txt
```

**配置环境变量：**

复制 `example.env` 为 `.env` 并修改配置：

```bash
cp example.env .env
```

**运行：**

```bash
python3 startup.py
```

## 集成说明

本项目原生支持 **Home Assistant MQTT Discovery**。

只要你的 Home Assistant 配置了 MQTT 集成，运行本项目后，上述数据实体会自动出现在 Home Assistant 中，无需任何手动配置。

对于其他平台，请订阅配置的 MQTT Topic 前缀（默认 `95598/`）获取数据。

## 环境变量说明

| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `PHONE_NUMBER` | 国网账号 | 必填 |
| `PASSWORD` | 国网密码 | 必填 |
| `MQTT_BROKER` | MQTT 服务器地址 | `localhost` |
| `MQTT_PORT` | MQTT 端口 | `1883` |
| `MQTT_USER` | MQTT 用户名 | (空) |
| `MQTT_PASSWORD` | MQTT 密码 | (空) |
| `JOB_START_TIME` | 每天定时运行时间 | `07:00` |
| `SLIDER_OFFSET` | 验证码滑块偏移微调，如果持续登录报错，考虑调整这个数值（-10 ~ 10） | `5` |
| `IGNORE_USER_ID` | 忽略的户号(逗号分隔) | (空) |
