"""Consulta do CRLV digital — Detran-MT.

Só precisa de placa, RENAVAM e documento do proprietário (CPF ou CNPJ).
Não grava credenciais no código. Use somente com autorização.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

CRLVMt_URL = "https://internet.detrannet.mt.gov.br/ApiRenavam/api/CRLV"


def proxy_url(proxy: str | None = None) -> str | None:
    """Converte host:porta:usuario:senha ou URL em URL de proxy."""
    value = proxy or os.getenv("DETRAN_PROXY")
    if not value:
        return None
    if "://" in value:
        return value
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise ValueError("DETRAN_PROXY deve estar em host:porta:usuario:senha")
    host, port, user, password = parts
    return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"


def decode_base64_pdf(value: str | bytes) -> bytes:
    raw = value.encode() if isinstance(value, str) else value
    raw = raw.strip()
    if raw.startswith(b"data:"):
        raw = raw.split(b",", 1)[1]
    try:
        decoded = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("O retorno não é base64 válido") from exc
    if not decoded.startswith(b"%PDF"):
        raise ValueError("Base64 decodificado não começa com assinatura PDF")
    return decoded


def classificar_mensagem(texto: str) -> str:
    normalizado = texto.casefold()
    if "não foi encontrado registro" in normalizado or "nao foi encontrado registro" in normalizado:
        return "registro_nao_encontrado"
    if "placa em formato inválido" in normalizado or "placa em formato invalido" in normalizado:
        return "placa_invalida"
    if "uf diferente" in normalizado or "pertence à uf" in normalizado or "pertence a uf" in normalizado:
        return "uf_divergente"
    return "outro"


def normalizar_mensagens(payload: Any) -> list[dict[str, str]]:
    valores: list[Any] = []
    if isinstance(payload, dict):
        for chave, valor in payload.items():
            chave_n = str(chave).casefold()
            if any(t in chave_n for t in ("mensagem", "message", "erro")):
                valores.extend(valor if isinstance(valor, list) else [valor])
    elif isinstance(payload, list):
        valores = payload
    elif isinstance(payload, str):
        valores = [payload]

    mensagens: list[str] = []
    for valor in valores:
        if not isinstance(valor, str):
            continue
        texto = re.sub(r"\s+", " ", valor).strip()
        if not texto:
            continue
        if texto not in mensagens:
            mensagens.append(texto)
    return [{"tipo": classificar_mensagem(t), "texto": t} for t in mensagens]


def extrair_dados_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """Extrai texto do PDF com pdftotext, se disponível."""
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Conteúdo sem assinatura PDF válida")
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf_bytes)
        f.flush()
        proc = subprocess.run(
            ["pdftotext", "-layout", f.name, "-"],
            capture_output=True,
            text=True,
            check=False,
        )
    texto = proc.stdout.strip()
    linhas = [re.sub(r"\s+", " ", ln).strip() for ln in texto.splitlines() if ln.strip()]
    campos: dict[str, str] = {}
    for linha in linhas:
        if ":" in linha:
            k, v = linha.split(":", 1)
            if k.strip() and v.strip():
                campos[k.strip()] = v.strip()
    return {"texto": texto, "linhas": linhas, "campos": campos}


def consultar_crlv_mt(
    *,
    placa: str,
    renavam: str,
    documento_proprietario: str,
    cookies: str | None = None,
    proxy: str | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    """Consulta CRLV-MT. Obrigatórios: placa, RENAVAM, documento (CPF/CNPJ)."""
    obrigatorios = {
        "placa": placa,
        "renavam": renavam,
        "documento_proprietario": documento_proprietario,
    }
    ausentes = [n for n, v in obrigatorios.items() if not str(v or "").strip()]
    if ausentes:
        return {
            "kind": "incompleto",
            "disponivel": False,
            "dados": None,
            "mensagens": [{
                "tipo": "campos_obrigatorios_ausentes",
                "texto": "Campos obrigatórios ausentes",
                "campos": ausentes,
            }],
        }

    session = requests.Session()
    p = proxy_url(proxy)
    if p:
        session.proxies.update({"http": p, "https": p})

    headers = {"accept": "application/pdf, application/json, */*"}
    if cookies:
        headers["cookie"] = cookies

    response = session.get(
        CRLVMt_URL,
        params={
            "Placa": placa.strip().upper(),
            "Renavam": renavam.strip(),
            "DocumentoProprietario": documento_proprietario.strip(),
        },
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    body = response.content

    if body.startswith(b"%PDF") or "application/pdf" in content_type:
        dados = None
        try:
            dados = extrair_dados_pdf(body)
        except Exception:
            pass
        return {
            "kind": "pdf",
            "disponivel": True,
            "dados": dados,
            "bytes": body,
            "size": len(body),
        }

    text = response.text.strip()
    if text.casefold() == "lista de erros":
        return {
            "kind": "incompleto",
            "disponivel": False,
            "mensagens": [{"tipo": "retorno_incompleto", "texto": "Lista de Erros"}],
        }

    try:
        payload = response.json()
        mensagens = normalizar_mensagens(payload)
        return {
            "kind": "json",
            "disponivel": not bool(mensagens),
            "dados": payload,
            "mensagens": mensagens,
        }
    except ValueError:
        pass

    try:
        pdf = decode_base64_pdf(text)
        dados = None
        try:
            dados = extrair_dados_pdf(pdf)
        except Exception:
            pass
        return {
            "kind": "pdf_base64",
            "disponivel": True,
            "dados": dados,
            "bytes": pdf,
            "size": len(pdf),
        }
    except ValueError:
        mensagens = normalizar_mensagens(text)
        return {
            "kind": "text",
            "disponivel": False,
            "mensagens": mensagens or [{"tipo": "outro", "texto": text}],
        }


def salvar_documento(resultado: dict[str, Any], caminho: str | os.PathLike[str]) -> str:
    path = Path(caminho)
    kind = resultado.get("kind")
    if kind in {"pdf", "pdf_base64"} and isinstance(resultado.get("bytes"), (bytes, bytearray)):
        path.write_bytes(bytes(resultado["bytes"]))
    else:
        path.write_text(resultado.get("text", json.dumps(resultado, ensure_ascii=False)), encoding="utf-8")
    return str(path)
