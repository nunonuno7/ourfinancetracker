from nbformat import v4, writes
from pathlib import Path

# Células melhor formatadas e com visual mais bonito
cells = [
    v4.new_markdown_cell("# 📺 ROADMAP DO PROJETO WEB (DJANGO + POSTGRESQL)"),
    v4.new_markdown_cell("---"),

    v4.new_markdown_cell("## 🧭 FASE 1: Planeamento e Ferramentas\n"
                         "Nesta fase foi feita a preparação do ambiente de trabalho e ferramentas essenciais para o desenvolvimento."),
    v4.new_markdown_cell("### ✅ Ações\n"
                         "| Etapa | Ação |\n"
                         "|-------|------|\n"
                         "| 1.1 | Definir nome e domínio: `ourfinancetracker.com` |\n"
                         "| 1.2 | Comprar domínio |\n"
                         "| 1.3 | Instalar Python, Git, VS Code, PostgreSQL (Supabase) |\n"
                         "| 1.4 | Instalar extensões VS Code |\n"
                         "| 1.5 | Configurar Git e GitHub |"),
    v4.new_markdown_cell("---"),

    v4.new_markdown_cell("## 🛠️ FASE 2: Desenvolvimento Local (Django)\n"
                         "Ambiente de desenvolvimento criado com virtualenv, projeto Django configurado, app principal registada e ligada a base de dados externa."),
    v4.new_markdown_cell("### ✅ Etapas detalhadas\n"
                         "| Etapa | Ação |\n"
                         "|-------|------|\n"
                         "| 2.1 | Criar pasta do projeto em: `C:/Users/nunov/OneDrive/Ambiente de Trabalho/Python/ourfinancetracker` |\n"
                         "| 2.2 | Criar ambiente virtual:\n`python -m venv ourfinancetracker` |\n"
                         "| 2.3 | Ativar ambiente no Git Bash:\n`source ourfinancetracker/Scripts/activate` |\n"
                         "| 2.4 | Instalar pacotes com `pip install django psycopg2 python-dotenv gunicorn` |\n"
                         "| 2.5 | Criar projeto Django:\n`django-admin startproject ourfinancetracker_site .` |\n"
                         "| 2.6 | Verificar funcionamento do servidor:\n`python manage.py runserver` → http://127.0.0.1:8000 |\n"
                         "| 2.7 | Criar app core com:\n`python manage.py startapp core` |\n"
                         "| 2.8 | Adicionar `'core'` à lista de `INSTALLED_APPS` no `settings.py` |\n"
                         "| 2.9 | Criar modelo `Transacao` em `models.py` com campos: `descricao`, `valor`, `data` |\n"
                         "| 2.10 | Registar `Transacao` no `admin.py` com `from .models import Transacao` e `admin.site.register(Transacao)` |\n"
                         "| 2.11 | Criar e aplicar migrações:\n`python manage.py makemigrations` e `python manage.py migrate` |\n"
                         "| 2.12 | Criar superuser com `python manage.py createsuperuser` |\n"
                         "| 2.13 | Aceder ao admin: http://127.0.0.1:8000/admin |\n"
                         "| 2.14 | Verificar se o modelo Transacao está acessível no admin e funciona |\n"
                         "| 2.15 | Criar views, formulário e template para inserir e listar transações |\n"
                         "| 2.16 | Criar ficheiro `.env` com variáveis `DB_NAME`, `DB_USER`, etc. |\n"
                         "| 2.17 | Adicionar `load_dotenv()` e usar `os.getenv()` no `settings.py` |\n"
                         "| 2.18 | Substituir base de dados SQLite pela ligação PostgreSQL/Supabase |\n"
                         "| 2.19 | Confirmar ligação com Supabase usando pgAdmin e Django ORM |\n"
                         "| 2.20 | Criar `.gitignore` para ignorar `.env`, `db.sqlite3`, `__pycache__`, pasta virtual |\n"
                         "| 2.21 | Se `.env` tiver sido enviado para Git, usar `git rm --cached .env` para removê-lo |"),
    v4.new_markdown_cell("---"),

    v4.new_markdown_cell("## 🌐 FASE 3: Alojamento (em curso)\n"
                         "Configuração para publicação do projeto online com Render."),
    v4.new_markdown_cell("### ✅ Etapas\n"
                         "| Etapa | Ação |\n"
                         "|-------|------|\n"
                         "| 3.1 | Criar repositório GitHub |\n"
                         "| 3.2 | Criar ficheiros de deploy: `requirements.txt`, `Procfile`, `render.yaml` |\n"
                         "| 3.3 | Criar Web Service no Render |\n"
                         "| 3.4 | Adicionar variáveis de ambiente no Render |\n"
                         "| 3.5 | Executar `migrate` e `createsuperuser` via shell |\n"
                         "| 3.6 | Testar link do site: `https://ourfinancetracker.onrender.com` |"),
    v4.new_markdown_cell("---"),

    v4.new_markdown_cell("## 🔐 FASE 4: Domínio (por iniciar)\n"
                         "Configuração para usar domínio próprio com Render."),
    v4.new_markdown_cell("### 🔜 Etapas\n"
                         "| Etapa | Ação |\n"
                         "|-------|------|\n"
                         "| 4.1 | Ativar domínio em Site.pt |\n"
                         "| 4.2 | Apontar DNS para Render |\n"
                         "| 4.3 | Validar propagação DNS |\n"
                         "| 4.4 | Ativar SSL |"),
    v4.new_markdown_cell("---"),

    v4.new_markdown_cell("## 🧰 FASE 5: Segurança e Manutenção\n"
                         "Tarefas para garantir segurança e fiabilidade."),
    v4.new_markdown_cell("### 🔒 Ações\n"
                         "| Etapa | Ação |\n"
                         "|-------|------|\n"
                         "| 5.1 | Garantir HTTPS ativo |\n"
                         "| 5.2 | Configurar backups |\n"
                         "| 5.3 | Criar logs e controlo de erros |\n"
                         "| 5.4 | Ajustar `ALLOWED_HOSTS` |"),
    v4.new_markdown_cell("---"),

    v4.new_markdown_cell("## 📈 FASE 6: Evolução\n"
                         "Funcionalidades futuras para evolução do projeto."),
    v4.new_markdown_cell("- Novas funcionalidades Django\n"
                         "- Dashboards com Metabase ou outra ferramenta\n"
                         "- API REST\n"
                         "- Mobile app\n"
                         "- Integração com email, exportações, alertas")
]

# Criar o notebook e guardar
notebook = v4.new_notebook(cells=cells)
path = Path("roadmap_detalhado.ipynb")
with path.open("w", encoding="utf-8") as f:
    f.write(writes(notebook, indent=2))

path.name
