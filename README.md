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

## Persistência e provedores de API

A migration inicial cria as tabelas para clientes, leads, consultas veiculares, provedores de API e auditoria. O gerenciamento de provedores usa PostgreSQL para criar, listar, atualizar e remover configurações. Chaves de API não são armazenadas em texto puro: `api_providers.secret_ref` guarda somente uma referência à variável de ambiente.

Para configurar a chave de um provedor, defina no ambiente do serviço Render a variável correspondente ao ID do provedor, seguindo o padrão `QUITA_PROVIDER_<ID>_API_KEY` (o ID é convertido para maiúsculas e caracteres não alfanuméricos viram sublinhados).

## Captação e gestão de leads

- `POST /leads`: recebe nome, e-mail e/ou telefone, código postal opcional, origem e consentimento de privacidade. Requer pelo menos um meio de contato e consentimento explícito. Cria o cliente e o lead no PostgreSQL.
- `GET /admin/leads`: lista leads para uso administrativo. Aceita `status`, `limit` (1–200) e `offset`. Requer autenticação administrativa.
- `PATCH /admin/leads/{lead_id}`: atualiza o status (`new`, `contacted`, `qualified`, `converted`, `closed`) e opcionalmente as notas. Requer autenticação administrativa.

## Consultas veiculares

- `POST /consultations/vehicle`: valida e normaliza a placa, consulta a BuscaFIPE e salva a consulta, o resultado e o estado no PostgreSQL. Aceita `lead_id` opcional para associar a consulta a um lead.
- `GET /admin/consultations/vehicle`: lista consultas para administradores, com filtros opcionais por `status` e `lead_id`, paginação por `limit` e `offset`. Requer autenticação administrativa.
- Os estados persistidos são `pending`, `success`, `unavailable` e `failed`. Uma indisponibilidade do fornecedor não é tratada como confirmação de ausência de débitos ou restrições.
- A consulta por placa depende da disponibilidade e das condições comerciais do fornecedor. A API não promete dados que o fornecedor não disponibilizar.

## Integração BuscaFIPE

O backend possui um cliente server-side para a API documentada em `https://buscafipe.com/api`.

- `GET /integrations/buscafipe/fipe?action=marcas|modelos|anos|valor`
- `POST /integrations/buscafipe/placa` com JSON `{"placa":"ABC1D23"}`
- `POST /integrations/buscafipe/cnpj` com JSON `{"cnpj":"00000000000100"}`
- `GET /integrations/buscafipe/ipva?uf=SP`

Documentação de referência: https://buscafipe.com/api-docs/

A documentação informa 100 consultas/dia sem autenticação para FIPE/IPVA. Ela lista CNPJ como gratuito, mas também descreve acesso de parceiro com chave para todos os endpoints; confirme com o fornecedor a disponibilidade do endpoint de CNPJ por API e o mecanismo de autenticação. A consulta por placa aparece como premium/parceiro. O código não inventa um formato de chave que a documentação não descreva. Respostas HTTP 429 e falhas de rede são expostas como indisponibilidade, não como ausência de débitos.

## Proteção de requisições

Os endpoints públicos aplicam limites por IP e janela móvel: login administrativo (5/min), criação de lead (10/min), consulta por placa (5/min) e endpoints públicos BuscaFIPE de placa/CNPJ (5/min). Excesso retorna HTTP 429 e `Retry-After`.

- Configure `QUITA_REDIS_URL` no ambiente do serviço para usar o contador Redis compartilhado entre instâncias.
- O Redis executa a atualização da janela em uma operação Lua atômica; a chave usa hash do IP, não o IP em texto puro.
- Se Redis estiver configurado mas indisponível, as rotas limitadas falham de forma fechada com HTTP 503, em vez de ignorar a proteção.
- Sem `QUITA_REDIS_URL`, a API mantém o modo em memória, adequado apenas a uma instância. Para habilitar o modo compartilhado em produção, conecte um Render Key Value compatível com Redis e defina a URL privada como `QUITA_REDIS_URL`.

Consultas por placa podem envolver dados pessoais; os eventos de auditoria evitam registrar a placa ou os dados de contato.

## Desenvolvimento local

Requer Python 3.11+ e PostgreSQL se quiser testar uma conexão real.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
# Defina DATABASE_URL antes de executar migrations
alembic upgrade head
uvicorn app.main:app --reload --app-dir backend
pytest
```

## Segurança

Nunca commite chaves reais. Use variáveis de ambiente/secret manager em produção e TLS quando aplicável. Endpoints administrativos exigem autenticação; mantenha segredos fora do GitHub e evite registrar dados pessoais desnecessários.

## Login administrativo

O login administrativo usa o e-mail configurado em `QUITA_ADMIN_EMAIL` e a senha guardada somente no ambiente do servidor.

Configure em **Render → quita-api → Environment**:

- `QUITA_ADMIN_EMAIL`: e-mail do administrador.
- `QUITA_ADMIN_PASSWORD`: senha exclusiva com pelo menos 12 caracteres.
- `QUITA_ADMIN_TOKEN_SECRET`: segredo aleatório com pelo menos 32 caracteres.
- `QUITA_ADMIN_TOKEN_TTL_MINUTES`: `30` (opcional; padrão de 30 minutos).

Não coloque a senha nem o segredo no GitHub ou em mensagens. Após o deploy, faça login com `POST /auth/admin/login`, enviando JSON com `email` e `password`. A resposta contém `access_token`; envie-o como `Authorization: Bearer <access_token>`. `GET /auth/admin/me` valida o token. A chave administrativa existente `X-Admin-Api-Key` continua aceita nas rotas de provedores.
