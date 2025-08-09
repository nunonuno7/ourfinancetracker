
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send a test email to verify SMTP configuration'

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
        
        self.stdout.write('Testing email configuration...')
        self.stdout.write(f'Host: {settings.EMAIL_HOST}')
        self.stdout.write(f'Port: {settings.EMAIL_PORT}')
        self.stdout.write(f'Use SSL: {settings.EMAIL_USE_SSL}')
        self.stdout.write(f'From: {from_email}')
        self.stdout.write(f'To: {recipient}')

        try:
            success = send_mail(
                subject='OurFinanceTracker Email Test',
                message='This is a test email from your OurFinanceTracker application. If you received this, your email configuration is working properly!',
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Test email sent successfully to {recipient}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to send email to {recipient}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Email sending failed: {str(e)}')
            )
