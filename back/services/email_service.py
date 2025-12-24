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
        "from_name": os.getenv("SMTP_FROM_NAME", "Crypto Daily Report")
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
    """Send subscription confirmation email - Multi-language"""
    
    if language == "zh":
        subject = "✅ 订阅成功 - Crypto Daily Report"
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 500px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; border: 1px solid #334155;">
                    <tr>
                        <td style="padding: 40px; text-align: center;">
                            <!-- Logo -->
                            <div style="font-size: 48px; margin-bottom: 20px;">📰</div>
                            
                            <!-- Title -->
                            <h1 style="color: #4ade80; font-size: 28px; margin: 0 0 16px 0;">
                                ✅ 订阅成功！
                            </h1>
                            
                            <!-- Message -->
                            <p style="color: #e2e8f0; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                您已成功订阅 <strong style="color: #818cf8;">Crypto Daily Report</strong>
                            </p>
                            
                            <!-- Info Box -->
                            <div style="background: #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                                <p style="color: #94a3b8; font-size: 14px; margin: 0 0 8px 0;">📧 订阅邮箱</p>
                                <p style="color: #f8fafc; font-size: 16px; margin: 0; word-break: break-all;">{to_email}</p>
                            </div>
                            
                            <div style="background: #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                                <p style="color: #94a3b8; font-size: 14px; margin: 0 0 8px 0;">⏰ 发送时间</p>
                                <p style="color: #f8fafc; font-size: 16px; margin: 0;">每日 UTC 0:05 (北京时间 8:05)</p>
                            </div>
                            
                            <!-- Footer -->
                            <p style="color: #64748b; font-size: 12px; margin: 24px 0 0 0;">
                                如需退订，请在日报邮件底部点击退订链接
                            </p>
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
        subject = "✅ Subscription Confirmed - Crypto Daily Report"
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 500px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; border: 1px solid #334155;">
                    <tr>
                        <td style="padding: 40px; text-align: center;">
                            <!-- Logo -->
                            <div style="font-size: 48px; margin-bottom: 20px;">📰</div>
                            
                            <!-- Title -->
                            <h1 style="color: #4ade80; font-size: 28px; margin: 0 0 16px 0;">
                                ✅ You're Subscribed!
                            </h1>
                            
                            <!-- Message -->
                            <p style="color: #e2e8f0; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                You've successfully subscribed to <strong style="color: #818cf8;">Crypto Daily Report</strong>
                            </p>
                            
                            <!-- Info Box -->
                            <div style="background: #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                                <p style="color: #94a3b8; font-size: 14px; margin: 0 0 8px 0;">📧 Subscribed Email</p>
                                <p style="color: #f8fafc; font-size: 16px; margin: 0; word-break: break-all;">{to_email}</p>
                            </div>
                            
                            <div style="background: #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                                <p style="color: #94a3b8; font-size: 14px; margin: 0 0 8px 0;">⏰ Delivery Time</p>
                                <p style="color: #f8fafc; font-size: 16px; margin: 0;">Daily at UTC 0:05</p>
                            </div>
                            
                            <!-- Footer -->
                            <p style="color: #64748b; font-size: 12px; margin: 24px 0 0 0;">
                                To unsubscribe, click the link at the bottom of any daily report email.
                            </p>
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
    """Send daily report email - Multi-language"""
    
    # Convert Markdown to HTML
    html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    
    if language == "zh":
        subject = f"📰 加密日报 - {report_date}"
        header_title = "📰 加密日报"
        footer_text = "您收到此邮件是因为您订阅了加密日报。"
        unsubscribe_text = "退订"
    else:
        subject = f"📰 Crypto Daily Report - {report_date}"
        header_title = "📰 Crypto Daily Report"
        footer_text = "You received this email because you subscribed to Crypto Daily Report."
        unsubscribe_text = "Unsubscribe"
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        .card {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 16px;
            border: 1px solid #334155;
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            padding: 32px;
            text-align: center;
        }}
        .header h1 {{
            color: #ffffff;
            font-size: 24px;
            margin: 0 0 8px 0;
        }}
        .header .date {{
            color: rgba(255,255,255,0.8);
            font-size: 14px;
        }}
        .content {{
            padding: 32px;
            color: #cbd5e1;
            line-height: 1.7;
        }}
        .content h2 {{
            color: #818cf8;
            font-size: 20px;
            margin-top: 28px;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #334155;
        }}
        .content h3 {{
            color: #a5b4fc;
            font-size: 16px;
            margin-top: 20px;
        }}
        .content p {{
            margin: 0 0 16px 0;
        }}
        .content ul {{
            margin: 0 0 16px 0;
            padding-left: 24px;
        }}
        .content li {{
            margin-bottom: 8px;
        }}
        .content strong {{
            color: #f8fafc;
        }}
        .positive {{ color: #4ade80; }}
        .negative {{ color: #f87171; }}
        .footer {{
            padding: 24px 32px;
            border-top: 1px solid #334155;
            text-align: center;
        }}
        .footer p {{
            color: #64748b;
            font-size: 12px;
            margin: 0 0 12px 0;
        }}
        .footer a {{
            color: #818cf8;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>{header_title}</h1>
                <div class="date">{report_date}</div>
            </div>
            <div class="content">
                {html_content}
            </div>
            <div class="footer">
                <p>{footer_text}</p>
                <a href="https://aigcog.com/api/unsubscribe/{unsubscribe_token}">{unsubscribe_text}</a>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    text_body = f"""
{header_title} - {report_date}
{'=' * 50}

{content}

---
{footer_text}
{unsubscribe_text}: https://aigcog.com/api/unsubscribe/{unsubscribe_token}
"""
    
    return send_email(to_email, subject, html_body, text_body)
