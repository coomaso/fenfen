import json
import requests
from Crypto.Cipher import AES
import base64
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("credit_monitor.log", encoding="utf-8")
    ]
)

# ========== 配置参数 ==========
class Config:
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d42183fc-fb71-4c25-a123-7a61fb83fad5")
    AES_KEY = os.getenv("AES_KEY", "6875616E6779696E6875616E6779696E").encode("utf-8")
    AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
    API_URL = os.getenv("API_URL", "http://106.15.60.27:22222/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails")
    CEC_ID = os.getenv("CEC_ID", "4028e4ef4d5b0ad4014d5b1aa1f001ae")
    ALERT_DAYS_NEW = int(os.getenv("ALERT_DAYS_NEW", 3))
    ALERT_DAYS_EXPIRE = int(os.getenv("ALERT_DAYS_EXPIRE", 30))
    MAX_MSG_BYTES = 4000
    LOCAL_DATA_PATH = "company_data.json"

# ========== 工具函数 ==========
def split_markdown_content(content: str, max_bytes: int = Config.MAX_MSG_BYTES) -> List[str]:
    parts = []
    lines = content.splitlines(keepends=True)
    current = ""
    for line in lines:
        if len((current + line).encode("utf-8")) > max_bytes:
            parts.append(current)
            current = line
        else:
            current += line
    if current:
        parts.append(current)
    return parts

def send_wechat_markdown(content: str) -> bool:
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(Config.WEBHOOK_URL, json=payload, headers=headers, timeout=10)
        logging.info(f"企业微信响应: {response.status_code} - {response.text}")
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"推送请求失败: {str(e)}")
        return False

def decrypt_data(encrypted_data: str) -> Optional[dict]:
    try:
        cipher = AES.new(Config.AES_KEY, AES.MODE_CBC, Config.AES_IV)
        raw = base64.b64decode(encrypted_data)
        decrypted = cipher.decrypt(raw)
        decrypted_text = decrypted.rstrip(b"\x00").decode("utf-8", errors="ignore")
        return json.loads(decrypted_text)
    except Exception as e:
        logging.error(f"解密失败: {str(e)}")
        return None

def load_data_locally(filepath: str = Config.LOCAL_DATA_PATH) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data_locally(data: dict, filepath: str = Config.LOCAL_DATA_PATH):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========== 报告生成 ==========
class CreditReportGenerator:
    @staticmethod
    def format_integrity_scores(data: Dict) -> str:
        company_name = data.get("cioName", "未知企业")
        score_items = data.get("cxdamxArray", [])
        content = [f"#### 📋 {company_name} 信用情况通报", "", "**🏅 资质诚信评分：**"]
        if not score_items:
            content.append("- 暂无评分记录")
        for item in score_items:
            content.extend([
                f"  - 资质：{item.get('zzmx', '未知资质')}",
                f"  - 等级：{item.get('cxdj', '未知等级')}",
                f"  - 得分：{item.get('score', '无')}（基础分: {item.get('csf', '无')}，扣分: {item.get('kf', '无')}，加分: {item.get('zxjf', '无')}）"
            ])
        return "\n".join(content)

    @staticmethod
    def format_project_awards(data: Dict) -> str:
        awards = data.get("lhxwArray", [])
        total_score = sum(float(item.get("realValue", 0)) for item in awards if item.get("realValue"))
        content = ["", f"**🏆 良好行为汇总（总加分：<font color='red'>**{total_score}**</font>）**"]
        
        if not awards:
            content.append("- 暂无良好行为记录")
        else:
            for idx, item in enumerate(awards):
                score_str = f"<font color='red'>**{item.get('realValue', '未知')} 分**</font>"
                content.extend([
                    f"  - **项目**: {item.get('engName', '未知项目')}",
                    f"  - 加分值: {score_str}",
                    f"  - 奖项: {item.get('reason', '未知原因')}",
                    f"  - 等级: {item.get('bzXwlb', '未知等级')}",
                    f"  - 有效期: {item.get('beginDate', '未知开始')} 至 {item.get('endDate', '未知结束')}",
                    f"  - 文号: {item.get('documentNumber', '无')}"
                ])
                if idx < len(awards) - 1:
                    content.append("\n")
        return "\n".join(content)



    @staticmethod
    def format_bad_behaviors(data: Dict) -> str:
        bad_behaviors = data.get("blxwArray", [])
        total_score = sum(abs(item.get("tbValue", 0)) for item in bad_behaviors if item.get("tbValue") is not None)
        content = ["", f"**⚠️ 不良行为记录（总扣分：<font color='green'>**{total_score}**</font>）**"]
        
        if not bad_behaviors:
            content.append("  - 无不良行为记录")
        else:
            for i, item in enumerate(bad_behaviors):
                score = abs(item.get("tbValue", 0))
                score_str = f"<font color='green'>**{score} 分**</font>"
                content.extend([
                    f"{i+1}. **项目**：{item.get('engName', '未知项目')}",
                    f"   - 事由：{item.get('reason', '未知原因')}",
                    f"   - 类别：{item.get('bzXwlb', '未知类别')}",
                    f"   - 扣分值：{score_str}",
                    f"   - 扣分编号：{item.get('kftzsbh', '无')}",
                    f"   - 扣分人员：{item.get('cfry', '—')}（证号：{item.get('cfryCertNum', '—')}）",
                    f"   - 有效期：{item.get('beginDate', '未知')} 至 {item.get('endDate', '未知')}"
                ])
                if i < len(bad_behaviors) - 1:
                    content.append("\n")
        return "\n".join(content)


    @classmethod
    def generate_full_report(cls, data: Dict) -> str:
        return "\n".join([
            cls.format_integrity_scores(data),
            cls.format_project_awards(data),
            cls.format_bad_behaviors(data)
        ])

