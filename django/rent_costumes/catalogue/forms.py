from django.contrib.auth.forms import AuthenticationForm

class CustomAuthForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['username'].widget.attrs.update({
            'placeholder': ' ',
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': ' ',
        })
