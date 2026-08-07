"""
Email service (Gmail SMTP).

WHY templates live in code, not a CMS: for an MVP with one recruiter org,
a CMS is overhead we don't need yet. Templates are plain functions
returning HTML — easy for you or an intern to edit without touching
the sending logic. If you outgrow this (multiple orgs wanting custom
branding), that's the trigger to move templates to the database, not before.

WHY every send is wrapped and logged, never allowed to raise into the
caller uncaught: an email failure must never block a scoring pipeline
or a webhook handler from completing its real job. A candidate not
getting an email is bad; a webhook handler crashing and losing an
interview transcript because Gmail had a blip is much worse.

WHY Gmail SMTP instead of Resend right now: Resend requires a verified
sending domain, which is blocked pending GoDaddy DNS access. Gmail SMTP
works immediately with no domain verification. This is a stopgap for
low-volume sending (caps around 500/day) — switch back to Resend once
the domain is verified; that swap only touches this one file.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _send(to: str, subject: str, html: str, *, context: dict) -> bool:
    """Returns True on success, False on failure — never raises."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.GMAIL_ADDRESS
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_ADDRESS, [to], msg.as_string())

        logger.info("email_sent", to=to, subject=subject, **context)
        return True
    except Exception as exc:
        logger.error("email_send_failed", to=to, subject=subject, error=str(exc), **context)
        return False


def send_interview_invite(
    *, to_email: str, candidate_name: str, job_title: str, company_name: str, interview_url: str
) -> bool:
    # Subject line follows researched best practice: role + company + purpose,
    # kept short enough to display fully on mobile inboxes.
    subject = f"Interview Invitation: {job_title} at {company_name}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #1a1a1a;">
      <h2 style="margin-bottom: 4px;">You've been shortlisted!</h2>
      <p>Hi {candidate_name},</p>
      <p>
        Thank you for your interest in the <strong>{job_title}</strong> position at <strong>{company_name}</strong>
        After reviewing your application, we would like to invite you to the next stage of our hiring process.  
        As part of this initial screening, you'll complete a 10–15 minute AI interview. 
        This interview is designed to help us better understand your background, experience, communication skills, and overall suitability for the role. 
        You may complete the interview at your convenience before the interview link expires.
      </p>

      <p><strong>Before you begin, please ensure you have:</strong></p>
      <ul>
        <li>A quiet environment with minimal distractions</li>
        <li>A device with a working camera and microphone</li>
        <li>A stable internet connection</li>
        <li>About 15 uninterrupted minutes</li>
      </ul>

      <p style="margin: 24px 0;">
        <a href="{interview_url}"
           style="background:#5B5FEF; color:#fff; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:600;">
          Start Your Interview
        </a>
      </p>
      <p style="color:#666; font-size:13px;"> 
        This link is unique to you and expires in 5 days &mdash;  please don't share it. 
        The application window for this position is closing soon, so please complete your AI interview at the earliest. 
        If you face any issues reply to this email.
      </p>
    </div>
    """
    return _send(to_email, subject, html, context={"template": "interview_invite"})


def send_interview_followup(
    *, to_email: str, candidate_name: str, job_title: str, company_name: str
) -> bool:
    subject = f"Thanks for interviewing for {job_title}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #1a1a1a;">
      <h2 style="margin-bottom: 4px;">Interview complete</h2>
      <p>Hi {candidate_name},</p>
      <p>
        Thanks for completing your interview for the <strong>{job_title}</strong> role
        at {company_name}. Our team is reviewing your application, and we will be in touch with you regarding the next steps soon.
      </p>
      <p>We appreciate the time you took to speak with us.</p>
    </div>
    """
    return _send(to_email, subject, html, context={"template": "interview_followup"})