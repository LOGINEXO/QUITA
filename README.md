# QUITA

Plataforma de captação e atendimento para análise e renegociação veicular.

## Hospedagem no Render

O repositório inclui um Blueprint em `render.yaml` para criar o serviço FastAPI e um PostgreSQL no Render, com conexão privada entre eles.

1. Abra o Render e escolha **New → Blueprint**.
2. Conecte o repositório `LOGINEXO/QUITA`.
3. Revise os recursos e os planos/custos antes de confirmar a criação.
4. O Render injeta `DATABASE_URL` pela propriedade `connectionString` do banco.
5. As migrations são aplicadas no início do serviço por `alembic upgrade head`.
6. O health check de liveness é `/health/live`; `/health/ready` verifica também a conexão com o banco.

**Importante:** o Blueprint usa planos `free` para facilitar a primeira validação. Antes de produção, confirme as limitações, a retenção/expiração do banco gratuito e os requisitos de disponibilidade no Render; escolha um plano pago se precisar de persistência e operação de produção garantidas. Serviço e banco devem ficar na mesma região. O banco está configurado para aceitar apenas conexões internas (`ipAllowList: []`).

## Persistência inicial

A primeira migration cria as tabelas para clientes, leads, consultas veiculares, configuração de provedores e auditoria. O esquema não armazena chaves de API em texto puro: `api_providers.secret_ref` é uma referência a um segredo configurado fora do banco. O gerenciador de provedores existente ainda precisa ser conectado a essa persistência na próxima etapa.

## Integração BuscaFIPE

O backend possui um cliente server-side para a API documentada em `https://buscafipe.com/api`.

- `GET /integrations/buscafipe/fipe?action=marcas|modelos|anos|valor`
- `POST /integrations/buscafipe/placa` com JSON `{"placa":"ABC1D23"}`
- `POST /integrations/buscafipe/cnpj` com JSON `{"cnpj":"00000000000100"}`
- `GET /integrations/buscafipe/ipva?uf=SP`

Documentação de referência: https://buscafipe.com/api-docs/

A documentação informa 100 consultas/dia sem autenticação para FIPE/IPVA. Ela lista CNPJ como gratuito, mas também descreve acesso de parceiro com chave para todos os endpoints; confirme com o fornecedor a disponibilidade do endpoint de CNPJ por API e o mecanismo de autenticação. A consulta por placa aparece como premium/parceiro. O código não inventa um formato de chave que a documentação não descreva. Respostas HTTP 429 e falhas de rede são expostas como indisponibilidade, não como ausência de débitos.

As rotas de consulta ainda precisam de rate limiting/autenticação pública apropriada antes de serem expostas sem restrições. Não use resultados da BuscaFIPE como prova de que multas, débitos ou restrições não existem sem confirmar a cobertura da fonte.

## Desenvolvimento local

Requer Python 3.11+ e PostgreSQL se quiser testar uma conexão real.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
# Defina DATABASE_URL antes de executar migrations
alembic upgrade head
uvicorn app.main:app --reload --app-dir backend
pytest
```

## Segurança

Nunca commite chaves reais. Use variáveis de ambiente/secret manager em produção, TLS quando aplicável, autenticação e autorização para endpoints administrativos. O endpoint de gestão de provedores continua usando uma chave administrativa simples como proteção inicial; isso não substitui autenticação completa de usuários, funções, auditoria e armazenamento seguro.
