import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from app.core.config import settings

class EmailClient:
    def __init__(self):
        self.sender = settings.EMAIL_SENDER
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_USE_TLS
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """Send an email."""
        message = MIMEMultipart()
        message["From"] = self.sender
        message["To"] = to_email
        message["Subject"] = subject
        
        if cc:
            message["Cc"] = ", ".join(cc)
        if bcc:
            message["Bcc"] = ", ".join(bcc)
        
        message.attach(MIMEText(html_content, "html"))
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                if bcc:
                    recipients.extend(bcc)
                
                server.sendmail(self.sender, recipients, message.as_string())
                
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
    
    async def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str
    ) -> bool:
        """Send an email verification email."""
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        subject = "Verify your ChatWave account"
        
        html_content = f"""
        <html>
            <body>
                <h2>Welcome to ChatWave, {username}!</h2>
                <p>Thank you for registering. Please verify your email address by clicking the link below:</p>
                <p><a href="{verification_url}">Verify Email</a></p>
                <p>Or copy and paste this URL into your browser:</p>
                <p>{verification_url}</p>
                <p>This link will expire in {settings.VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</p>
                <p>If you did not register for a ChatWave account, please ignore this email.</p>
                <p>Best regards,<br>The ChatWave Team</p>
            </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, html_content)
    
    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """Send a password reset email."""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        subject = "Reset your ChatWave password"
        
        html_content = f"""
        <html>
            <body>
                <h2>Hello, {username}!</h2>
                <p>We received a request to reset your password. Click the link below to reset it:</p>
                <p><a href="{reset_url}">Reset Password</a></p>
                <p>Or copy and paste this URL into your browser:</p>
                <p>{reset_url}</p>
                <p>This link will expire in {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>
                <p>If you did not request a password reset, please ignore this email.</p>
                <p>Best regards,<br>The ChatWave Team</p>
            </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, html_content)

email_client = EmailClient()
