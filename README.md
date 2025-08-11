# ourfinancetracker

> **Aplicação web de controlo financeiro pessoal**

Este repositório contém o código‑fonte do **ourfinancetracker**, uma aplicação em Django que permite aos utilizadores registar saldos mensais, rendimentos e despesas, obtendo assim uma visão consolidada da sua saúde financeira, sem dependência de APIs bancárias externas.

## ✨ Funcionalidades principais

- Dashboard mensal com receitas, despesas estimadas e saldos
- Contas bancárias e de investimento ilimitadas
- Categorias personalizáveis por utilizador
- Etiquetas (tags) reutilizáveis para categorizar transações
- Estimativa automática de despesas com base no saldo
- Multi-moeda com suporte a diferentes tipos de contas
- Relatórios baseados em períodos mensais
- Interface responsiva com formulários dinâmicos

## 🏗️ Tech Stack

| Camada        | Tecnologia                                  |
| ------------- | ------------------------------------------- |
| Backend       | Django 5.2.1 · Python 3.12                  |
| Base de dados | PostgreSQL (via Supabase)                   |
| Frontend      | Django Templates (fase inicial)             |
| Deploy        | Render.com (config via `render.yaml`)       |
| Dev Tools     | pip · pre‑commit · GitHub Actions           |

## 📐 Modelo de Dados

### Diagrama ER

```mermaid
erDiagram

%% ---------- AUTENTICAÇÃO ----------
auth_user||--o{auth_user_groups: has
auth_user||--o{auth_user_user_permissions: has
auth_group||--o{auth_group_permissions: has
auth_user_groups}o--||auth_group: member_of
auth_user_user_permissions}o--||auth_permission: granted_to
auth_group_permissions}o--||auth_permission: grants
auth_permission}o--||django_content_type: applies_to
django_admin_log}o--||auth_user: action_by
django_admin_log}o--||django_content_type: relates_to

%% ---------- CORE ----------
auth_user||--o{core_account: owns
auth_user||--o{core_transaction: records
auth_user||--o{core_category: defines

core_account}o--||core_accounttype: typed_as
core_account}o--||core_currency: in_currency

core_accountbalance}o--||core_account: for_account
core_accountbalance}o--||date_period: for_period

core_transaction}o--||core_category: categorized_as
core_transaction}o--||date_period: for_period

core_transaction_tags}o--||core_transaction: tags_txn
core_transaction_tags}o--||core_tag: with_tag
```

## 🚀 Como começar

```bash
# Clonar o repositório
git clone https://github.com/nunonuno7/ourfinancetracker.git
cd ourfinancetracker

# Instalar dependências
pip install -r requirements.txt

# Copiar e configurar variáveis de ambiente
cp .env.example .env
# editar valores conforme necessário

# Criar base de dados e aplicar migrações
python manage.py migrate

# Iniciar servidor local
python manage.py runserver
```

## 🌐 Domínios adicionais

Para autorizar novos domínios no `ALLOWED_HOSTS` ou na lista de origens confiáveis do CSRF, defina variáveis de ambiente adicionais:

```bash
EXTRA_ALLOWED_HOSTS=exemplo.com,sub.dominio.com
EXTRA_CSRF_TRUSTED_ORIGINS=https://exemplo.com,https://sub.dominio.com
```

Use valores separados por vírgulas. No caso de `EXTRA_CSRF_TRUSTED_ORIGINS`, cada origem deve incluir o esquema (`http://` ou `https://`).

## 📄 Licença

Distribuído sob a licença MIT. Ver ficheiro `LICENSE` para mais detalhes.