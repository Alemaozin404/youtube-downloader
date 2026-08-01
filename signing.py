#!/usr/bin/env python3
"""
Assinatura digital de atualizacoes (Ed25519)
=============================================
Garante autenticidade e integridade dos instaladores: apenas quem possui a
chave privada consegue publicar uma atualizacao valida.

Chaves:
    - update_private.pem      Chave privada (NUNCA publique; gitignored)
    - update_public_key.py    Chave publica embutida no app para verificar

Uso (CLI):
    python signing.py gerar-chaves            # gera o par + update_public_key.py
    python signing.py assinar <sha256hex>     # assina um digest e imprime base64
    python signing.py verificar <hex> <sig>   # verifica uma assinatura

Uso (API):
    from signing import assinar_sha256, verificar_assinatura
    sig = assinar_sha256(sha256_hex)
    ok  = verificar_assinatura(sha256_hex, sig)
"""

import argparse
import base64
import sys
from pathlib import Path
from typing import Optional

# Permite importar da raiz do projeto
sys.path.insert(0, str(Path(__file__).parent))

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    HAS_CRYPTOGRAPHY = False

PROJECT_DIR = Path(__file__).parent
PRIVATE_KEY_FILE = PROJECT_DIR / "update_private.pem"
PUBLIC_KEY_FILE = PROJECT_DIR / "update_public.pem"
PUBLIC_KEY_MODULE = PROJECT_DIR / "update_public_key.py"


# ─── Geracao de chaves ──────────────────────────────────────────────────────

def gerar_par_chaves(
    privado: Path = PRIVATE_KEY_FILE,
    publico_modulo: Path = PUBLIC_KEY_MODULE,
) -> tuple:
    """Gera o par Ed25519, salva a privada em .pem e o modulo da publica.

    Retorna (pem_privada_bytes, pem_publica_bytes).
    """
    if not HAS_CRYPTOGRAPHY:
        raise RuntimeError(
            "Biblioteca 'cryptography' nao instalada. "
            "Instale com: pip install cryptography"
        )

    privada = Ed25519PrivateKey.generate()
    publica = privada.public_key()

    pem_privada = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_publica = publica.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    privado.parent.mkdir(parents=True, exist_ok=True)
    privado.write_bytes(pem_privada)
    PUBLIC_KEY_FILE.write_bytes(pem_publica)

    # Modulo Python com a chave publica embutida (viaja no app)
    publica_b64 = pem_publica.decode("utf-8").strip()
    publico_modulo.write_text(
        f'#!/usr/bin/env python3\n'
        f'"""Chave publica do sistema de atualizacoes (embutida no app)."""\n\n'
        f'CHAVE_PUBLICA_PEM = """{publica_b64}"""\n',
        encoding="utf-8",
    )
    return pem_privada, pem_publica


# ─── Carregamento de chaves ─────────────────────────────────────────────────

def carregar_chave_privada(caminho: Path = PRIVATE_KEY_FILE) -> Ed25519PrivateKey:
    """Carrega a chave privada Ed25519 de um arquivo PEM."""
    if not HAS_CRYPTOGRAPHY:
        raise RuntimeError("Biblioteca 'cryptography' nao instalada.")
    return serialization.load_pem_private_key(
        Path(caminho).read_bytes(), password=None
    )


def carregar_chave_publica_pem(caminho: Path = PUBLIC_KEY_FILE) -> str:
    """Retorna a chave publica PEM (do arquivo ou do modulo embutido)."""
    if Path(caminho).exists():
        return Path(caminho).read_text(encoding="utf-8")
    # Fallback: modulo gerado embutido no app
    try:
        import update_public_key  # noqa: PLC0415
        return update_public_key.CHAVE_PUBLICA_PEM
    except ImportError:
        return ""


def carregar_chave_publica(caminho: Path = PUBLIC_KEY_FILE) -> Optional[Ed25519PublicKey]:
    """Carrega a chave publica Ed25519 (None se indisponivel)."""
    if not HAS_CRYPTOGRAPHY:
        return None
    pem = carregar_chave_publica_pem(caminho)
    if not pem:
        return None
    return serialization.load_pem_public_key(pem.encode("utf-8"))


# ─── Assinatura / verificacao ───────────────────────────────────────────────

def assinar_sha256(
    sha256_hex: str,
    chave_privada: Optional[Ed25519PrivateKey] = None,
    caminho_privada: Path = PRIVATE_KEY_FILE,
) -> str:
    """Assina o digest sha256 (hex) e retorna a assinatura em base64."""
    if not HAS_CRYPTOGRAPHY:
        raise RuntimeError("Biblioteca 'cryptography' nao instalada.")
    chave = chave_privada or carregar_chave_privada(caminho_privada)
    digest = bytes.fromhex(sha256_hex.strip())
    return base64.b64encode(chave.sign(digest)).decode("utf-8")


def verificar_assinatura(
    sha256_hex: str,
    assinatura_b64: str,
    chave_publica: Optional[Ed25519PublicKey] = None,
) -> bool:
    """Verifica a assinatura de um digest sha256.

    Retorna False se a assinatura for invalida, a chave ausente ou a
    biblioteca cryptography nao estiver disponivel (falha segura).
    """
    if not HAS_CRYPTOGRAPHY or not assinatura_b64:
        return False
    chave = chave_publica or carregar_chave_publica()
    if chave is None:
        return False
    try:
        digest = bytes.fromhex(sha256_hex.strip())
        chave.verify(base64.b64decode(assinatura_b64), digest)
        return True
    except Exception:
        return False


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Assinatura Ed25519 de atualizacoes.")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_gerar = sub.add_parser("gerar-chaves", help="Gera par de chaves + modulo publico")
    p_gerar.add_argument("--privado", default=str(PRIVATE_KEY_FILE), help="Arquivo .pem da privada")
    p_gerar.add_argument("--publico-modulo", default=str(PUBLIC_KEY_MODULE), help="Modulo .py da publica")

    p_assinar = sub.add_parser("assinar", help="Assina um digest sha256 (hex)")
    p_assinar.add_argument("sha256_hex", help="Digest sha256 em hex")
    p_assinar.add_argument("--privado", default=str(PRIVATE_KEY_FILE), help="Arquivo .pem da privada")

    p_verif = sub.add_parser("verificar", help="Verifica uma assinatura (base64)")
    p_verif.add_argument("sha256_hex", help="Digest sha256 em hex")
    p_verif.add_argument("assinatura_b64", help="Assinatura em base64")

    args = parser.parse_args()

    if args.comando == "gerar-chaves":
        _, pub = gerar_par_chaves(Path(args.privado), Path(args.publico_modulo))
        print(f"Chave privada: {args.privado}")
        print(f"Chave publica: {PUBLIC_KEY_FILE}")
        print(f"Modulo publico: {args.publico_modulo}")
        print("Mantenha a privada em segredo e NUNCA a commite no git.")
        return 0

    if args.comando == "assinar":
        try:
            sig = assinar_sha256(args.sha256_hex, caminho_privada=Path(args.privado))
        except RuntimeError as e:
            print(f"Erro: {e}")
            return 1
        print(sig)
        return 0

    if args.comando == "verificar":
        ok = verificar_assinatura(args.sha256_hex, args.assinatura_b64)
        print("ASSINATURA VALIDA" if ok else "ASSINATURA INVALIDA")
        return 0 if ok else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
