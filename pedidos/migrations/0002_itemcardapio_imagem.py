from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemcardapio",
            name="imagem",
            field=models.ImageField(
                blank=True,
                help_text="Opcional. Sem foto, o site mostra uma ilustração do item.",
                upload_to="cardapio/",
                verbose_name="foto",
            ),
        ),
    ]
