#!/usr/bin/env python3
"""
Gera um PDF A4 com fotos circulares prontas para impressão.

Uso:
    python fotos_circulares.py ./minhas_fotos
    python fotos_circulares.py ./minhas_fotos -o fotos_a4.pdf
    python fotos_circulares.py ./minhas_fotos --diametro 6.5 --colunas 3 --linhas 4

Dependências:
    pip install pillow reportlab

As imagens são ajustadas em recorte quadrado e inseridas em círculos.
A posição do recorte pode ser ajustada com --crop-x e --crop-y:
    0.0 = início/esquerda ou topo
    0.5 = centro
    1.0 = fim/direita ou base

Exemplo:
    Se as pessoas estiverem mais abaixo na foto, experimente --crop-y 0.62
"""

import argparse
import math
from pathlib import Path
from reportlab.lib.utils import ImageReader

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def listar_imagens(pasta: Path):
    """Lista imagens da pasta, em ordem alfabética, sem entrar em subpastas."""
    return sorted(
        (p for p in pasta.iterdir()
         if p.is_file() and p.suffix.lower() in EXTENSOES),
        key=lambda p: p.name.lower(),
    )


def preparar_imagem(caminho: Path, tamanho_px: int, crop_x: float, crop_y: float):
    """Corrige orientação EXIF e gera um recorte quadrado RGB."""
    with Image.open(caminho) as original:
        imagem = ImageOps.exif_transpose(original).convert("RGB")
        lado = min(imagem.width, imagem.height)

        # A posição do quadrado é controlada pelos parâmetros crop_x/crop_y.
        esquerda = round((imagem.width - lado) * crop_x)
        topo = round((imagem.height - lado) * crop_y)
        imagem = imagem.crop((esquerda, topo, esquerda + lado, topo + lado))
        imagem = imagem.resize((tamanho_px, tamanho_px), Image.Resampling.LANCZOS)
        return imagem


def desenhar_foto_circular(pdf, imagem, x, y, diametro_pt, nome_arquivo,
                           linha_corte=True):
    """Desenha uma imagem recortada em círculo; x/y são o canto inferior esquerdo."""
    pdf.saveState()

    caminho = pdf.beginPath()
    caminho.circle(x + diametro_pt / 2, y + diametro_pt / 2, diametro_pt / 2)
    pdf.clipPath(caminho, stroke=0, fill=0)

    # A imagem quadrada ocupa exatamente o círculo de recorte.
    from io import BytesIO

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    buffer.seek(0)

    imagem_reader = ImageReader(buffer)

    pdf.drawImage(
        imagem_reader,
        x, y,
        width=diametro_pt,
        height=diametro_pt,
        preserveAspectRatio=False,
        mask="auto",
    )
    
    pdf.restoreState()

    # Linha fina para facilitar o corte manual.
    if linha_corte:
        pdf.saveState()
        pdf.setLineWidth(0.35)
        pdf.setStrokeGray(0.45)
        pdf.circle(x + diametro_pt / 2, y + diametro_pt / 2,
                   diametro_pt / 2, stroke=1, fill=0)
        pdf.restoreState()


