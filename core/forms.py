from django import forms
from .models import Transacao

class TransacaoForm(forms.ModelForm):
    class Meta:
        model = Transacao
        fields = ['descricao', 'valor', 'data']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
        }
