# SPDX-FileCopyrightText: (C) 2021 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import time
from scene_common import log
from django.core.management.base import BaseCommand
from django.conf import settings
import manager.models
from django.db.models.base import ModelBase
from django.db import connection

class Command(BaseCommand):
  def fullExceptionName(self, ex):
    name = ex.__class__.__name__
    module = ex.__class__.__module__
    if module is not None and module != str.__class__.__module__:
      name = module + "." + name
    return name

  def handle(self, *args, **options):
    while True:
      try:
        print(settings.DATABASES['default']['NAME'])
        print(settings.DATABASES['default']['USER'])
        print(settings.DATABASES['default']['HOST'])
        print(settings.DATABASES['default']['PASSWORD'])

        with connection.cursor() as cursor:
          cursor.execute("SELECT 1;")  # simple test query

        tables_av = {}
        log.info("Waiting for tables")

        # Check that tables exist
        for model, obj in manager.models.__dict__.items():
          if isinstance(obj, ModelBase):
            try:
              data_av = obj.objects.all()
              if model not in tables_av:
                tables_av[model] = len(data_av)
            except Exception:
              # table might not exist yet
              log.info(f"Table for model {model} not ready yet")

        time.sleep(10)
        log.info("Waiting for data")

        # Wait until table data stabilizes
        tables_updated = True
        while tables_updated:
          tables_updated = False
          for model, obj in manager.models.__dict__.items():
            if isinstance(obj, ModelBase):
              try:
                table_count = obj.objects.count()
                if model not in tables_av or table_count != tables_av[model]:
                  tables_av[model] = table_count
                  tables_updated = True
              except Exception:
                log.info(f"Skipping model {model}, table not ready yet")

          if tables_updated:
            time.sleep(0.5)

        log.info("Database ready")
        break

      except Exception as ex:
        log.error("W4DB ERROR", self.fullExceptionName(ex), ex)
        time.sleep(2)
