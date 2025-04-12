import json
import requests
from Crypto.Cipher import AES
import base64
import logging

# ========== 日志配置 ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ========== 企业微信 Markdown 推送函数 ==========
def send_wexinqq_md(markdown_content):
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84124f9b-f26f-4a0f-b9d8-6661cfa47abf"
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_content
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            logging.info("✅ 企业微信推送成功")
        else:
            logging.error(f"❌ 推送失败：{response.status_code} - {response.text}")
    except Exception as e:
        logging.exception("❌ 推送异常：%s", e)

# ========== AES 解密函数（无填充，尾部补零） ==========
def decrypt_no_padding(ciphertext_b64):
    key_str = "6875616E6779696E6875616E6779696E"
    key = key_str.encode("utf-8")
    iv = b"sskjKingFree5138"
    cipher = AES.new(key, AES.MODE_CBC, iv)
    raw = base64.b64decode(ciphertext_b64)
    decrypted = cipher.decrypt(raw)
    return decrypted.rstrip(b"\x00").decode("utf-8")

# ========== 格式化：诚信评分 ==========
def format_integrity_scores(data):
    company_name = data.get("cioName", "未知企业")
    score_items = data.get("cxdamxArray", [])
    content = f"#### 📋 {company_name} 信用情况通报\n\n**🏅 资质诚信评分：**\n"
    if not score_items:
        content += "- 暂无评分记录\n"
    for item in score_items:
        content += (
            f"- 资质：{item['zzmx']}\n"
            f"  - 等级：{item['cxdj']}\n"
            f"  - 得分：{item['score']}（基础分: {item['csf']}，扣分: {item['kf']}，加分: {item['zxjf']}）\n"
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
                f"- **项目**: {item['engName']}\n"
                f"  - 奖项: {item['reason']}\n"
                f"  - 等级: {item['bzXwlb']}\n"
                f"  - 有效期: {item['beginDate']} 至 {item['endDate']}\n"
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
            score = item.get("tbValue", 0)
            score_str = f"**{score} 分**" if score >= 1 else f"{score} 分"
            content += (
                f"\n{i}. **项目**：{item['engName']}\n"
                f"   - 事由：{item['reason']}\n"
                f"   - 类别：{item['bzXwlb']}\n"
                f"   - 扣分值：{score_str}\n"
                f"   - 扣分编号：{item.get('kftzsbh', '无')}\n"
                f"   - 扣分人员：{item.get('cfry', '—')}（证号：{item.get('cfryCertNum', '—')}）\n"
                f"   - 有效期：{item['beginDate']} 至 {item['endDate']}\n"
            )
    return content

# ========== 主程序入口 ==========
if __name__ == "__main__":
    try:
        url = "https://www.ycjsjg.net/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails?cecId=4028e4ef4d5b0ad4014d5b1aa1f001ae"

        logging.info("请求接口数据中...")
        res = requests.get(url, timeout=60)
        res.raise_for_status()
        raw_json = res.json()

        if raw_json["code"] == "0" and raw_json["data"]:
            decrypted_text = decrypt_no_padding(raw_json["data"])
            decrypted_data = json.loads(decrypted_text)

            data = decrypted_data["data"]
            parts = [
                format_integrity_scores(data),
                format_project_awards(data),
                format_bad_behaviors(data),
            ]
            full_md = "\n".join(parts)
            send_wexinqq_md(full_md)
        else:
            logging.warning("❌ 接口返回异常或无数据")
    except Exception as e:
        logging.exception("❌ 主程序异常：%s", e)
