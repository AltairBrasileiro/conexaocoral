from django.db import migrations, models


def publicar_eventos_pendentes(apps, schema_editor):
    """Eventos deixaram de passar por moderação: os que aguardavam aprovação são publicados."""
    Evento = apps.get_model("core", "Evento")
    Evento.objects.filter(status_aprovacao="PENDENTE").update(status_aprovacao="APROVADO")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_logo_consulado'),
    ]

    operations = [
        migrations.AddField(
            model_name='membroconsulado',
            name='cargo',
            field=models.CharField(blank=True, max_length=60, verbose_name='cargo'),
        ),
        migrations.AddField(
            model_name='consulado',
            name='motivo_rejeicao',
            field=models.TextField(blank=True, verbose_name='motivo da rejeição'),
        ),
        migrations.RunPython(publicar_eventos_pendentes, migrations.RunPython.noop),
    ]
