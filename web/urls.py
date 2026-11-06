"""
Rotas da interface web (templates Django + login por sessão).

    /                                       mapa de consulados
    entrar/ | sair/                         login e logout
    consulados/{id}/                        detalhes, equipe, próximo jogo e eventos
    eventos/{id}/confirmar/                 POST confirma presença
    partidas/                               calendário (?periodo=anteriores)
    aliados/                                vitrine (?categoria=BAR&q=...)
    painel/                                 painel do responsável (?consulado=id)
    painel/consulados/{id}/editar/          dados do bar/sede
    painel/consulados/{id}/eventos/novo/    novo evento
    painel/consulados/{id}/membros/         membros: cadastro, cargos e remoção
    painel/eventos/{id}/editar/ | excluir/  edição e exclusão de evento
    painel/solicitacoes/                    admin aceita/recusa novos consulados
    consulados/solicitar/                   torcedor solicita cadastro de consulado
    consulados/{id}/entrar/ | sair/         POST pede para ser membro / sai do consulado
    pedidos-entrada/{id}/cancelar/          POST cancela o próprio pedido de entrada
    painel/pedidos-entrada/{id}/responder/  POST embaixador aprova ou recusa a entrada
    conta/                                  minha conta: consulados, pedidos e eventos
    eventos/{id}/desmarcar/                 POST o torcedor desmarca a própria presença
    painel/eventos/{id}/confirmados/        lista de confirmados (embaixador, membro com cargo, admin)
    painel/eventos/{id}/confirmados.pdf     a mesma lista em PDF
    painel/presencas/{id}/remover/          POST tira uma pessoa da lista (ela não confirma de novo)
    painel/presencas/{id}/readmitir/        POST devolve à lista quem foi retirado
    reportar/                               problema ou sugestão (qualquer usuário; só admins veem)
    painel/reportes/                        admin: lista, resolve e reabre os reportes
    apoie/                                  contribuição financeira via Pix
    painel/consulados/{id}/fotos/           fotos: enviar (embaixador ou membro com cargo)
    painel/fotos/{id}/legenda/|capa/|remover/  POST editar legenda, definir capa, remover
"""
from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.consulados, name="consulados"),
    path("entrar/", views.EntrarView.as_view(), name="login"),
    path("sair/", views.SairView.as_view(), name="logout"),
    path("consulados/<int:pk>/", views.consulado_detalhe, name="consulado"),
    path("eventos/<int:pk>/confirmar/", views.confirmar_presenca, name="confirmar-presenca"),
    path("partidas/", views.partidas, name="partidas"),
    path("aliados/", views.aliados, name="aliados"),
    path("painel/", views.painel, name="painel"),
    path("painel/consulados/<int:pk>/editar/", views.editar_consulado, name="editar-consulado"),
    path("painel/consulados/<int:pk>/eventos/novo/", views.novo_evento, name="novo-evento"),
    path("painel/consulados/<int:pk>/membros/", views.membros, name="membros"),
    path("painel/membros/<int:pk>/cargo/", views.definir_cargo, name="definir-cargo"),
    path("painel/membros/<int:pk>/remover/", views.remover_membro, name="remover-membro"),
    path("painel/eventos/<int:pk>/editar/", views.editar_evento, name="editar-evento"),
    path("painel/eventos/<int:pk>/excluir/", views.excluir_evento, name="excluir-evento"),
    path("painel/solicitacoes/", views.solicitacoes, name="solicitacoes"),
    path("painel/solicitacoes/<int:pk>/aprovar/", views.aprovar_solicitacao, name="aprovar-solicitacao"),
    path("painel/solicitacoes/<int:pk>/rejeitar/", views.rejeitar_solicitacao, name="rejeitar-solicitacao"),
    path("consulados/solicitar/", views.solicitar_consulado, name="solicitar-consulado"),
    path("consulados/<int:pk>/entrar/", views.solicitar_entrada, name="solicitar-entrada"),
    path("consulados/<int:pk>/sair/", views.sair_do_consulado, name="sair-do-consulado"),
    path("pedidos-entrada/<int:pk>/cancelar/", views.cancelar_pedido_entrada, name="cancelar-pedido-entrada"),
    path("painel/pedidos-entrada/<int:pk>/responder/", views.responder_pedido_entrada, name="responder-pedido-entrada"),
    path("conta/", views.minha_conta, name="minha-conta"),
    path("eventos/<int:pk>/desmarcar/", views.desmarcar_presenca, name="desmarcar-presenca"),
    path("painel/eventos/<int:pk>/confirmados/", views.presencas_evento, name="presencas-evento"),
    path("painel/eventos/<int:pk>/confirmados.pdf", views.presencas_evento_pdf, name="presencas-evento-pdf"),
    path("painel/presencas/<int:pk>/remover/", views.remover_presenca_evento, name="remover-presenca"),
    path("painel/presencas/<int:pk>/readmitir/", views.readmitir_presenca_evento, name="readmitir-presenca"),
    path("reportar/", views.reportar, name="reportar"),
    path("painel/reportes/", views.reportes, name="reportes"),
    path("painel/reportes/<int:pk>/responder/", views.responder_reporte, name="responder-reporte"),
    path("apoie/", views.apoie, name="apoie"),
    path("painel/consulados/<int:pk>/fotos/", views.fotos_consulado, name="fotos-consulado"),
    path("painel/fotos/<int:pk>/legenda/", views.legenda_foto, name="legenda-foto"),
    path("painel/fotos/<int:pk>/capa/", views.capa_foto, name="capa-foto"),
    path("painel/fotos/<int:pk>/remover/", views.remover_foto, name="remover-foto"),
]
