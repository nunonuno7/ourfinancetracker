from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password


class SignupForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        return self.cleaned_data["username"].strip()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_password(self):
        password = self.cleaned_data["password"]
        user_model = get_user_model()
        temp_user = user_model(username=self.cleaned_data.get("username", ""))
        # The user instance is not saved to the database
        validate_password(password, user=temp_user)
        return password
