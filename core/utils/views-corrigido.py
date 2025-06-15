#!/usr/bin/env python
"""
Script para gerar e configurar uma nova SECRET_KEY segura no .env

Este script:
1. Verifica se o ficheiro .env existe, se não, cria um baseado no .env.example
2. Gera uma nova SECRET_KEY segura
3. Atualiza o .env com a nova SECRET_KEY
4. Verifica outras configurações críticas no .env
"""

import os
import sys
import secrets
import string
from pathlib import Path
from dotenv import load_dotenv


def generate_secret_key(length=64):
    """Gera uma SECRET_KEY forte usando o módulo secrets."""
    alphabet = string.ascii_letters + string.digits + '-_!@#$%^&*()+='
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def check_or_create_env():
    """Verifica se o .env existe, se não, cria baseado no .env.example."""
    env_path = Path('.env')
    example_path = Path('env-example.txt')
    
    if not env_path.exists():
        if example_path.exists():
            print("❌ Ficheiro .env não encontrado")
            print("✅ Criando .env baseado em env-example.txt")
            with open(example_path, 'r') as example_file:
                with open(env_path, 'w') as env_file:
                    env_file.write(example_file.read())
        else:
            print("❌ Nem .env nem env-example.txt encontrados!")
            print("📝 Criando .env mínimo")
            with open(env_path, 'w') as env_file:
                env_file.write("SECRET_KEY=\nDEBUG=True\n")
    
    return env_path.exists()


def update_secret_key(env_path):
    """Atualiza a SECRET_KEY no .env."""
    new_key = generate_secret_key()
    
    with open(env_path, 'r') as file:
        lines = file.readlines()
    
    key_updated = False
    with open(env_path, 'w') as file:
        for line in lines:
            if line.startswith('SECRET_KEY='):
                file.write(f'SECRET_KEY={new_key}\n')
                key_updated = True
            else:
                file.write(line)
    
    if not key_updated:
        with open(env_path, 'a') as file:
            file.write(f'\nSECRET_KEY={new_key}\n')
    
    return new_key


def check_other_critical_settings(env_path):
    """Verifica outras configurações críticas no .env."""
    load_dotenv(env_path)
    
    issues = []
    
    # Verificar DEBUG
    debug = os.getenv('DEBUG', 'True')
    if debug.lower() == 'true' and not input_is_yes("⚠️ DEBUG está definido como True. Manter? (y/N): "):
        with open(env_path, 'r') as file:
            content = file.read()
        
        content = content.replace('DEBUG=True', 'DEBUG=False')
        
        with open(env_path, 'w') as file:
            file.write(content)
        
        print("✅ DEBUG definido como False")
    
    # Verificar configuração da base de dados
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    if not all([db_name, db_user, db_password]):
        issues.append("⚠️ Configuração da base de dados incompleta no .env")
    
    return issues


def input_is_yes(prompt):
    """Retorna True se o input for 'y' ou 'yes'."""
    response = input(prompt).lower()
    return response in ['y', 'yes', 's', 'sim']


def main():
    """Função principal."""
    print("🔐 Gerador de SECRET_KEY para Django")
    print("=" * 50)
    
    if not check_or_create_env():
        print("❌ Não foi possível criar o ficheiro .env")
        sys.exit(1)
    
    env_path = '.env'
    new_key = update_secret_key(env_path)
    
    print(f"✅ Nova SECRET_KEY gerada e guardada em {env_path}")
    print(f"📋 Valor (não partilhe!): {new_key}")
    
    issues = check_other_critical_settings(env_path)
    
    if issues:
        print("\n⚠️ Verificações adicionais:")
        for issue in issues:
            print(f"  - {issue}")
    
    print("\n✅ Processo concluído!")
    print("Para usar a nova SECRET_KEY, reinicie a aplicação Django.")


if __name__ == "__main__":
    main()