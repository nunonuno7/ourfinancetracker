from django.shortcuts import render, redirect
from .models import Transacao
from .forms import TransacaoForm

def lista_transacoes(request):
    transacoes = Transacao.objects.all().order_by('-data')
    return render(request, 'core/lista.html', {'transacoes': transacoes})

def nova_transacao(request):
    if request.method == 'POST':
        form = TransacaoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_transacoes')
    else:
        form = TransacaoForm()
    return render(request, 'core/form.html', {'form': form})
