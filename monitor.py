import json
import os
import requests
import base64
import logging
from datetime import datetime
from Crypto.Cipher import AES
from typing import Optional, Dict, Any, List

# ========== 配置参数 ==========
class Config:
    WEBHOOK_URL = os.environ["QYWX_URL"]
    AES_KEY = os.getenv("AES_KEY", "6875616E6779696E6875616E6779696E").encode("utf-8")
    AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
    API_URL = os.getenv("API_URL", "http://106.15.60.27:22222/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails")
    CEC_ID = os.getenv("CEC_ID", "4028e4ef4d5b0ad4014d5b1aa1f001ae")
    LOCAL_DATA_PATH = "company_old_data.json"

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# ========== 工具函数 ==========
def generate_signature(item: Dict[str, Any]) -> tuple:
    return (
        item.get('engName', ''),
        item.get('reason', ''),
        item.get('beginDate', ''),
        item.get('documentNumber', '')
    )

def compare_records(old_list: list, new_list: list) -> tuple:
    old_set = {generate_signature(item) for item in old_list}
    new_set = {generate_signature(item) for item in new_list}
    added = [item for item in new_list if generate_signature(item) not in old_set]
    expired = [item for item in old_list if generate_signature(item) not in new_set]
    return added, expired

def format_records(records: List[Dict], record_type: str, max_display: int = 10) -> str:
    if not records:
        return ""

    icon_map = {
        "新增良好记录": "🎉",
        "良好记录过期": "📌",
        "新增处罚记录": "⚠️",
        "处罚记录过期": "⌛"
    }
    icon = icon_map.get(record_type, "🔹")
    lines = [f"### {icon} **{record_type}（{len(records)}条）**"]

    for i, item in enumerate(records[:max_display], 1):
        lines.append(
            f"{i}. `{item.get('engName', '')}`\n"
            f"   - 原因：{item.get('reason', '')}\n"
            f"   - 文号：{item.get('documentNumber', '无') or '无'}\n"
            f"   - 有效期：{item.get('beginDate', '')} → {item.get('endDate', '')}\n"
        )

    if len(records) > max_display:
        lines.append(f"> ...及其他 {len(records) - max_display} 条记录未展示")

    return "\n".join(lines) + "\n"

def send_wechat_notification(content: str) -> bool:
    if not content:
        return False

    summary = (
        "# 盛荣集团信用记录异动通知\n"
        f"> **检测时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    )
    footer = (
        "> 本通知由系统自动生成，如有疑问请联系情报部门\n"
    )
    full_content = summary + content + footer

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": full_content
        }
    }

    try:
        response = requests.post(Config.WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"企业微信通知发送失败: {e}")
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

def load_local_data() -> dict:
    try:
        if os.path.exists(Config.LOCAL_DATA_PATH):
            with open(Config.LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"加载本地数据失败: {e}")
        return {}

def save_local_data(data: dict):
    try:
        with open(Config.LOCAL_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info("本地数据已更新")
    except Exception as e:
        logging.error(f"保存本地数据失败: {e}")

def fetch_new_data() -> Optional[dict]:
    try:
        logging.info("请求接口数据...")
        response = requests.get(f"{Config.API_URL}?cecId={Config.CEC_ID}", timeout=30)
        response.raise_for_status()

        raw_data = response.json()
        encrypted_data = raw_data.get("data")
        if not encrypted_data:
            logging.error("接口返回数据为空")
            return None

        decrypted_data = decrypt_data(encrypted_data)
        if not decrypted_data:
            logging.error("解密后数据为空")
            return None

        return decrypted_data.get("data", {})
    except Exception as e:
        logging.error(f"获取新数据失败: {e}")
        return None

# ========== 主流程 ==========
def main():
    old_data = load_local_data()
    new_data = fetch_new_data()

    if not new_data:
        logging.error("未获取到新数据，终止处理")
        return

    # 比较数据
    old_lhxw = old_data.get("lhxwArray", [])
    new_lhxw = new_data.get("lhxwArray", [])
    lhxw_added, lhxw_expired = compare_records(old_lhxw, new_lhxw)

    old_blxw = old_data.get("blxwArray", [])
    new_blxw = new_data.get("blxwArray", [])
    blxw_added, blxw_expired = compare_records(old_blxw, new_blxw)

    # 构建变动通知内容
    content = ""
    if lhxw_added:
        content += format_records(lhxw_added, "新增良好记录")
    if lhxw_expired:
        content += format_records(lhxw_expired, "良好记录过期")
    if blxw_added:
        content += format_records(blxw_added, "新增处罚记录")
    if blxw_expired:
        content += format_records(blxw_expired, "处罚记录过期")

    # 添加摘要统计
    if content:
        summary = (
            "### 📊 **变更摘要**\n"
            f"- 🎉 新增良好记录：**{len(lhxw_added)}** 条\n"
            f"- 📌 良好记录过期：**{len(lhxw_expired)}** 条\n"
            f"- ⚠️ 新增处罚记录：**{len(blxw_added)}** 条\n"
            f"- ⌛ 处罚记录过期：**{len(blxw_expired)}** 条\n"
            "\n\n"
        )
        content = summary + content

        logging.info("检测到记录变更，准备推送通知...")
        success = send_wechat_notification(content)
        if success:
            logging.info("企业微信通知发送成功")
        else:
            logging.warning("企业微信通知发送失败")
    else:
        logging.info("未检测到任何记录变更")

    save_local_data(new_data)

if __name__ == "__main__":
    main()
