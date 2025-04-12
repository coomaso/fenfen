import json
import requests
import logging
from Crypto.Cipher import AES
import base64

# ===== 日志设置 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

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
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            logging.info("✅ 企业微信推送成功")
        else:
            logging.error(f"❌ 推送失败：{response.status_code} - {response.text}")
    except Exception as e:
        logging.exception("❌ 企业微信推送请求异常")

# ===== AES 解密函数（无填充，尾部补零） =====
def decrypt_no_padding(ciphertext_b64):
    key_str = "6875616E6779696E6875616E6779696E"
    key = key_str.encode("utf-8")
    iv = b"sskjKingFree5138"

    cipher = AES.new(key, AES.MODE_CBC, iv)
    raw = base64.b64decode(ciphertext_b64)
    decrypted = cipher.decrypt(raw)
    return decrypted.rstrip(b"\x00").decode("utf-8")

# ===== 格式化：诚信评分 =====
def format_integrity_score(data):
    company_name = data.get("cioName", "未知企业")
    score_items = data.get("cxdamxArray", [])

    content = f"#### 📋 {company_name} 信用情况通报\n\n"
    content += "**🏅 资质诚信评分：**\n"
    if not score_items:
        content += "- 暂无评分数据。\n"
    else:
        for item in score_items:
            content += (
                f"- 资质：{item['zzmx']}\n"
                f"  - 等级：{item['cxdj']}\n"
                f"  - 得分：{item['score']}（基础分: {item['csf']}，扣分: {item['kf']}，加分: {item['zxjf']}）\n"
            )
    return content

# ===== 格式化：良好行为 =====
def format_project_awards(data):
    awards = data.get("lhxwArray", [])
    content = "\n**🏆 良好行为汇总：**\n"
    if not awards:
        content += "- 暂无良好行为信息。\n"
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

# ===== 格式化：不良行为 =====
def format_bad_behaviors(data):
    bad_behaviors = data.get("blxwArray", [])
    content = "\n**⚠️ 不良行为记录（扣分项）：**\n"
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

    # === IP代理池 ===
    ip_pool = [
        "43.153.15.23", "43.153.8.210", "43.153.2.82", "43.153.5.109", "43.153.13.149",
        "43.153.12.107", "43.153.4.199", "43.153.9.80", "43.153.8.196", "43.153.10.210",
        "43.153.7.172", "43.153.11.118", "43.153.5.31", "43.153.2.235", "43.153.2.3"
    ]

    success = False
    for ip in ip_pool:
        proxy_str = f"http://{ip}:13001"
        proxies = {"http": proxy_str, "https": proxy_str}
        try:
            logging.info(f"🌐 尝试代理：{proxy_str}")
            res = requests.get(url, params=params, timeout=15, proxies=proxies)
            res.raise_for_status()
            res_json = res.json()
            success = True
            break
        except Exception as e:
            logging.warning(f"⚠️ 代理失败：{proxy_str}，原因：{e}")
            continue

    if not success:
        logging.error("❌ 所有代理尝试均失败")
    elif res_json.get("code") == "0" and res_json.get("data"):
        try:
            decrypted_text = decrypt_no_padding(res_json["data"])
            decrypted_data = json.loads(decrypted_text)["data"]

            integrity_md = format_integrity_score(decrypted_data)
            awards_md = format_project_awards(decrypted_data)
            bad_md = format_bad_behaviors(decrypted_data)

            full_md = integrity_md + awards_md + bad_md
            send_wexinqq_md(full_md)
        except Exception as e:
            logging.exception("❌ 数据处理异常")
    else:
        logging.error("❌ 接口响应失败或无有效数据")
