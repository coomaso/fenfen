import json
import requests
from Crypto.Cipher import AES
import base64
import logging
import os
from datetime import datetime, timedelta

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
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84124f9b-f26f-4a0f-b9d8-6661cfa47abf")
    AES_KEY = os.getenv("AES_KEY", "6875616E6779696E6875616E6779696E").encode("utf-8")
    AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
    API_URL = os.getenv("API_URL", "http://106.15.60.27:22222/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails")
    CEC_ID = os.getenv("CEC_ID", "4028e4ef4d5b0ad4014d5b1aa1f001ae")

# ========== 解密函数 ==========
def decrypt_data(encrypted_data: str) -> dict:
    """解密AES加密的数据"""
    try:
        cipher = AES.new(Config.AES_KEY, AES.MODE_CBC, Config.AES_IV)
        decrypted = cipher.decrypt(base64.b64decode(encrypted_data))
        decrypted_text = decrypted.rstrip(b"\x00").decode("utf-8", errors="ignore")
        return json.loads(decrypted_text)
    except Exception as e:
        logging.error(f"解密失败: {str(e)}")
        return {}

# ========== 数据格式化 ==========
def format_report(data: dict) -> str:
    """格式化信用报告"""
    if not data:
        return "❌ 无有效数据可展示"
    
    # 企业基本信息
    company_name = data.get("cioName", "未知企业")
    report = [f"#### 📋 {company_name} 信用情况通报"]
    
    # 诚信评分
    scores = data.get("cxdamxArray", [])
    report.append("\n**🏅 资质诚信评分：**")
    if not scores:
        report.append("- 暂无评分记录")
    for item in scores:
        report.append(
            f"- 资质：{item.get('zzmx', '未知资质')}\n"
            f"  - 等级：{item.get('cxdj', '未知等级')}\n"
            f"  - 得分：{item.get('score', '无')}（基础分: {item.get('csf', '无')}，扣分: {item.get('kf', '无')}，加分: {item.get('zxjf', '无')}）"
        )
    
    # 良好行为
    awards = data.get("lhxwArray", [])
    report.append("\n**🏆 良好行为汇总：**")
    if not awards:
        report.append("- 暂无良好行为记录")
    else:
        for item in awards:
            report.append(
                f"- **项目**: {item.get('engName', '未知项目')}\n"
                f"  - 奖项: {item.get('reason', '未知原因')}\n"
                f"  - 等级: {item.get('bzXwlb', '未知等级')}\n"
                f"  - 有效期: {item.get('beginDate', '未知开始日期')} 至 {item.get('endDate', '未知结束日期')}\n"
                f"  - 文号: {item.get('documentNumber', '无')}"
            )
    
    # 不良行为
    penalties = data.get("blxwArray", [])
    report.append("\n**⚠️ 不良行为记录：**")
    if not penalties:
        report.append("- 无不良行为记录")
    else:
        for i, item in enumerate(penalties, 1):
            score = abs(item.get("tbValue", 0))
            score_str = f"**{score} 分**" if score >= 1 else f"{score} 分"
            report.append(
                f"\n{i}. **项目**：{item.get('engName', '未知项目')}\n"
                f"   - 事由：{item.get('reason', '未知原因')}\n"
                f"   - 类别：{item.get('bzXwlb', '未知类别')}\n"
                f"   - 扣分值：{score_str}\n"
                f"   - 扣分编号：{item.get('kftzsbh', '无')}\n"
                f"   - 扣分人员：{item.get('cfry', '—')}（证号：{item.get('cfryCertNum', '—')}）\n"
                f"   - 有效期：{item.get('beginDate', '未知开始日期')} 至 {item.get('endDate', '未知结束日期')}"
            )
    
    return "\n".join(report)

# ========== 主程序 ==========
def main():
    try:
        # 1. 获取数据
        logging.info("请求接口数据...")
        api_url = f"{Config.API_URL}?cecId={Config.CEC_ID}"
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        
        raw_data = response.json()
        logging.info(f"接口原始数据: {json.dumps(raw_data, ensure_ascii=False, indent=2)}")
        
        # 2. 检查接口返回
        if raw_data.get("code") != "0":
            error_msg = raw_data.get("msg", "未知错误")
            logging.error(f"接口返回异常: {error_msg}")
            return
        
        encrypted_data = raw_data.get("data")
        if not encrypted_data:
            logging.error("接口返回数据为空")
            return
        
        # 3. 解密数据
        decrypted_data = decrypt_data(encrypted_data)
        if not decrypted_data:
            logging.error("解密后数据为空")
            return
        
        # 4. 提取有效数据
        actual_data = decrypted_data.get("data", {})
        if not actual_data:
            logging.error("解密数据中缺失'data'字段")
            logging.debug(f"完整解密数据: {json.dumps(decrypted_data, ensure_ascii=False, indent=2)}")
            return
        
        # 5. 生成并发送报告
        report = format_report(actual_data)
        logging.info("生成的报告内容:\n" + report)
        
        # 发送到企业微信
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": report}
        }
        response = requests.post(
            Config.WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        logging.info("✅ 报告发送成功")
        
    except requests.exceptions.RequestException as e:
        logging.error(f"请求失败: {str(e)}")
    except Exception as e:
        logging.exception(f"程序异常: {str(e)}")

if __name__ == "__main__":
    main()
