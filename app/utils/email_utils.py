from fastapi_mail import FastMail, MessageSchema
from app.core.config import conf, settings

fm = FastMail(conf)

def get_html_layout(title: str, content: str, button_text: str = None, button_url: str = None) -> str:
    """
    Generates a professional, responsive HTML email layout.
    """
    button_html = f"""
        <tr>
            <td align="center" style="padding: 30px 0;">
                <a href="{button_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                    {button_text}
                </a>
            </td>
        </tr>
    """ if button_text and button_url else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #374151; margin: 0; padding: 0; background-color: #f9fafb; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            .header {{ background-color: #4f46e5; padding: 30px; text-align: center; color: #ffffff; }}
            .content {{ padding: 40px; }}
            .footer {{ background-color: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
            h1 {{ margin: 0; font-size: 24px; font-weight: 700; }}
            p {{ margin: 16px 0; }}
            .otp-box {{ background-color: #f3f4f6; padding: 20px; border-radius: 8px; text-align: center; font-size: 32px; font-weight: 800; letter-spacing: 4px; color: #111827; margin: 24px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{settings.APP_NAME}</h1>
            </div>
            <div class="content">
                <h2 style="color: #111827; margin-top: 0;">{title}</h2>
                {content}
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    {button_html}
                </table>
                <p style="font-size: 14px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
                    If you did not request this email, please ignore it or contact our support if you have concerns.
                </p>
            </div>
            <div class="footer">
                &copy; {settings.APP_NAME}. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

async def send_account_email(background_tasks, to_email: str, subject: str, content_html: str):
    """
    Sends an email asynchronously using FastMail + BackgroundTasks.
    """
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=content_html,
        subtype="html"
    )
    background_tasks.add_task(fm.send_message, message)
