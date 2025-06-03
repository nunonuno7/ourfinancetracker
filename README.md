# ourfinancetracker

> **Aplicação web de controlo financeiro pessoal**

Este repositório contém o código‑fonte do **ourfinancetracker**, uma aplicação em Django que permite aos utilizadores registar saldos mensais, rendimentos e despesas, obtendo assim uma visão consolidada da sua saúde financeira sem dependências de APIs bancárias externas.

## ✨ Principais Funcionalidades

* **Dashboard resumido** de receitas, despesas estimadas e saldos por mês
* **Contas** bancárias e de investimento ilimitadas
* **Categorias & Subcategorias** personalizáveis para rendimentos e despesas
* **Estimativa automática de despesas** (quando não inseridas manualmente)
* **Orçamentos** e **transações recorrentes**
* Importação de ficheiros (CSV, OFX, etc.)
* Multi‑moeda com **taxas de câmbio** históricas

## 🏗️ Tech Stack

| Camada        | Tecnologia                                  |
| ------------- | ------------------------------------------- |
| Backend       | Django 5.2.1 · Python 3.12                  |
| Base de dados | PostgreSQL (via Supabase)                   |
| Frontend      | Django Templates (fase inicial)             |
| Deploy        | Render.com (configuração via `render.yaml`) |
| Dev Tools     | Poetry · pre‑commit · GitHub Actions        |

## 📐 Modelo de Dados

### Diagrama Entidade‑Relacionamento

```mermaid
%% Copiado de mermaidchart.md
" + open('/mnt/data/mermaidchart.md').read() + "
```

### Dicionário de Dados

<details>
<summary><strong>USER</strong></summary>

| Campo           | Tipo         | Descrição                         |
| --------------- | ------------ | --------------------------------- |
| `id`            | int PK       | Identificador único do utilizador |
| `username`      | varchar(150) | Nome de utilizador **único**      |
| `email`         | varchar(254) | Endereço de e‑mail **único**      |
| `password_hash` | varchar(255) | Hash da palavra‑passe             |
| `is_active`     | boolean      | Se a conta está ativa             |
| `created_at`    | datetime     | Data/hora de criação              |
| `updated_at`    | datetime     | Data/hora da última atualização   |

</details>

<details>
<summary><strong>USER_SETTINGS</strong></summary>

| Campo                 | Tipo        | Descrição                                 |
| --------------------- | ----------- | ----------------------------------------- |
| `id`                  | int PK      | Identificador único                       |
| `user_id`             | int FK      | Referência ao **USER**                    |
| `default_currency_id` | varchar(3)  | Moeda padrão (FK → **CURRENCY**)          |
| `timezone`            | varchar(50) | Fuso horário (e.g. `Europe/Lisbon`)       |
| `start_of_month`      | tinyint     | Dia em que considera iniciar o mês (1‑31) |
| `created_at`          | datetime    | Data/hora de criação                      |
| `updated_at`          | datetime    | Data/hora da última atualização           |

</details>

<details>
<summary><strong>ACCOUNT</strong></summary>

| Campo             | Tipo        | Descrição                              |
| ----------------- | ----------- | -------------------------------------- |
| `id`              | int PK      | Identificador único da conta           |
| `user_id`         | int FK      | Referência ao **USER**                 |
| `name`            | varchar(80) | Nome atribuído pelo utilizador         |
| `account_type_id` | int FK      | Tipo de conta (FK → **ACCOUNT\_TYPE**) |
| `currency_id`     | varchar(3)  | Moeda da conta (FK → **CURRENCY**)     |
| `created_at`      | datetime    | Data/hora de criação                   |
| `updated_at`      | datetime    | Data/hora da última atualização        |

</details>

<details>
<summary><strong>ACCOUNT_TYPE</strong></summary>

| Campo  | Tipo        | Descrição                                     |
| ------ | ----------- | --------------------------------------------- |
| `id`   | int PK      | Identificador único                           |
| `name` | varchar(40) | Descritivo (ex.: "Conta à ordem", "Poupança") |

</details>

<details>
<summary><strong>CURRENCY</strong></summary>

| Campo      | Tipo          | Descrição                           |
| ---------- | ------------- | ----------------------------------- |
| `code`     | varchar(3) PK | Código ISO‑4217 (ex.: EUR, USD)     |
| `symbol`   | varchar(4)    | Símbolo monetário (€, \$)           |
| `decimals` | tinyint       | Número de casas decimais suportadas |

</details>

<details>
<summary><strong>ACCOUNT_BALANCE</strong></summary>

| Campo              | Tipo     | Descrição                             |
| ------------------ | -------- | ------------------------------------- |
| `id`               | int PK   | Identificador único                   |
| `account_id`       | int FK   | Referência à **ACCOUNT**              |
| `balance_date`     | date     | Data do saldo reportado               |
| `reported_balance` | decimal  | Valor do saldo                        |
| `is_manual_entry`  | boolean  | Indica se foi introduzido manualmente |
| `created_at`       | datetime | Data/hora de criação                  |
| `updated_at`       | datetime | Data/hora da última atualização       |

</details>

<details>
<summary><strong>CATEGORY</strong></summary>

| Campo        | Tipo        | Descrição                           |
| ------------ | ----------- | ----------------------------------- |
| `id`         | int PK      | Identificador único                 |
| `user_id`    | int FK      | Referência ao **USER**              |
| `name`       | varchar(80) | Nome da categoria                   |
| `parent_id`  | int FK      | Categoria pai (auto‑relacionamento) |
| `created_at` | datetime    | Data/hora de criação                |
| `updated_at` | datetime    | Data/hora da última atualização     |

