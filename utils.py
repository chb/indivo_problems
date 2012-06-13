"""
utility functions for the views

Ben Adida
ben.adida@childrens.harvard.edu
"""

from lxml import etree as ET
import cgi, datetime

from indivo_client_py import IndivoClient

# settings including where to find Indivo
import settings

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.exceptions import *
from django.core.urlresolvers import reverse
from django.db import transaction
from django.template import Context, loader


def get_indivo_client(request, with_session_token=True):
    server_params = {"api_base": settings.INDIVO_SERVER_LOCATION,
                     "authorization_base": settings.INDIVO_UI_SERVER_BASE}
    consumer_params = settings.INDIVO_SERVER_OAUTH
    token = request.session['access_token'] if with_session_token else None
    client = IndivoClient(server_params, consumer_params, resource_token=token)
    return client

def parse_token_from_response(resp):
    token = cgi.parse_qs(resp.response['response_data'])
    for k, v in token.iteritems():
        token[k] = v[0]
    return token

MIME_TYPES = {'html': 'text/html',
              'xml': 'application/xml'}

def render_raw(template_name, vars, type):
  """
  rendering a template into a string
  """
  t_obj = loader.get_template('%s/%s.%s' % (settings.TEMPLATE_PREFIX,template_name, type))
  c_obj = Context(vars)
  return t_obj.render(c_obj)

def render_template(template_name, vars={}, type="html"):
  """
  rendering a template into a Django HTTP response
  with proper mimetype
  """

  new_vars = {'INDIVO_UI_SERVER_BASE': settings.INDIVO_UI_SERVER_BASE,
              'CB': datetime.datetime.now().isoformat(),
              'STATIC_HOME': settings.STATIC_HOME}
  new_vars.update(vars)

  content = render_raw(template_name, new_vars, type="html")

  mimetype = MIME_TYPES[type]

  return HttpResponse(content, mimetype=mimetype)

def parse_xml(xml_string):
  return ET.XML(xml_string)

NS = "{http://indivo.org/vocab/xml/documents#}"

def parse_meta(etree):
    return {'document_id': etree.attrib['id'], 'created_at' : etree.findtext('createdAt')}

def parse_sdmx_problem(etree, ns=False):
    def _t(tag):
        return NS+tag if ns else tag
    new_problem = {}
    for field in etree.find(_t('Model')).findall(_t('Field')):
        new_problem[field.get('name', None)] = field.text
    return new_problem

def process_problem(problem):
    problem['id'] = problem['__documentid__']
    del problem['__documentid__']
    return problem
