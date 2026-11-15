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
    conta/                                  minha conta: dados pessoais, foto, senha, consulados, pedidos e eventos
    conta/dados/ | foto/ | foto/remover/ | senha/  POST atualiza os dados, a foto e a senha
    senha/esqueci/ | esqueci/enviado/       "esqueci a senha": pede o link por e-mail
    senha/redefinir/{uid}/{token}/ | senha/redefinida/  cadastra a nova senha pelo link
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
    painel/consulados/{id}/caronas/nova/    Carona Coral: oferecer (admin, embaixador, membro com cargo)
    painel/caronas/{id}/editar/ | excluir/  edição e exclusão (quem oferece, embaixador, admin)
    painel/caronas/{id}/passageiros/        passageiros e check-in
    painel/caronas/{id}/passageiros.pdf     a mesma lista em PDF
    painel/reservas-carona/{id}/checkin/ | retirar/ | readmitir/  POST check-in (ou desfazer) / retirar / readmitir
    caronas/{id}/reservar/ | cancelar/      POST membro reserva / cancela a própria vaga
    painel/consulados/{id}/icone/ | icone/remover/  ícone do consulado, o pino do mapa (embaixador, membro com cargo, admin)
    aliados/meus/ | novo/                   lojista: meus negócios e novo cadastro
    aliados/{id}/editar/ | excluir/         o dono edita / exclui o próprio negócio
    painel/negocios/                        admin: aprova, recusa, dá o selo e remove negócios da vitrine
    painel/usuarios/                        admin: busca contas, troca o papel e bloqueia/libera o acesso
    painel/partidas/ | nova/ | {id}/editar/ | {id}/excluir/  admin: calendário de partidas
"""
from django.urls import path

from web import views, views_admin, views_aliados

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
    path("conta/dados/", views.atualizar_perfil, name="atualizar-perfil"),
    path("conta/foto/", views.foto_perfil, name="foto-perfil"),
    path("conta/foto/remover/", views.remover_foto_perfil, name="remover-foto-perfil"),
    path("conta/senha/", views.trocar_senha, name="trocar-senha"),
    path("senha/esqueci/", views.EsqueciSenhaView.as_view(), name="senha-esqueci"),
    path("senha/esqueci/enviado/", views.SenhaEnviadaView.as_view(), name="senha-enviada"),
    path("senha/redefinir/<uidb64>/<token>/", views.RedefinirSenhaView.as_view(), name="senha-redefinir"),
    path("senha/redefinida/", views.SenhaRedefinidaView.as_view(), name="senha-redefinida"),
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
    path("painel/consulados/<int:pk>/caronas/nova/", views.nova_carona, name="nova-carona"),
    path("painel/caronas/<int:pk>/editar/", views.editar_carona, name="editar-carona"),
    path("painel/caronas/<int:pk>/excluir/", views.excluir_carona, name="excluir-carona"),
    path("painel/caronas/<int:pk>/passageiros/", views.passageiros_carona, name="passageiros-carona"),
    path("painel/caronas/<int:pk>/passageiros.pdf", views.passageiros_carona_pdf, name="passageiros-carona-pdf"),
    path("painel/reservas-carona/<int:pk>/checkin/", views.checkin_carona, name="checkin-carona"),
    path("painel/reservas-carona/<int:pk>/retirar/", views.retirar_passageiro, name="retirar-passageiro"),
    path("painel/reservas-carona/<int:pk>/readmitir/", views.readmitir_passageiro, name="readmitir-passageiro"),
    path("caronas/<int:pk>/reservar/", views.reservar_carona, name="reservar-carona"),
    path("caronas/<int:pk>/cancelar/", views.cancelar_reserva_carona, name="cancelar-reserva-carona"),
    # Ícone do consulado (pino do mapa)
    path("painel/consulados/<int:pk>/icone/", views.icone_consulado, name="icone-consulado"),
    path("painel/consulados/<int:pk>/icone/remover/", views.remover_icone_consulado, name="remover-icone-consulado"),
    # Lojista: meus negócios na Vitrine da Torcida
    path("aliados/meus/", views_aliados.meus_negocios, name="meus-negocios"),
    path("aliados/novo/", views_aliados.novo_negocio, name="novo-negocio"),
    path("aliados/<int:pk>/editar/", views_aliados.editar_negocio, name="editar-negocio"),
    path("aliados/<int:pk>/excluir/", views_aliados.excluir_negocio, name="excluir-negocio"),
    # Administração
    path("painel/negocios/", views_admin.negocios, name="admin-negocios"),
    path("painel/negocios/<int:pk>/moderar/", views_admin.moderar_negocio, name="admin-moderar-negocio"),
    path("painel/usuarios/", views_admin.usuarios, name="admin-usuarios"),
    path("painel/usuarios/<int:pk>/papel/", views_admin.papel_usuario, name="admin-papel-usuario"),
    path("painel/usuarios/<int:pk>/acesso/", views_admin.acesso_usuario, name="admin-acesso-usuario"),
    path("painel/partidas/", views_admin.partidas, name="admin-partidas"),
    path("painel/partidas/nova/", views_admin.nova_partida, name="admin-nova-partida"),
    path("painel/partidas/<int:pk>/editar/", views_admin.editar_partida, name="admin-editar-partida"),
    path("painel/partidas/<int:pk>/excluir/", views_admin.excluir_partida, name="admin-excluir-partida"),
]