</details>

<details>
<summary><strong>TRANSACTION</strong></summary>

| Campo          | Tipo     | Descrição                                  |
| -------------- | -------- | ------------------------------------------ |
| `id`           | int PK   | Identificador único                        |
| `user_id`      | int FK   | Referência ao **USER**                     |
| `amount`       | decimal  | Valor da transação (+ receita / − despesa) |
| `date`         | date     | Data da transação                          |
| `type`         | enum     | `income`, `expense`, `investment`          |
| `category_id`  | int FK   | Categoria associada                        |
| `account_id`   | int FK   | Conta reconciliada (opcional)              |
| `is_estimated` | boolean  | Se o valor é estimado (default: `false`)   |
| `notes`        | text     | Observações livres                         |
| `is_cleared`   | boolean  | Se a transação foi reconciliada            |
| `created_at`   | datetime | Data/hora de criação                       |
| `updated_at`   | datetime | Data/hora da última atualização            |

</details>

<details>
<summary><strong>TRANSACTION_ATTACHMENT</strong></summary>

| Campo            | Tipo         | Descrição                                         |
| ---------------- | ------------ | ------------------------------------------------- |
| `id`             | int PK       | Identificador único                               |
| `transaction_id` | int FK       | Referência à **TRANSACTION**                      |
| `file_path`      | varchar(255) | Localização do ficheiro (no sistema de ficheiros) |
| `created_at`     | datetime     | Data/hora de criação                              |
| `updated_at`     | datetime     | Data/hora da última atualização                   |

</details>

<details>
<summary><strong>BUDGET</strong></summary>

| Campo         | Tipo     | Descrição                                             |
| ------------- | -------- | ----------------------------------------------------- |
| `id`          | int PK   | Identificador único                                   |
| `user_id`     | int FK   | Referência ao **USER**                                |
| `category_id` | int FK   | Categoria orçamentada                                 |
| `start_date`  | date     | Início do período                                     |
| `end_date`    | date     | Fim do período                                        |
| `amount`      | decimal  | Montante orçamentado                                  |
| `rollover`    | boolean  | Se o saldo não gasto transita para o período seguinte |
| `created_at`  | datetime | Data/hora de criação                                  |
| `updated_at`  | datetime | Data/hora da última atualização                       |

</details>

<details>
<summary><strong>RECURRING_TRANSACTION</strong></summary>

| Campo                     | Tipo     | Descrição                               |
| ------------------------- | -------- | --------------------------------------- |
| `id`                      | int PK   | Identificador único                     |
| `user_id`                 | int FK   | Referência ao **USER**                  |
| `amount`                  | decimal  | Valor da transação recorrente           |
| `frequency`               | enum     | `daily`, `weekly`, `monthly`, `yearly`  |
| `next_occurrence`         | date     | Próxima ocorrência prevista             |
| `end_date`                | date     | Data de término (opcional)              |
| `is_active`               | boolean  | Se o agendamento está ativo             |
| `template_transaction_id` | int FK   | Transação modelo (FK → **TRANSACTION**) |
| `created_at`              | datetime | Data/hora de criação                    |
| `updated_at`              | datetime | Data/hora da última atualização         |

</details>

<details>
<summary><strong>IMPORT_LOG</strong></summary>

| Campo           | Tipo        | Descrição                                  |
| --------------- | ----------- | ------------------------------------------ |
| `id`            | int PK      | Identificador único                        |
| `user_id`       | int FK      | Referência ao **USER**                     |
| `source`        | varchar(80) | Origem do ficheiro (ex.: "n26.csv")        |
| `imported_at`   | datetime    | Data/hora da importação                    |
| `num_records`   | int         | Número de registos processados             |
| `status`        | enum        | `success`, `partial`, `error`              |
| `error_message` | text        | Mensagem de erro (quando `status = error`) |
| `created_at`    | datetime    | Data/hora de criação                       |
| `updated_at`    | datetime    | Data/hora da última atualização            |

</details>

<details>
<summary><strong>EXCHANGE_RATE</strong></summary>

| Campo                | Tipo       | Descrição                            |
| -------------------- | ---------- | ------------------------------------ |
| `id`                 | int PK     | Identificador único                  |
| `from_currency_code` | varchar(3) | Moeda de origem (FK → **CURRENCY**)  |
| `to_currency_code`   | varchar(3) | Moeda de destino (FK → **CURRENCY**) |
| `rate`               | decimal    | Taxa de câmbio                       |
| `rate_date`          | date       | Data de referência da taxa           |
| `created_at`         | datetime   | Data/hora de criação                 |
| `updated_at`         | datetime   | Data/hora da última atualização      |

</details>

## 🚀 Como Começar

```bash
# Clonar o repositório
$ git clone https://github.com/nunonuno7/ourfinancetracker.git
$ cd ourfinancetracker

# Instalar dependências
$ poetry install

# Configurar variáveis de ambiente
$ cp .env.example .env
# editar as variáveis necessárias

# Criar e aplicar migrações
$ poetry run python manage.py migrate

# Iniciar servidor de desenvolvimento
$ poetry run python manage.py runserver
```

## 📄 Licença

Distribuído sob a licença MIT. Consulte o ficheiro `LICENSE` para mais detalhes.
