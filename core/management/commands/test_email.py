
"""
Management command to test email configuration
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Test email configuration by sending a test email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            help='Email address to send test email to',
        )

    def handle(self, *args, **options):
        recipient = options.get('to')
        
        if not recipient:
            self.stdout.write(
                self.style.ERROR('Please provide a recipient email address using --to')
            )
            return

        try:
            self.stdout.write('Testing email configuration...')
            self.stdout.write(f'Host: {settings.EMAIL_HOST}')
            self.stdout.write(f'Port: {settings.EMAIL_PORT}')
            self.stdout.write(f'Use SSL: {settings.EMAIL_USE_SSL}')
            self.stdout.write(f'From: {settings.DEFAULT_FROM_EMAIL}')
            self.stdout.write(f'To: {recipient}')

            success = send_mail(
                subject='OurFinanceTracker Email Test',
                message='This is a test email from your OurFinanceTracker application. If you received this, your email configuration is working properly!',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Test email sent successfully to {recipient}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to send test email')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error sending test email: {str(e)}')
            )
