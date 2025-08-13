# SPDX-FileCopyrightText: (C) 2024 - 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import traceback

from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token

from scene_common import log

class Custom500Middleware:
  def __init__(self, get_response):
    self.get_response = get_response
    return

  def __call__(self, request):
    response = self.get_response(request)
    return response

  def process_exception(self, request, exception):
    error_message = traceback.format_exc()
    log.error(error_message)
    response = render(request, 'sscape/500_error.html', {
      'error_message': error_message,
      'request_info': self._stringify_request(request),
    })
    response.status_code = 500
    return response

  def _stringify_request(self, request):
    request_data = {
      'method': request.method,
      'path': request.path,
      'GET': request.GET.dict(),
      'POST': request.POST.dict(),
      'headers': {k: v for k, v in request.headers.items()},
    }
    return json.dumps(request_data, indent=2)

class TokenAuthMiddleware(MiddlewareMixin):
  def process_request(self, request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Token '):
      token_key = auth_header.split(' ')[1]
      try:
          token = Token.objects.select_related('user').get(key=token_key)
          request.user = token.user
      except Token.DoesNotExist:
            request.user = AnonymousUser()
    return
