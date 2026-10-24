# QUITA

Plataforma de captação e atendimento para análise e renegociação veicular.

## Estado do projeto

Este repositório começa com uma base de backend testável. Integrações reais de dados veiculares exigem provedores autorizados, documentação e credenciais válidas. O sistema deve distinguir `indisponível` de `nenhuma pendência identificada` e nunca inventar resultados.

## Arquitetura inicial

- `backend/app`: API FastAPI e camada de provedores.
- `backend/tests`: testes automatizados do failover e da validação de configuração.
- `frontend`: reservado para a aplicação web responsiva.

## Desenvolvimento local

Requer Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --app-dir backend
pytest
```

## Segurança

Nunca commite chaves reais. Use variáveis de ambiente/secret manager em produção, TLS, autenticação e autorização para endpoints administrativos. O endpoint de gestão de provedores nesta primeira base é explicitamente protegido por uma chave administrativa configurada no servidor; antes de produção, deve ser integrado ao sistema completo de usuários, funções, auditoria e armazenamento seguro.
