from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .bots import is_reserved_username

User = get_user_model()


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ["username", "email"]

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if is_reserved_username(username):
            raise forms.ValidationError(
                "Los nombres que empiezan con «IA-» son de la computadora.")
        qs = User.objects.filter(username__iexact=username, is_guest=False)
        if qs.exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
