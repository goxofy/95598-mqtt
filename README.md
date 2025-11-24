# ⚡️ SGCC Electricity Data Fetcher

## 简介

本项目用于自动获取国家电网（SGCC）的电费和用电量数据，并通过 MQTT 协议发布。支持数据持久化存储到 SQLite 数据库。

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

## 安装与配置

### 1. 准备工作

1. 注册[国家电网账户](https://www.95598.cn/osgweb/login)，绑定户号。
2. 确保环境中有 Python 3.x。

### 2. 克隆代码

```bash
git clone https://github.com/goxofy/95598-mqtt.git
cd 95598-mqtt
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `example.env` 为 `.env` 并修改配置：

```bash
cp example.env .env
```

`.env` 核心配置项：

```bash
# 国网账号密码
PHONE_NUMBER="你的账号"
PASSWORD="你的密码"

# MQTT 配置
MQTT_BROKER="localhost"
MQTT_PORT=1883
MQTT_USER="user"
MQTT_PASSWORD="password"

# 运行参数
JOB_START_TIME="07:00" # 每天执行时间
SLIDER_OFFSET=0        # 验证码滑块偏移量微调（像素）
```

### 4. 运行

```bash
python3 startup.py
```

## 集成说明

本项目原生支持 **Home Assistant MQTT Discovery**。

只要你的 Home Assistant 配置了 MQTT 集成，运行本项目后，上述数据实体会自动出现在 Home Assistant 中，无需任何手动配置。

对于其他平台，请订阅配置的 MQTT Topic 前缀（默认 `sgcc/`）获取数据。