# ========== 提醒机制 ==========
class AlertManager:
    DATE_FORMAT = "%Y-%m-%d"
    
    @classmethod
    def check_alerts(cls, data: Dict) -> List[str]:
        now = datetime.now()
        alerts = []
        alerts.extend(cls._check_awards(data.get("lhxwArray", []), now))
        alerts.extend(cls._check_penalties(data.get("blxwArray", []), now))
        return alerts

    @classmethod
    def _check_awards(cls, items: List[Dict], now: datetime) -> List[str]:
        alerts = []
        for item in items:
            try:
                begin = datetime.strptime(item.get("beginDate", ""), cls.DATE_FORMAT)
                end = datetime.strptime(item.get("endDate", ""), cls.DATE_FORMAT)
                if begin >= now - timedelta(days=Config.ALERT_DAYS_NEW):
                    alerts.append(f"🎉 新增良好：**{item.get('reason')}**（项目：{item.get('engName')}）")
                if end <= now + timedelta(days=Config.ALERT_DAYS_EXPIRE):
                    alerts.append(f"📌 良好即将过期：**{item.get('reason')}**，到期日：{item.get('endDate')}")
            except Exception:
                continue
        return alerts

    @classmethod
    def _check_penalties(cls, items: List[Dict], now: datetime) -> List[str]:
        alerts = []
        for item in items:
            try:
                begin = datetime.strptime(item.get("beginDate", ""), cls.DATE_FORMAT)
                end = datetime.strptime(item.get("endDate", ""), cls.DATE_FORMAT)
                score = abs(item.get("tbValue", 0))
                if begin >= now - timedelta(days=Config.ALERT_DAYS_NEW):
                    alerts.append(f"⚠️ 新增处罚：**{item.get('reason')}**（项目：{item.get('engName')}，扣分：{score}）")
                if end <= now + timedelta(days=Config.ALERT_DAYS_EXPIRE):
                    alerts.append(f"⌛ 处罚即将过期：**{item.get('reason')}**，到期日：{item.get('endDate')}")
            except Exception:
                continue
        return alerts

# ========== 数据对比 ==========
def get_diff_data(local_data: dict, new_data: dict) -> dict:
    diff_data = {}
    if local_data.get("cxdamxArray") != new_data.get("cxdamxArray"):
        diff_data["cxdamxArray"] = new_data.get("cxdamxArray", [])
    if local_data.get("lhxwArray") != new_data.get("lhxwArray"):
        diff_data["lhxwArray"] = new_data.get("lhxwArray", [])
    if local_data.get("blxwArray") != new_data.get("blxwArray"):
        diff_data["blxwArray"] = new_data.get("blxwArray", [])
    diff_data["cioName"] = new_data.get("cioName", "未知企业")
    return diff_data

# ========== 主程序 ==========
def main():
    try:
        logging.info("请求接口数据...")
        response = requests.get(f"{Config.API_URL}?cecId={Config.CEC_ID}", timeout=30)
        response.raise_for_status()

        raw_data = response.json()
        encrypted_data = raw_data.get("data")
        if not encrypted_data:
            logging.error("接口返回数据为空")
            return
        
        decrypted_data = decrypt_data(encrypted_data)
        if not decrypted_data:
            logging.error("解密后数据为空")
            return
        
        new_data = decrypted_data.get("data", {})
        if not new_data:
            logging.error("解密数据中缺失 'data' 字段")
            return

        local_data = load_data_locally()
        diff_data = get_diff_data(local_data, new_data)

        if diff_data:
            save_data_locally(new_data)

            alerts = AlertManager.check_alerts(new_data)
            if alerts:
                alert_report = (
                    f"#### 📋 {new_data.get('cioName', '企业')} 信用异常提醒\n\n"
                    f"### 🚨 异常提醒（近{Config.ALERT_DAYS_NEW}天新增 / {Config.ALERT_DAYS_EXPIRE}天内到期）\n"
                    + "\n".join(f"- {alert}" for alert in alerts)
                )
                send_wechat_markdown(alert_report)

            for report_func in [
                CreditReportGenerator.format_integrity_scores,
                CreditReportGenerator.format_project_awards,
                CreditReportGenerator.format_bad_behaviors,
            ]:
                report = report_func(new_data)
                for part in split_markdown_content(report):
                    send_wechat_markdown(part)

            logging.info("✅ 新数据报告发送完成")
        else:
            logging.info("📡 数据未变化，无需推送")
    except Exception as e:
        logging.exception(f"程序异常: {str(e)}")

if __name__ == "__main__":
    main()
