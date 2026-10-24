# QUITA

Plataforma de captação e atendimento para análise e renegociação veicular.

## Integração BuscaFIPE

O backend possui um cliente server-side para a API documentada em `https://buscafipe.com/api`.

- `GET /integrations/buscafipe/fipe?action=marcas|modelos|anos|valor`
- `POST /integrations/buscafipe/placa` com JSON `{"placa":"ABC1D23"}`
- `POST /integrations/buscafipe/cnpj` com JSON `{"cnpj":"00000000000100"}`
- `GET /integrations/buscafipe/ipva?uf=SP`

Documentação de referência: https://buscafipe.com/api-docs/

O plano informado pela documentação permite 100 consultas por dia para FIPE/IPVA sem autenticação. Endpoints de placa/CNPJ e cobertura ampliada podem depender de acesso de parceiro; confirme as condições e a autenticação diretamente com o fornecedor. O QUITA não presume um formato de chave que a documentação não descreva. Respostas HTTP 429 e falhas de rede são expostas como indisponibilidade, não como ausência de débitos.

As rotas de consulta estão prontas para integração, mas não substituem uma validação de contrato, política de uso, cobertura e formatos reais de resposta antes da produção.

## Estado do projeto

Este repositório começa com uma base de backend testável. Integrações reais de dados veiculares exigem provedores autorizados, documentação e credenciais válidas. O sistema deve distinguir `indisponível` de `nenhuma pendência identificada` e nunca inventar resultados.

## Arquitetura inicial

- `backend/app`: API FastAPI e camada de provedores.
- `backend/tests`: testes automatizados do failover e dos adaptadores.
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
