
"""
Email helper utilities for ourfinancetracker
"""

import logging
import smtplib
from django.conf import settings
from django.core.mail import BadHeaderError, send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.tokens import generate_activation_token, revoke_activation_token

logger = logging.getLogger(__name__)


def send_template_email(subject, template_name, context, recipient_list, 
                       from_email=None, fail_silently=False):
    """
    Send an email using a Django template.
    
    Args:
        subject (str): Email subject line
        template_name (str): Path to email template
        context (dict): Template context variables
        recipient_list (list): List of recipient email addresses
        from_email (str, optional): Sender email address
        fail_silently (bool): Whether to suppress exceptions
    
    Returns:
        bool: True if email was sent successfully
    """
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    try:
        # Render the email content from template
        email_content = render_to_string(template_name, context)
        
        # Send the email
        success = send_mail(
            subject=subject,
            message=email_content,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=fail_silently
        )
        
        if success:
            logger.info(f"Email sent successfully to {recipient_list}")
            return True
        else:
            logger.error(f"Failed to send email to {recipient_list}")
            return False
            
    except (smtplib.SMTPException, BadHeaderError) as e:
        logger.error(f"Error sending email to {recipient_list}: {e}")
        if not fail_silently:
            raise
        return False


def send_account_activation_email(user, request):
    """Send account activation email to ``user``.

    The email includes a unique activation link based on a token
    generated for the user. The link is built using ``request`` so it
    contains the correct domain and protocol.

    Args:
        user (django.contrib.auth.models.User): The user to activate.
        request (django.http.HttpRequest): Current request instance used
            to build the absolute activation URL.

    Returns:
        bool: ``True`` if the email was sent successfully, otherwise
        ``False``.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = generate_activation_token(user)
    activation_link = request.build_absolute_uri(
        reverse("accounts:activate", kwargs={"uidb64": uid, "token": token})
    )

    context = {"user": user, "activation_link": activation_link}

    try:
        send_mail(
            "Activate your account",
            render_to_string("accounts/emails/account_activation_email.txt", context),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info("Activation email sent to %s", user.email)
        return True
    except (smtplib.SMTPException, BadHeaderError) as exc:
        revoke_activation_token(user)
        logger.error("Failed to send activation email to %s: %s", user.email, exc)
        return False


def test_email_configuration():
    """
    Test email configuration by sending a test email.
    Returns True if successful, False otherwise.
    """
    try:
        from django.core.mail import mail_admins
        mail_admins(
            "Email Configuration Test",
            "This is a test email to verify SMTP configuration.",
            fail_silently=False
        )
        return True
    except (smtplib.SMTPException, BadHeaderError) as e:
        logger.error(f"Email configuration test failed: {e}")
        return False
