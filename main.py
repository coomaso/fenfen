import json
import requests
from Crypto.Cipher import AES
import base64
import logging
import os
from datetime import datetime, timedelta

# ========== 日志配置 ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ========== 配置参数 ==========
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84124f9b-f26f-4a0f-b9d8-6661cfa47abf")
AES_KEY = os.getenv("AES_KEY", "6875616E6779696E6875616E6779696E").encode("utf-8")
AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
API_URL = os.getenv("API_URL", "http://106.15.60.27:22222/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails?cecId=4028e4ef4d5b0ad4014d5b1aa1f001ae")

# ========== 企业微信 Markdown 推送函数 ==========
def send_wexinqq_md(markdown_content):
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_content
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(WEBHOOK_URL, data=json.dumps(payload), headers=headers, timeout=10)
        response.raise_for_status()
        logging.info("✅ 企业微信推送成功")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ 推送请求失败：{e}")
    except Exception as e:
        logging.exception("❌ 推送异常")

# ========== AES 解密函数（无填充，尾部补零） ==========
def decrypt_no_padding(ciphertext_b64):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    raw = base64.b64decode(ciphertext_b64)
    decrypted = cipher.decrypt(raw)
    return decrypted.rstrip(b"\x00").decode("utf-8", errors="ignore")

# ========== 格式化：诚信评分 ==========
def format_integrity_scores(data):
    company_name = data.get("cioName", "未知企业")
    score_items = data.get("cxdamxArray", [])
    content = f"#### 📋 {company_name} 信用情况通报\n\n**🏅 资质诚信评分：**\n"
    if not score_items:
        content += "- 暂无评分记录\n"
    for item in score_items:
        content += (
            f"- 资质：{item.get('zzmx', '未知资质')}\n"
            f"  - 等级：{item.get('cxdj', '未知等级')}\n"
            f"  - 得分：{item.get('score', '无')}（基础分: {item.get('csf', '无')}，扣分: {item.get('kf', '无')}，加分: {item.get('zxjf', '无')}）\n"
        )
    return content

# ========== 格式化：良好行为 ==========
def format_project_awards(data):
    awards = data.get("lhxwArray", [])
    content = "\n**🏆 良好行为汇总：**\n"
    if not awards:
        content += "- 暂无良好行为记录。\n"
    else:
        for item in awards:
            content += (
                f"- **项目**: {item.get('engName', '未知项目')}\n"
                f"  - 奖项: {item.get('reason', '未知原因')}\n"
                f"  - 等级: {item.get('bzXwlb', '未知等级')}\n"
                f"  - 有效期: {item.get('beginDate', '未知开始日期')} 至 {item.get('endDate', '未知结束日期')}\n"
                f"  - 文号: {item.get('documentNumber', '无')}\n\n"
            )
    return content

# ========== 格式化：不良行为 ==========
def format_bad_behaviors(data):
    bad_behaviors = data.get("blxwArray", [])
    content = "\n**⚠️ 不良行为记录：**\n"
    if not bad_behaviors:
        content += "- 无不良行为记录。\n"
    else:
        for i, item in enumerate(bad_behaviors, 1):
            score = abs(item.get("tbValue", 0))
            score_str = f"**{score} 分**" if score >= 1 else f"{score} 分"
            content += (
                f"\n{i}. **项目**：{item.get('engName', '未知项目')}\n"
                f"   - 事由：{item.get('reason', '未知原因')}\n"
                f"   - 类别：{item.get('bzXwlb', '未知类别')}\n"
                f"   - 扣分值：{score_str}\n"
                f"   - 扣分编号：{item.get('kftzsbh', '无')}\n"
                f"   - 扣分人员：{item.get('cfry', '—')}（证号：{item.get('cfryCertNum', '—')}）\n"
                f"   - 有效期：{item.get('beginDate', '未知开始日期')} 至 {item.get('endDate', '未知结束日期')}\n"
            )
    return content

# ========== 提醒信息提取（新增或即将过期） ==========
def extract_alerts(data, days_new=3, days_expire=30):
    alerts = []
    now = datetime.now()
    date_fmt = "%Y-%m-%d"
    new_since = now - timedelta(days=days_new)
    expire_until = now + timedelta(days=days_expire)

    for item in data.get("lhxwArray", []):
        try:
            begin = datetime.strptime(item.get("beginDate", ""), date_fmt)
            end = datetime.strptime(item.get("endDate", ""), date_fmt)
            if begin >= new_since:
                alerts.append(f"🎉 新增奖励：**{item.get('reason', '未知奖励')}**（项目：{item.get('engName', '未知项目')}）")
            if end <= expire_until:
                alerts.append(f"📌 奖励即将过期：**{item.get('reason', '未知奖励')}**，到期日：{item.get('endDate')}")
        except Exception:
            continue

    for item in data.get("blxwArray", []):
        try:
            begin = datetime.strptime(item.get("beginDate", ""), date_fmt)
            end = datetime.strptime(item.get("endDate", ""), date_fmt)
            score = abs(item.get("tbValue", 0))
            if begin >= new_since:
                alerts.append(f"⚠️ 新增处罚：**{item.get('reason', '未知事由')}**（项目：{item.get('engName', '未知项目')}，扣分：{score}）")
            if end <= expire_until:
                alerts.append(f"⌛ 处罚即将过期：**{item.get('reason', '未知事由')}**，到期日：{item.get('endDate')}")
        except Exception:
            continue

    return alerts

# ========== 主程序入口 ==========
if __name__ == "__main__":
    try:
        logging.info("请求接口数据中...")
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        raw_json = response.json()

        if raw_json.get("code") != "0" or not raw_json.get("data"):
            logging.warning(f"❌ 接口返回异常或无数据: {raw_json.get('msg', '未知错误')}")
            exit()

        decrypted_text = decrypt_no_padding(raw_json["data"])
        try:
            decrypted_data = json.loads(decrypted_text)
        except json.JSONDecodeError as e:
            logging.error(f"❌ 解密内容JSON解析失败: {e}")
            exit()

        data = decrypted_data.get("data")
        if not data:
            logging.error("❌ 解密数据中缺失'data'字段")
            exit()

        alerts = extract_alerts(data)
        alerts_md = "\n".join([f"- {alert}" for alert in alerts])
        full_md = "\n".join([
            f"### 🚨 异常提醒（近3天新增 / 30天内到期）\n{alerts_md}\n" if alerts else "",
            format_integrity_scores(data),
            format_project_awards(data),
            format_bad_behaviors(data)
        ])
        send_wexinqq_md(full_md)

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ 请求失败: {e}")
    except Exception as e:
        logging.exception(f"❌ 主程序异常: {e}")
