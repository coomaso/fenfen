import json
import os
import requests
import base64
import logging
from datetime import datetime
from Crypto.Cipher import AES
from typing import Optional, Dict, Any

# ========== 配置参数 ==========
class Config:
    WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=9b81f009-c046-4812-8690-76763d6b1abd"
    AES_KEY = os.getenv("AES_KEY", "6875616E6779696E6875616E6779696E").encode("utf-8")
    AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
    API_URL = os.getenv("API_URL", "http://106.15.60.27:22222/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails")
    CEC_ID = os.getenv("CEC_ID", "4028e4ef4d5b0ad4014d5b1aa1f001ae")
    LOCAL_DATA_PATH = "company_old_data.json"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def generate_signature(item: Dict[str, Any]) -> tuple:
    """生成唯一标识签名（用于比较记录）"""
    return (
        item.get('engName', ''),
        item.get('reason', ''),
        item.get('beginDate', ''),
        item.get('documentNumber', '')
    )

def compare_records(old_list: list, new_list: list) -> tuple:
    """比较两个记录列表，返回新增和过期记录"""
    old_set = {generate_signature(item) for item in old_list}
    new_set = {generate_signature(item) for item in new_list}
    
    added = [item for item in new_list if generate_signature(item) not in old_set]
    expired = [item for item in old_list if generate_signature(item) not in new_set]
    
    return added, expired

def format_records(records: list, record_type: str) -> str:
    """格式化记录列表为Markdown文本"""
    if not records:
        return ""
    
    text = f"**{record_type}**（共{len(records)}条）:\n"
    for i, item in enumerate(records, 1):
        text += (
            f"{i}. `{item.get('engName', '')}`\n"
            f"- 原因：{item.get('reason', '')}\n"
            f"- 文号：{item.get('documentNumber', '')}\n"
            f"- 日期：{item.get('beginDate', '')} → {item.get('endDate', '')}\n"
        )
    return text + "\n"

def send_wechat_notification(content: str) -> bool:
    """发送企业微信通知"""
    if not content:
        return False
        
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**盛荣集团信用记录异动通知**\n> 检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}"
        }
    }
    try:
        response = requests.post(Config.WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"企业微信通知发送失败: {e}")
        return False
      
def decrypt_data(encrypted_data: str) -> Optional[dict]:
    """解密AES加密的数据"""
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
    """加载本地存储的数据"""
    filepath = Config.LOCAL_DATA_PATH
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"加载本地数据失败: {e}")
        return {}

def save_local_data(data: dict):
    """保存数据到本地文件"""
    filepath = Config.LOCAL_DATA_PATH
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info("本地数据已更新")
    except Exception as e:
        logging.error(f"保存本地数据失败: {e}")

def fetch_new_data() -> Optional[dict]:
    """从API获取新数据"""
    try:
        logging.info("请求接口数据...")
        response = requests.get(
            f"{Config.API_URL}?cecId={Config.CEC_ID}", 
            timeout=30
        )
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

def main():
    # 1. 加载本地旧数据
    old_data = load_local_data()
    logging.info(f"加载本地数据: {len(old_data.get('lhxwArray', []))}条良好记录")
    
    # 2. 获取新数据
    new_data = fetch_new_data()
    if not new_data:
        logging.error("未获取到新数据，终止处理")
        return
        
    logging.info(f"获取新数据: {len(new_data.get('lhxwArray', []))}条良好记录")
    
    # 3. 比较数据变化
    content = ""
    
    # 比较良好记录
    old_lhxw = old_data.get('lhxwArray', [])
    new_lhxw = new_data.get('lhxwArray', [])
    lhxw_added, lhxw_expired = compare_records(old_lhxw, new_lhxw)
    
    # 比较处罚记录
    old_blxw = old_data.get('blxwArray', [])
    new_blxw = new_data.get('blxwArray', [])
    blxw_added, blxw_expired = compare_records(old_blxw, new_blxw)
    
    # 构建通知内容
    if lhxw_added:
        content += "🎉 **新增良好记录**\n" + format_records(lhxw_added, "新增良好")
    if lhxw_expired:
        content += "📌 **良好记录过期**\n" + format_records(lhxw_expired, "过期良好")
    if blxw_added:
        content += "⚠️ **新增处罚记录**\n" + format_records(blxw_added, "新增处罚")
    if blxw_expired:
        content += "⌛ **处罚记录过期**\n" + format_records(blxw_expired, "过期处罚")
    
    # 4. 发送通知（如果有变更）
    if content:
        logging.info(f"检测到变更: {len(lhxw_added)}新增良好, {len(lhxw_expired)}过期良好, "
                    f"{len(blxw_added)}新增处罚, {len(blxw_expired)}过期处罚")
        
        success = send_wechat_notification(content)
        if success:
            logging.info("企业微信通知发送成功")
        else:
            logging.warning("企业微信通知发送失败")
    else:
        logging.info("未检测到变更记录")
    
    # 5. 保存新数据到本地（无论是否有变更都保存）
    save_local_data(new_data)

if __name__ == "__main__":
    main()
