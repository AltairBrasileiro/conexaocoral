"""Listas em PDF (ReportLab): presença em evento e passageiros da Carona Coral."""
from __future__ import annotations

import io
from html import escape
from collections.abc import Sequence

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.models import Carona, Evento, PresencaEvento, ReservaCarona
from web.templatetags.coral import dia_hora, hora

PRETO = colors.HexColor("#0B0B0B")
VERMELHO = colors.HexColor("#E30613")
CINZA = colors.HexColor("#5F5F5F")
BORDA = colors.HexColor("#E4E4E4")
FUNDO = colors.HexColor("#F7F7F7")

TITULO = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=PRETO)
SUBTITULO = ParagraphStyle("subtitulo", fontName="Helvetica", fontSize=10.5, leading=14, textColor=CINZA)
CELULA = ParagraphStyle("celula", fontName="Helvetica", fontSize=8.5, leading=10.5, alignment=TA_LEFT)


def _telefone(numero: str) -> str:
    """"+5583999990000" -> "+55 (83) 99999-0000" (outros formatos ficam como estão)."""
    digitos = numero.lstrip("+")
    if numero.startswith("+55") and len(digitos) in (12, 13) and digitos.isdigit():
        ddd, resto = digitos[2:4], digitos[4:]
        return f"+55 ({ddd}) {resto[:-4]}-{resto[-4:]}"
    return numero or "—"


def _faixa(canvas, documento, rotulo: str = "Lista de presença") -> None:
    """Cabeçalho preto → branco → vermelho e rodapé com página, em todas as páginas."""
    largura, altura = A4
    canvas.saveState()
    canvas.setFillColor(PRETO)
    canvas.rect(0, altura - 16 * mm, largura, 16 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(18 * mm, altura - 10.5 * mm, "Conexão Coral")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(largura - 18 * mm, altura - 10.5 * mm, rotulo)
    # Branco entre o preto e o vermelho, como nas listras do uniforme.
    canvas.setFillColor(VERMELHO)
    canvas.rect(0, altura - 19.5 * mm, largura, 2 * mm, stroke=0, fill=1)
    canvas.setFillColor(CINZA)
    canvas.setFont("Helvetica", 8)
    gerado = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    canvas.drawString(18 * mm, 10 * mm, f"Gerado em {gerado}")
    canvas.drawRightString(largura - 18 * mm, 10 * mm, f"Página {documento.page}")
    canvas.restoreState()


def lista_de_presenca(evento: Evento, presencas: Sequence[PresencaEvento]) -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=28 * mm, bottomMargin=18 * mm,
        title=f"Lista de presença - {evento.titulo}", author="Conexão Coral",
    )
    vagas = f"{len(presencas)} de {evento.limite_vagas} vagas" if evento.limite_vagas else f"{len(presencas)} confirmados"
    conteudo = [
        Paragraph(escape(evento.titulo), TITULO),
        Spacer(1, 2 * mm),
        Paragraph(escape(evento.consulado.nome), SUBTITULO),
        Paragraph(f"{dia_hora(evento.data_hora_inicio)} até {hora(evento.data_hora_fim)}", SUBTITULO),
        Paragraph(
            f"{vagas} · {'Exclusivo para membros' if evento.exclusivo_membros else 'Aberto a todos os torcedores'}",
            SUBTITULO,
        ),
        Spacer(1, 7 * mm),
    ]

    linhas = [["#", "Nome", "E-mail", "Telefone", "Confirmou em", "Presente"]]  # 174 mm = A4 sem margens
    for numero, presenca in enumerate(presencas, start=1):
        usuario = presenca.usuario
        linhas.append([
            str(numero),
            Paragraph(escape(usuario.nome), CELULA),
            Paragraph(escape(usuario.email), CELULA),
            _telefone(usuario.telefone),
            timezone.localtime(presenca.data_confirmacao).strftime("%d/%m/%y %H:%M"),
            "",  # coluna em branco para marcar a presença no dia
        ])
    if not presencas:
        linhas.append(["", Paragraph("Ninguém confirmou presença ainda.", CELULA), "", "", "", ""])

    tabela = Table(linhas, colWidths=[8 * mm, 42 * mm, 49 * mm, 32 * mm, 25 * mm, 18 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRETO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (5, 0), (5, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDA),
        ("BOX", (5, 1), (5, -1), 0.5, BORDA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    conteudo.append(tabela)
    documento.build(conteudo, onFirstPage=_faixa, onLaterPages=_faixa)
    return buffer.getvalue()


def _faixa_carona(canvas, documento) -> None:
    _faixa(canvas, documento, "Carona Coral")


def lista_da_carona(carona: Carona, reservas: Sequence[ReservaCarona]) -> bytes:
    """Passageiros da carona com coluna de check-in (horário registrado ou caixa para marcar)."""
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=28 * mm, bottomMargin=18 * mm,
        title=f"Carona Coral - {carona.motorista.nome}", author="Conexão Coral",
    )
    embarcados = sum(1 for r in reservas if r.checkin_em)
    conteudo = [
        Paragraph(f"Carona de {escape(carona.motorista.nome)}", TITULO),
        Spacer(1, 2 * mm),
        Paragraph(escape(carona.consulado.nome), SUBTITULO),
        Paragraph(f"Encontro: {dia_hora(carona.data_hora_encontro)}", SUBTITULO),
        Paragraph(
            f"{len(reservas)} de {carona.vagas} vagas reservadas · {embarcados} check-in(s) feito(s)", SUBTITULO,
        ),
        Spacer(1, 3 * mm),
        Paragraph(escape(carona.descricao).replace("\n", "<br/>"), CELULA),
        Spacer(1, 6 * mm),
    ]

    linhas = [["#", "Passageiro", "E-mail", "Telefone", "Reservou em", "Check-in"]]
    for numero, reserva in enumerate(reservas, start=1):
        usuario = reserva.usuario
        linhas.append([
            str(numero),
            Paragraph(escape(usuario.nome), CELULA),
            Paragraph(escape(usuario.email), CELULA),
            _telefone(usuario.telefone),
            timezone.localtime(reserva.reservado_em).strftime("%d/%m/%y %H:%M"),
            hora(reserva.checkin_em) if reserva.checkin_em else "",  # em branco: marcar à mão no dia
        ])
    if not reservas:
        linhas.append(["", Paragraph("Nenhuma vaga reservada ainda.", CELULA), "", "", "", ""])

    tabela = Table(linhas, colWidths=[8 * mm, 42 * mm, 49 * mm, 32 * mm, 25 * mm, 18 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRETO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (5, 0), (5, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDA),
        ("BOX", (5, 1), (5, -1), 0.5, BORDA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    conteudo.append(tabela)
    documento.build(conteudo, onFirstPage=_faixa_carona, onLaterPages=_faixa_carona)
    return buffer.getvalue()
