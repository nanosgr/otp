import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def send_password_reset(
        self, to_email: str, username: str, reset_token: str
    ) -> None:
        """
        Compose and send a password-reset email containing a one-time link.
        Failures are logged but not re-raised so they do not surface to the caller.
        """
        reset_url = (
            f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        )
        expire_min = settings.RESET_TOKEN_EXPIRE_MINUTES

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Recuperación de contraseña"
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
        msg["To"] = to_email

        # Plain-text fallback
        text = (
            f"Hola {username},\n\n"
            f"Recibimos una solicitud para restablecer tu contraseña.\n\n"
            f"Ingresá al siguiente enlace para crear una nueva contraseña:\n{reset_url}\n\n"
            f"Este enlace expira en {expire_min} minutos y es de un solo uso.\n\n"
            f"Si no solicitaste este cambio, podés ignorar este correo con seguridad."
        )

        # HTML version
        html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;background:#f5f5f4;padding:32px">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;border:1px solid #e7e5e4;padding:32px">
    <div style="text-align:center;margin-bottom:24px">
      <div style="display:inline-flex;background:#1c1917;border-radius:10px;padding:10px">
        <span style="font-size:20px">&#128274;</span>
      </div>
      <h2 style="color:#1c1917;margin:12px 0 4px">Recuperación de contraseña</h2>
    </div>
    <p style="color:#57534e;font-size:14px">Hola <strong>{username}</strong>,</p>
    <p style="color:#57534e;font-size:14px">
      Recibimos una solicitud para restablecer la contraseña de tu cuenta.
    </p>
    <div style="text-align:center;margin:28px 0">
      <a href="{reset_url}"
         style="background:#1c1917;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600">
        Restablecer contraseña
      </a>
    </div>
    <p style="color:#78716c;font-size:13px">
      Este enlace expira en <strong>{expire_min} minutos</strong> y es de un solo uso.
    </p>
    <hr style="border:none;border-top:1px solid #e7e5e4;margin:24px 0">
    <p style="color:#a8a29e;font-size:12px">
      Si no solicitaste este cambio, podés ignorar este correo con seguridad.
    </p>
  </div>
</body>
</html>"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())
        except Exception:
            logger.exception(
                "Error enviando email de recuperación de contraseña a %s",
                to_email,
            )


email_service = EmailService()
