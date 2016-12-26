# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import regnskab.models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('regnskab', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SheetImage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('sheet', models.PositiveIntegerField()),
                ('quad', jsonfield.fields.JSONField(default=[])),
                ('cols', jsonfield.fields.JSONField(default=[])),
                ('rows', jsonfield.fields.JSONField(default=[])),
                ('person_rows', jsonfield.fields.JSONField(default=[])),
                ('crosses', jsonfield.fields.JSONField(default=[])),
                ('person_counts', jsonfield.fields.JSONField(default=[])),
            ],
        ),
        migrations.CreateModel(
            name='SheetImageStack',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('file', models.FileField(upload_to=regnskab.models.sheet_image_stack_upload)),
                ('sheets', models.PositiveIntegerField()),
            ],
        ),
        migrations.AddField(
            model_name='sheetimage',
            name='stack',
            field=models.ForeignKey(to='regnskab.SheetImageStack'),
        ),
    ]
