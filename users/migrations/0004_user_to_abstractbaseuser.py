"""
Switch `users.User` from a plain `models.Model` to
`AbstractBaseUser + PermissionsMixin` so SimpleJWT can authenticate it.

This migration is paired with the auth swap landed on 2026-05-21:
Keycloak -> djangorestframework-simplejwt. The model gains the standard
Django auth fields (`password`, `last_login`, `is_superuser`,
`is_active`, `is_staff`, and the `groups` / `user_permissions` M2Ms),
plus a custom `UserManager`. Existing rows (Keycloak-imported) get an
empty password string, which Django treats as unusable for password
login — meaning a forced reset/registration is required to set one.
"""

import django.contrib.auth.models
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import users.models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('users', '0003_guestsession'),
    ]

    operations = [
        # ---- New auth fields from AbstractBaseUser + PermissionsMixin ----
        migrations.AddField(
            model_name='user',
            name='password',
            # Default '' so the AddField doesn't prompt mid-migrate on an
            # existing DB; the model's manager calls `set_unusable_password`
            # for any user created without a real password.
            field=models.CharField(default='', max_length=128, verbose_name='password'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='user',
            name='last_login',
            field=models.DateTimeField(blank=True, null=True, verbose_name='last login'),
        ),
        migrations.AddField(
            model_name='user',
            name='is_superuser',
            field=models.BooleanField(
                default=False,
                help_text='Designates that this user has all permissions without explicitly assigning them.',
                verbose_name='superuser status',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='groups',
            field=models.ManyToManyField(
                blank=True,
                help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
                related_name='user_set',
                related_query_name='user',
                to='auth.group',
                verbose_name='groups',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='user_permissions',
            field=models.ManyToManyField(
                blank=True,
                help_text='Specific permissions for this user.',
                related_name='user_set',
                related_query_name='user',
                to='auth.permission',
                verbose_name='user permissions',
            ),
        ),
        # ---- Loosen now-optional fields ----
        migrations.AlterField(
            model_name='user',
            name='first_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='user',
            name='last_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, max_length=20),
        ),
        # ---- Swap the manager ----
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('objects', users.models.UserManager()),
            ],
        ),
    ]
