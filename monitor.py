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

def format_records(records: List[Dict], record_type: str, max_display: int = 10) -> str:
    """高颜值格式化记录列表为Markdown文本"""
    if not records:
        return ""
    
    # 根据记录类型选择图标和颜色
    if "良好" in record_type:
        if "新增" in record_type:
            icon = "🎉"
            color = "<font color='#52c41a'>"
        else:
            icon = "📌"
            color = "<font color='#faad14'>"
    else:
        if "新增" in record_type:
            icon = "⚠️"
            color = "<font color='#f5222d'>"
        else:
            icon = "⌛"
            color = "<font color='#bfbfbf'>"
    
    text = f"### {icon} {color}{record_type}</font>（<font color='#1890ff'>{len(records)}条</font>）\n"
    
    # 显示摘要统计
    text += f"> 最后一条更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    # 显示前10条详细记录
    for i, item in enumerate(records[:max_display], 1):
        doc_num = item.get('documentNumber', '').strip()
        if not doc_num:
            doc_num = "<font color='#bfbfbf'>无</font>"
        
        text += (
            f"<font color='#096dd9'>**{i}. {item.get('engName', '')}**</font>\n"
            f"- <font color='#595959'>原因：</font>{item.get('reason', '')}\n"
            f"- <font color='#595959'>文号：</font>{doc_num}\n"
            f"- <font color='#595959'>有效期：</font>{item.get('beginDate', '')} → {item.get('endDate', '')}\n"
        )
    
    # 添加分隔线
    text += "---\n"
    
    # 如果记录超过最大显示数量，添加提示
    if len(records) > max_display:
        more_count = len(records) - max_display
        text += f"<font color='#8c8c8c'>...及其他{more_count}条记录（完整列表请查看系统）</font>\n"
    
    return text + "\n"

def send_wechat_notification(content: str) -> bool:
    """发送企业微信通知"""
    if not content:
        return False
        
    # 添加标题和摘要
    summary = (
        "## <font color='#1890ff'>盛荣集团信用记录异动通知</font>\n"
        f"> **检测时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        "---\n\n"
    )
    
    # 添加结尾提示
    footer = (
        "\n---\n"
        "<font color='#8c8c8f'>"
        "🔔 提示：本通知由企业信用监控系统自动生成\n"
        "📞 如有疑问请联系情报部门"
        "</font>"
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
        content += format_records(lhxw_added, "新增良好记录")
    if lhxw_expired:
        content += format_records(lhxw_expired, "良好记录过期")
    if blxw_added:
        content += format_records(blxw_added, "新增处罚记录")
    if blxw_expired:
        content += format_records(blxw_expired, "处罚记录过期")
    
    # 4. 发送通知（如果有变更）
    if content:
        # 添加摘要统计
        summary = (
            "### 📊 变更摘要\n"
            f"- 🎉 新增良好: <font color='#52c41a'>{len(lhxw_added)}</font>条\n"
            f"- 📌 良好过期: <font color='#faad14'>{len(lhxw_expired)}</font>条\n"
            f"- ⚠️ 新增处罚: <font color='#f5222d'>{len(blxw_added)}</font>条\n"
            f"- ⌛ 处罚过期: <font color='#bfbfbf'>{len(blxw_expired)}</font>条\n"
            "---\n\n"
        )
        content = summary + content
        
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
