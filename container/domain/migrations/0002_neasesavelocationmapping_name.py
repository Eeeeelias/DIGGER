# Generated by Django 2.2.28 on 2024-09-09 13:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='neasesavelocationmapping',
            name='name',
            field=models.CharField(default='', max_length=255),
        ),
    ]
