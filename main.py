import json
import requests
from Crypto.Cipher import AES
import base64

# ===== 企业微信 Markdown 推送函数 =====
def send_wexinqq_md(markdown_content):
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84124f9b-f26f-4a0f-b9d8-6661cfa47abf"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_content
        }
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        print("✅ 企业微信推送成功")
    else:
        print(f"❌ 推送失败：{response.status_code} - {response.text}")


# ===== AES 解密函数（无填充，尾部补零） =====
def decrypt_no_padding(ciphertext_b64):
    key_str = "6875616E6779696E6875616E6779696E"  # 32 字节 key
    key = key_str.encode("utf-8")
    iv = b"sskjKingFree5138"  # 16 字节 IV

    cipher = AES.new(key, AES.MODE_CBC, iv)
    raw = base64.b64decode(ciphertext_b64)
    decrypted = cipher.decrypt(raw)
    return decrypted.rstrip(b"\x00").decode("utf-8")


# ===== 格式化：企业信用通报（评分 + 获奖 + 不良） =====
def format_full_summary(data):
    company_name = data.get("cioName", "未知企业")
    score_items = data.get("cxdamxArray", [])
    awards = data.get("lhxwArray", [])
    bad_behaviors = data.get("blxwArray", [])

    content = f"#### 📋 {company_name} 信用情况通报\n"

    # --- 1. 资质诚信评分 ---
    content += "\n**🏅 资质诚信评分：**\n"
    if not score_items:
        content += "- 暂无评分数据。\n"
    else:
        for item in score_items:
            content += (
                f"- 资质：{item['zzmx']}\n"
                f"  - 等级：{item['cxdj']}\n"
                f"  - 得分：{item['score']}（基础分: {item['csf']}，扣分: {item['kf']}，加分: {item['zxjf']}）\n"
            )

    # --- 2. 项目获奖情况 ---
    content += "\n**🏆 良好行为记录（加分项）：**\n"
    if not awards:
        content += "- 暂无良好行为数据。\n"
    else:
        for item in awards:
            content += (
                f"- **项目**：{item['engName']}\n"
                f"  - 奖项：{item['reason']}\n"
                f"  - 等级：{item['bzXwlb']}\n"
                f"  - 有效期：{item['beginDate']} 至 {item['endDate']}\n"
                f"  - 文号：{item.get('documentNumber', '无')}\n\n"
            )

    # --- 3. 不良行为记录 ---
    content += "\n**⚠️ 不良行为记录（扣分项）：**\n"
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


# ===== 主程序入口 =====
if __name__ == "__main__":
    url = "https://www.ycjsjg.net/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails"
    params = {"cecId": "4028e4ef4d5b0ad4014d5b1aa1f001ae"}
    res = requests.get(url, params=params).json()

    if res.get("code") == "0" and res.get("data"):
        decrypted_text = decrypt_no_padding(res["data"])
        decrypted_data = json.loads(decrypted_text)
        markdown_report = format_full_summary(decrypted_data["data"])
        send_wexinqq_md(markdown_report)
    else:
        print("❌ 接口请求失败或无数据")
