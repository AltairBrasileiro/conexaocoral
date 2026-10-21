"""
Rotas da interface web (templates Django + login por sessão).

    /                                       mapa de consulados
    entrar/ | sair/                         login e logout
    consulados/{id}/                        detalhes, check-in e eventos
    consulados/{id}/checkin/                POST faz check-in no próximo jogo
    checkins/{id}/cancelar/                 POST cancela o check-in
    eventos/{id}/confirmar/                 POST confirma presença
    partidas/                               calendário (?periodo=anteriores)
    aliados/                                vitrine (?categoria=BAR&q=...)
    painel/                                 painel do responsável (?consulado=id)
    painel/consulados/{id}/editar/          dados do bar/sede
    painel/consulados/{id}/eventos/novo/    novo evento
"""
from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.consulados, name="consulados"),
    path("entrar/", views.EntrarView.as_view(), name="login"),
    path("sair/", views.SairView.as_view(), name="logout"),
    path("consulados/<int:pk>/", views.consulado_detalhe, name="consulado"),
    path("consulados/<int:pk>/checkin/", views.fazer_checkin, name="fazer-checkin"),
    path("checkins/<int:pk>/cancelar/", views.cancelar_checkin, name="cancelar-checkin"),
    path("eventos/<int:pk>/confirmar/", views.confirmar_presenca, name="confirmar-presenca"),
    path("partidas/", views.partidas, name="partidas"),
    path("aliados/", views.aliados, name="aliados"),
    path("painel/", views.painel, name="painel"),
    path("painel/consulados/<int:pk>/editar/", views.editar_consulado, name="editar-consulado"),
    path("painel/consulados/<int:pk>/eventos/novo/", views.novo_evento, name="novo-evento"),
]
