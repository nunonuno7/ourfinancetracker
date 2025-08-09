
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Test Resend email configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            'recipient',
            type=str,
            help='Email address to send test email to',
        )
        parser.add_argument(
            '--from',
            dest='from_email',
            type=str,
            help='From email address (optional)',
        )

    def handle(self, *args, **options):
        recipient = options['recipient']
        from_email = options.get('from_email') or settings.DEFAULT_FROM_EMAIL
        
        self.stdout.write('Testing Resend email configuration...')
        self.stdout.write(f'Backend: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'From: {from_email}')
        self.stdout.write(f'To: {recipient}')
        
        # Check if Resend is configured
        if hasattr(settings, 'ANYMAIL') and settings.ANYMAIL.get('RESEND_API_KEY'):
            self.stdout.write('✅ Resend API key configured')
        else:
            self.stdout.write(
                self.style.WARNING('⚠️  RESEND_API_KEY not found in environment')
            )
            return

        try:
            success = send_mail(
                subject='OurFinanceTracker - Resend Test',
                message='This is a test email sent via Resend API. If you received this, your email configuration is working properly!',
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Test email sent successfully to {recipient} via Resend')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to send email to {recipient}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Email sending failed: {str(e)}')
            )