def gerar_pdf(args):
    pasta = Path(args.pasta).expanduser().resolve()
    if not pasta.exists() or not pasta.is_dir():
        raise SystemExit(f"Erro: a pasta não existe: {pasta}")

    arquivos = listar_imagens(pasta)
    if not arquivos:
        raise SystemExit(f"Nenhuma imagem encontrada em: {pasta}")

    if not (0 <= args.crop_x <= 1 and 0 <= args.crop_y <= 1):
        raise SystemExit("crop-x e crop-y devem estar entre 0 e 1.")

    largura_pagina, altura_pagina = A4
    diametro = args.diametro * cm
    espacamento = args.espacamento * cm
    colunas = args.colunas
    linhas = args.linhas

    if colunas < 1 or linhas < 1:
        raise SystemExit("Linhas e colunas devem ser maiores que zero.")

    largura_grade = colunas * diametro + (colunas - 1) * espacamento
    altura_grade = linhas * diametro + (linhas - 1) * espacamento

    if largura_grade > largura_pagina or altura_grade > altura_pagina:
        raise SystemExit(
            "A grade não cabe na folha A4. Reduza o diâmetro/espacamento "
            "ou a quantidade de linhas/colunas."
        )

    saida = Path(args.saida).expanduser()
    if not saida.is_absolute():
        saida = Path.cwd() / saida
    saida.parent.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(str(saida), pagesize=A4)
    pdf.setTitle("Fotos circulares para impressão")
    pdf.setAuthor("Gerado com fotos_circulares.py")

    por_pagina = colunas * linhas
    total_paginas = math.ceil(len(arquivos) / por_pagina)

    # Centraliza a grade na folha A4.
    margem_x = (largura_pagina - largura_grade) / 2
    margem_y = (altura_pagina - altura_grade) / 2

    for indice, arquivo in enumerate(arquivos):
        posicao = indice % por_pagina
        if indice > 0 and posicao == 0:
            pdf.showPage()

        coluna = posicao % colunas
        linha = posicao // colunas

        x = margem_x + coluna * (diametro + espacamento)
        y = altura_pagina - margem_y - diametro - linha * (diametro + espacamento)

        try:
            imagem = preparar_imagem(
                arquivo, args.resolucao, args.crop_x, args.crop_y
            )
            desenhar_foto_circular(
                pdf, imagem, x, y, diametro, arquivo.name,
                linha_corte=not args.sem_linha
            )
            print(f"[OK] {arquivo.name}")
        except Exception as erro:
            print(f"[ERRO] {arquivo.name}: {erro}")

    pdf.save()
    print()
    print(f"PDF criado: {saida}")
    print(f"Fotos encontradas: {len(arquivos)}")
    print(f"Layout: {colunas} coluna(s) x {linhas} linha(s) por página")
    print(f"Diâmetro: {args.diametro:.2f} cm")
    print(f"Resolução do recorte: {args.resolucao} x {args.resolucao} px")
    print(f"Páginas previstas: {total_paginas}")


def main():
    parser = argparse.ArgumentParser(
        description="Organiza fotos em círculos de tamanho definido numa folha A4."
    )
    parser.add_argument("pasta", help="Pasta que contém as fotos.")
    parser.add_argument(
        "-o", "--saida", default="fotos_circulares_A4.pdf",
        help="Nome/caminho do PDF de saída (padrão: fotos_circulares_A4.pdf)."
    )
    parser.add_argument(
        "--diametro", type=float, default=6.5,
        help="Diâmetro de cada foto em centímetros (padrão: 6.5)."
    )
    parser.add_argument(
        "--colunas", type=int, default=3,
        help="Quantidade de fotos por linha (padrão: 3)."
    )
    parser.add_argument(
        "--linhas", type=int, default=4,
        help="Quantidade de linhas por página (padrão: 4)."
    )
    parser.add_argument(
        "--espacamento", type=float, default=0.3,
        help="Espaço entre círculos, em centímetros (padrão: 0.3)."
    )
    parser.add_argument(
        "--crop-x", type=float, default=0.5,
        help="Posição horizontal do recorte: 0=esquerda, 0.5=centro, 1=direita."
    )
    parser.add_argument(
        "--crop-y", type=float, default=0.5,
        help="Posição vertical do recorte: 0=topo, 0.5=centro, 1=base."
    )
    parser.add_argument(
        "--resolucao", type=int, default=768,
        help="Resolução em pixels do recorte quadrado (padrão: 768, adequado a 300 DPI)."
    )
    parser.add_argument(
        "--sem-linha", action="store_true",
        help="Não desenha a linha circular de orientação para o corte."
    )

    args = parser.parse_args()
    if args.diametro <= 0 or args.espacamento < 0 or args.resolucao < 1:
        parser.error("Diâmetro/resolução devem ser positivos e espaçamento não pode ser negativo.")
    gerar_pdf(args)


if __name__ == "__main__":
    main()
