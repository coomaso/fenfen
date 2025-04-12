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
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84124f9b-f26f-4a0f-b9d8-6661cfa47abf")
    AES_KEY = os.getenv("AES_KEY", "6875616E6779696E6875616E6779696E").encode("utf-8")
    AES_IV = os.getenv("AES_IV", "sskjKingFree5138").encode("utf-8")
    API_URL = os.getenv("API_URL", "http://106.15.60.27:22222/ycdc/bakCmisYcOrgan/getCurrentIntegrityDetails")
    CEC_ID = os.getenv("CEC_ID", "4028e4ef4d5b0ad4014d5b1aa1f001ae")
    ALERT_DAYS_NEW = int(os.getenv("ALERT_DAYS_NEW", 3))
    ALERT_DAYS_EXPIRE = int(os.getenv("ALERT_DAYS_EXPIRE", 30))

# ========== 企业微信推送函数 ==========
def send_wechat_markdown(content: str) -> bool:
    """发送企业微信Markdown消息"""
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content}
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(
            Config.WEBHOOK_URL,
            data=json.dumps(payload, ensure_ascii=False),
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"推送请求失败: {str(e)}")
        return False

# ========== AES解密函数 ==========
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

# ========== 信用报告生成器 ==========
class CreditReportGenerator:
    @staticmethod
    def format_integrity_scores(data: Dict) -> str:
        """格式化诚信评分"""
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
        """格式化良好行为"""
        awards = data.get("lhxwArray", [])
        content = ["", "**🏆 良好行为汇总：**"]
        
        if not awards:
            content.append("- 暂无良好行为记录")
        else:
            for item in awards:
                content.extend([
                    f"- **项目**: {item.get('engName', '未知项目')}",
                    f"  - 奖项: {item.get('reason', '未知原因')}",
                    f"  - 等级: {item.get('bzXwlb', '未知等级')}",
                    f"  - 有效期: {item.get('beginDate', '未知开始日期')} 至 {item.get('endDate', '未知结束日期')}",
                    f"  - 文号: {item.get('documentNumber', '无')}"
                ])
        
        return "\n".join(content)

    @staticmethod
    def format_bad_behaviors(data: Dict) -> str:
        """格式化不良行为"""
        bad_behaviors = data.get("blxwArray", [])
        content = ["", "**⚠️ 不良行为记录：**"]
        
        if not bad_behaviors:
            content.append("- 无不良行为记录")
        else:
            for i, item in enumerate(bad_behaviors, 1):
                score = abs(item.get("tbValue", 0))
                score_str = f"**{score} 分**" if score >= 1 else f"{score} 分"
                content.extend([
                    f"\n{i}. **项目**：{item.get('engName', '未知项目')}",
                    f"   - 事由：{item.get('reason', '未知原因')}",
                    f"   - 类别：{item.get('bzXwlb', '未知类别')}",
                    f"   - 扣分值：{score_str}",
                    f"   - 扣分编号：{item.get('kftzsbh', '无')}",
                    f"   - 扣分人员：{item.get('cfry', '—')}（证号：{item.get('cfryCertNum', '—')}）",
                    f"   - 有效期：{item.get('beginDate', '未知开始日期')} 至 {item.get('endDate', '未知结束日期')}"
                ])
        
        return "\n".join(content)

    @classmethod
    def generate_full_report(cls, data: Dict) -> str:
        """生成完整信用报告"""
        report_parts = [
            cls.format_integrity_scores(data),
            cls.format_project_awards(data),
            cls.format_bad_behaviors(data)
        ]
        return "\n".join(report_parts)

# ========== 提醒管理器 ==========
class AlertManager:
    DATE_FORMAT = "%Y-%m-%d"
    
    @classmethod
    def check_alerts(cls, data: Dict) -> List[str]:
        """检查新增和即将过期的事项"""
        alerts = []
        now = datetime.now()
        
        # 检查良好行为
        alerts.extend(cls._check_awards(data.get("lhxwArray", []), now))
        
        # 检查不良行为
        alerts.extend(cls._check_penalties(data.get("blxwArray", []), now))
        
        return alerts

    @classmethod
    def _check_awards(cls, items: List[Dict], now: datetime) -> List[str]:
        alerts = []
        for item in items:
            try:
                begin_date = datetime.strptime(item.get("beginDate", ""), cls.DATE_FORMAT)
                end_date = datetime.strptime(item.get("endDate", ""), cls.DATE_FORMAT)
                
                if begin_date >= now - timedelta(days=Config.ALERT_DAYS_NEW):
                    alerts.append(
                        f"🎉 新增良好：**{item.get('reason', '未知良好')}** "
                        f"（项目：{item.get('engName', '未知项目')}）"
                    )
                
                if end_date <= now + timedelta(days=Config.ALERT_DAYS_EXPIRE):
                    alerts.append(
                        f"📌 良好即将过期：**{item.get('reason', '未知良好')}**，"
                        f"到期日：{item.get('endDate')}"
                    )
            except ValueError:
                continue
        return alerts

    @classmethod
    def _check_penalties(cls, items: List[Dict], now: datetime) -> List[str]:
        alerts = []
        for item in items:
            try:
                begin_date = datetime.strptime(item.get("beginDate", ""), cls.DATE_FORMAT)
                end_date = datetime.strptime(item.get("endDate", ""), cls.DATE_FORMAT)
                score = abs(item.get("tbValue", 0))
                
                if begin_date >= now - timedelta(days=Config.ALERT_DAYS_NEW):
                    alerts.append(
                        f"⚠️ 新增处罚：**{item.get('reason', '未知事由')}** "
                        f"（项目：{item.get('engName', '未知项目')}，扣分：{score}）"
                    )
                
                if end_date <= now + timedelta(days=Config.ALERT_DAYS_EXPIRE):
                    alerts.append(
                        f"⌛ 处罚即将过期：**{item.get('reason', '未知事由')}**，"
                        f"到期日：{item.get('endDate')}"
                    )
            except ValueError:
                continue
        return alerts

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
            error_msg = raw_data.get("msg", "未知错误") or "无错误信息"
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
        data = decrypted_data.get("data", {})
        if not data:
            logging.error("解密数据中缺失'data'字段")
            logging.debug(f"完整解密数据: {json.dumps(decrypted_data, ensure_ascii=False, indent=2)}")
            return
        
        # 5. 生成提醒和报告
        alerts = AlertManager.check_alerts(data)
        alerts_md = "\n".join([f"- {alert}" for alert in alerts]) if alerts else ""
        
        # 生成完整报告
        report = "\n".join([
            f"### 🚨 异常提醒（近{Config.ALERT_DAYS_NEW}天新增 / {Config.ALERT_DAYS_EXPIRE}天内到期）\n{alerts_md}\n" if alerts else "",
            CreditReportGenerator.generate_full_report(data)
        ])
        
        logging.info("生成的报告内容:\n" + report)
        
        # 6. 发送报告
        if send_wechat_markdown(report):
            logging.info("✅ 报告发送成功")
        else:
            logging.error("❌ 报告发送失败")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"请求失败: {str(e)}")
    except Exception as e:
        logging.exception(f"程序异常: {str(e)}")
if __name__ == "__main__":
    main()
