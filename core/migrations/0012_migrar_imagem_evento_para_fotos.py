from django.db import migrations


def imagem_para_fotos(apps, schema_editor):
    """A imagem única de cada evento vira a primeira foto da galeria (o arquivo é o mesmo)."""
    Evento = apps.get_model("core", "Evento")
    FotoEvento = apps.get_model("core", "FotoEvento")
    for evento in Evento.objects.exclude(imagem=""):
        FotoEvento.objects.create(evento=evento, imagem=evento.imagem.name, ordem=0)


def fotos_para_imagem(apps, schema_editor):
    Evento = apps.get_model("core", "Evento")
    FotoEvento = apps.get_model("core", "FotoEvento")
    for foto in FotoEvento.objects.filter(ordem=0):
        Evento.objects.filter(pk=foto.evento_id).update(imagem=foto.imagem.name)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_fotos_evento'),
    ]

    operations = [
        migrations.RunPython(imagem_para_fotos, fotos_para_imagem),
        migrations.RemoveField(model_name='evento', name='imagem'),
    ]
