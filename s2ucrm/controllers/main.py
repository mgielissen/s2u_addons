# -*- coding: utf-8 -*-

import json
import base64
import werkzeug.urls
import sys
import os

from odoo import http
from odoo.http import request
from odoo import models
from odoo.addons.website.models.website import slugify

from odoo.modules import get_module_resource
from odoo.addons.web.controllers.main import binary_content
from odoo import tools, SUPERUSER_ID
from odoo.tools.image import image_resize_image
from odoo.tools.translate import _


class CRMController(http.Controller):

    @http.route(['/crm/logo/<string:entity_id>/<string:entity_code>'], type='http', auth='public', website=True)
    def get_entity_logo(self, entity_id=None, entity_code=None):

        try:
            entity_id = int(entity_id)
        except:
            entity_id = -1

        entity_model = request.env['s2u.crm.entity']
        if entity_id > 0:
            entity = entity_model.sudo().search([('id', '=', entity_id),
                                                 ('entity_code', '=', entity_code)])
            if not entity:
                entity_id = -1
        status, headers, content = binary_content(model='s2u.crm.entity', id=entity_id, field='image',
                                                  default_mimetype='image/jpeg',
                                                  env=request.env(user=SUPERUSER_ID))

        if not content:
            return request.render("website.404")

        if status == 304:
            return werkzeug.wrappers.Response(status=304)
        image_base64 = base64.b64decode(content)

        headers.append(('Content-Length', len(image_base64)))
        response = request.make_response(image_base64, headers)
        response.status = str(status)
        return response
