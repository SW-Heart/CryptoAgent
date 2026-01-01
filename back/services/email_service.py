"""
Email Service - Send daily reports via Alibaba Cloud Enterprise Email
Supports multi-language templates (English and Chinese)
"""
import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try import markdown, provide fallback
try:
    import markdown
except ImportError:
    markdown = None


def get_smtp_config():
    """Get SMTP configuration from environment"""
    return {
        "host": os.getenv("SMTP_HOST", "smtp.qiye.aliyun.com"),
        "port": int(os.getenv("SMTP_PORT", "465")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_name": os.getenv("SMTP_FROM_NAME", "OG Agent")
    }


def send_email(to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Send an email using SMTP"""
    config = get_smtp_config()
    
    if not config["user"] or not config["password"]:
        print(f"[Email] SMTP not configured (SMTP_USER={config['user']})")
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((config["from_name"], config["user"]))
        msg["To"] = to_email
        
        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["host"], config["port"], context=context) as server:
            server.login(config["user"], config["password"])
            server.sendmail(config["user"], to_email, msg.as_string())
        
        print(f"[Email] Sent to {to_email}: {subject}")
        return True
        
    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_subscription_confirmation(to_email: str, language: str = "en") -> bool:
    """Send subscription confirmation email - Multi-language with white theme"""
    
    if language == "zh":
        subject = "✅ 订阅成功 - Alpha 情报局"
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 500px; background: #ffffff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #8b5cf6 100%); padding: 40px 32px; text-align: center; border-radius: 16px 16px 0 0;">
                            <div style="display: inline-block; background: rgba(255,255,255,0.15); border-radius: 12px; padding: 12px 20px; margin-bottom: 16px;">
                                <span style="font-size: 32px;">✅</span>
                            </div>
                            <h1 style="color: #ffffff; font-size: 24px; font-weight: 700; margin: 0 0 8px 0;">订阅成功！</h1>
                            <p style="color: rgba(255,255,255,0.9); font-size: 14px; margin: 0;">欢迎加入 Alpha 情报局</p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; text-align: center;">
                            <p style="color: #475569; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                您已成功订阅 <strong style="color: #4f46e5;">加密市场日报</strong>
                            </p>
                            
                            <!-- Info Box 1 -->
                            <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #e2e8f0;">
                                <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">📧 订阅邮箱</p>
                                <p style="color: #1e293b; font-size: 15px; font-weight: 600; margin: 0; word-break: break-all;">{to_email}</p>
                            </div>
                            
                            <!-- Info Box 2 -->
                            <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin-bottom: 24px; border: 1px solid #e2e8f0;">
                                <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">⏰ 发送时间</p>
                                <p style="color: #1e293b; font-size: 15px; font-weight: 600; margin: 0;">每日 UTC 0:05 (北京时间 8:05)</p>
                            </div>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px 32px 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #94a3b8; font-size: 12px; margin: 0;">如需退订，请在日报邮件底部点击退订链接</p>
                            <p style="color: #cbd5e1; font-size: 11px; margin: 16px 0 0 0;">由 AIGCOG 提供技术支持</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    else:
        subject = "✅ Subscription Confirmed - Alpha Intelligence"
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f8fafc;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 500px; background: #ffffff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #8b5cf6 100%); padding: 40px 32px; text-align: center; border-radius: 16px 16px 0 0;">
                            <div style="display: inline-block; background: rgba(255,255,255,0.15); border-radius: 12px; padding: 12px 20px; margin-bottom: 16px;">
                                <span style="font-size: 32px;">✅</span>
                            </div>
                            <h1 style="color: #ffffff; font-size: 24px; font-weight: 700; margin: 0 0 8px 0;">You're Subscribed!</h1>
                            <p style="color: rgba(255,255,255,0.9); font-size: 14px; margin: 0;">Welcome to Alpha Intelligence</p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; text-align: center;">
                            <p style="color: #475569; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                You've successfully subscribed to <strong style="color: #4f46e5;">Crypto Daily Brief</strong>
                            </p>
                            
                            <!-- Info Box 1 -->
                            <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #e2e8f0;">
                                <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">📧 Subscribed Email</p>
                                <p style="color: #1e293b; font-size: 15px; font-weight: 600; margin: 0; word-break: break-all;">{to_email}</p>
                            </div>
                            
                            <!-- Info Box 2 -->
                            <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin-bottom: 24px; border: 1px solid #e2e8f0;">
                                <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">⏰ Delivery Time</p>
                                <p style="color: #1e293b; font-size: 15px; font-weight: 600; margin: 0;">Daily at UTC 0:05</p>
                            </div>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px 32px 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #94a3b8; font-size: 12px; margin: 0;">To unsubscribe, click the link at the bottom of any daily report email.</p>
                            <p style="color: #cbd5e1; font-size: 11px; margin: 16px 0 0 0;">Powered by AIGCOG</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    return send_email(to_email, subject, html_body)


def send_daily_report_email(to_email: str, report_date: str, content: str, unsubscribe_token: str, language: str = "en") -> bool:
    """Send daily report email - Multi-language with white theme"""
    
    # Convert Markdown to HTML
    html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    
    if language == "zh":
        # Chinese - 中文模板
        subject = f"Alpha情报局 | 加密市场日报 [{report_date}]"
        header_title = "Alpha 情报局"
        header_subtitle = "加密市场日报"
        footer_text = "您收到此邮件是因为订阅了 Alpha 情报局日报推送服务。"
        unsubscribe_text = "取消订阅"
        powered_by = "由 AIGCOG 提供技术支持"
    else:
        # English template
        subject = f"Alpha Intelligence | Crypto Daily Brief [{report_date}]"
        header_title = "Alpha Intelligence"
        header_subtitle = "Crypto Daily Brief"
        footer_text = "You received this email because you subscribed to Alpha Intelligence daily reports."
        unsubscribe_text = "Unsubscribe"
        powered_by = "Powered by AIGCOG"
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f8fafc;color:#1e293b;line-height:1.6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:24px 16px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width:720px;background:#ffffff;border-radius:12px;">
                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#4f46e5 0%,#8b5cf6 100%);padding:24px 32px;text-align:center;border-radius:12px 12px 0 0;">
                            <h1 style="color:#ffffff;font-size:24px;font-weight:700;margin:0 0 4px 0;">{header_title}</h1>
                            <p style="color:rgba(255,255,255,0.9);font-size:14px;margin:0 0 8px 0;">{header_subtitle}</p>
                            <p style="color:rgba(255,255,255,0.7);font-size:13px;margin:0;">{report_date}</p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding:28px 32px;color:#334155;font-size:15px;line-height:1.8;">
                            {html_content}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding:20px 32px 28px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center;border-radius:0 0 12px 12px;">
                            <p style="color:#94a3b8;font-size:12px;margin:0 0 12px 0;">{footer_text}</p>
                            <a href="https://aigcog.com/api/unsubscribe/{unsubscribe_token}" style="color:#6366f1;font-size:12px;text-decoration:none;">{unsubscribe_text}</a>
                            <p style="color:#cbd5e1;font-size:11px;margin:12px 0 0 0;">{powered_by}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    text_body = f"""
{header_title} - {header_subtitle}
{report_date}
{'=' * 50}

{content}

---
{footer_text}
{unsubscribe_text}: https://aigcog.com/api/unsubscribe/{unsubscribe_token}

{powered_by}
"""
    
    return send_email(to_email, subject, html_body, text_body)
