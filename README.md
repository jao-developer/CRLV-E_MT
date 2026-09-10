# CRLV digital — Detran-MT

Consulta do Certificado de Registro e Licenciamento de Veículo (digital) no portal do **Detran-MT**.

Use **somente** com autorização e dados legítimos.

## Campos obrigatórios

| Campo | Exemplo |
|-------|---------|
| placa | `ABC1D23` |
| renavam | `00000000000` |
| documento | CPF ou CNPJ do proprietário |

Nada mais é necessário para o CRLV-MT.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Opcional: `pdftotext` (poppler-utils) para extrair texto do PDF.

## Uso

1. Edite `consultar.py` e preencha os três campos.
2. (Opcional) configure proxy:

```bash
export DETRAN_PROXY="host:porta:usuario:senha"
```

3. Execute:

```bash
python consultar.py
```

Saídas (ignoradas pelo Git):

- `crlv_mt.pdf` — documento, se disponível
- `resultado_mt.json` — resumo

## Arquivos

| Arquivo | Função |
|---------|--------|
| `consultar.py` | Script principal (só os 3 campos) |
| `crlve_mt.py` | Cliente HTTP da API do Detran-MT |

## Segurança no GitHub

- [ ] Placeholders em `consultar.py` (sem placa/CPF reais)
- [ ] Nenhum PDF ou JSON de resultado no commit
- [ ] Proxy só em `DETRAN_PROXY`, nunca no código
