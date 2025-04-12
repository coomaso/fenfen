import json
import requests
from Crypto.Cipher import AES
import base64
import logging
import os

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ========== 配置参数 ==========
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84124f9b-f26f-4a0f-b9d8-6661cfa47abf")
AES_KEY = bytes.fromhex(os.getenv("AES_KEY_HEX", "6875616E6779696E6875616E6779696E"))
AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
API_URL = os.getenv("API_URL", "http://106.15.60.27:6666/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails?cecId=4028e4ef4d5b0ad4014d5b1aa1f001ae")

# ========== 企业微信 Markdown 推送 ==========
def send_wechat_markdown(content):
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content}
    }
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("✅ 企业微信推送成功")
    except Exception as e:
        logging.error(f"❌ 企业微信推送失败: {e}")

# ========== AES 解密（无填充） ==========
def decrypt_no_padding(ciphertext_b64):
    try:
        raw = base64.b64decode(ciphertext_b64)
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted = cipher.decrypt(raw)
        return decrypted.rstrip(b"\x00").decode("utf-8", errors="ignore")
    except Exception as e:
        logging.error(f"❌ AES 解密失败: {e}")
        return None

# ========== 数据格式化 ==========
def format_integrity_scores(data):
    name = data.get("cioName", "未知企业")
    items = data.get("cxdamxArray", [])
    lines = [f"#### 📋 {name} 信用情况通报", "\n**🏅 资质诚信评分：**"]
    if not items:
        lines.append("- 暂无评分记录")
    for item in items:
        lines.append(
            f"- 资质：{item.get('zzmx', '未知资质')}\n"
            f"  - 等级：{item.get('cxdj', '未知等级')}\n"
            f"  - 得分：{item.get('score', '无')}（基础分: {item.get('csf', '无')}，扣分: {item.get('kf', '无')}，加分: {item.get('zxjf', '无')}）"
        )
    return "\n".join(lines)

def format_project_awards(data):
    awards = data.get("lhxwArray", [])
    lines = ["\n**🏆 良好行为汇总：**"]
    if not awards:
        lines.append("- 暂无良好行为记录。")
    for item in awards:
        lines.append(
            f"- **项目**: {item.get('engName', '未知项目')}\n"
            f"  - 奖项: {item.get('reason', '未知原因')}\n"
            f"  - 等级: {item.get('bzXwlb', '未知等级')}\n"
            f"  - 有效期: {item.get('beginDate', '未知')} 至 {item.get('endDate', '未知')}\n"
            f"  - 文号: {item.get('documentNumber', '无')}\n"
        )
    return "\n".join(lines)

def format_bad_behaviors(data):
    bads = data.get("blxwArray", [])
    lines = ["\n**⚠️ 不良行为记录：**"]
    if not bads:
        lines.append("- 无不良行为记录。")
    for i, item in enumerate(bads, 1):
        score = abs(item.get("tbValue", 0))
        score_str = f"**{score} 分**" if score >= 1 else f"{score} 分"
        lines.append(
            f"\n{i}. **项目**：{item.get('engName', '未知项目')}\n"
            f"   - 事由：{item.get('reason', '未知原因')}\n"
            f"   - 类别：{item.get('bzXwlb', '未知类别')}\n"
            f"   - 扣分值：{score_str}\n"
            f"   - 扣分编号：{item.get('kftzsbh', '无')}\n"
            f"   - 扣分人员：{item.get('cfry', '—')}（证号：{item.get('cfryCertNum', '—')}）\n"
            f"   - 有效期：{item.get('beginDate', '未知')} 至 {item.get('endDate', '未知')}"
        )
    return "\n".join(lines)

# ========== 主程序入口 ==========
def main():
    try:
        logging.info("📡 正在请求接口数据...")
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        raw_json = response.json()

        if raw_json.get("code") != "0" or not raw_json.get("data"):
            logging.warning(f"❌ 接口返回异常或无数据: {raw_json.get('msg', '未知错误')}")
            return

        decrypted_text = decrypt_no_padding(raw_json["data"])
        if not decrypted_text:
            logging.error("❌ 解密失败，终止处理。")
            return

        decrypted_data = json.loads(decrypted_text)
        core_data = decrypted_data.get("data")
        if not core_data:
            logging.error("❌ 解密数据中缺失 'data' 字段。")
            return

        markdown_msg = "\n".join([
            format_integrity_scores(core_data),
            format_project_awards(core_data),
            format_bad_behaviors(core_data)
        ])
        send_wechat_markdown(markdown_msg)

    except Exception as e:
        logging.exception(f"❌ 主程序异常: {e}")

if __name__ == "__main__":
    main()
