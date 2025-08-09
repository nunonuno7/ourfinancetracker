
"""
Email helper utilities for ourfinancetracker
"""

import logging
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

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
            
    except Exception as e:
        logger.error(f"Error sending email to {recipient_list}: {e}")
        if not fail_silently:
            raise
        return False


def send_account_activation_email(user, request):
    """
    Send account activation email to user.
    This is a placeholder for future implementation.
    """
    # TODO: Implement account activation functionality
    pass


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
    except Exception as e:
        logger.error(f"Email configuration test failed: {e}")
        return False
