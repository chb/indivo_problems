"""
utility functions for the views

Ben Adida
ben.adida@childrens.harvard.edu
"""

from xml.etree import ElementTree
import cgi, datetime

from indivo_client_py.lib.client import IndivoClient

# settings including where to find Indivo
import settings

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.exceptions import *
from django.core.urlresolvers import reverse
from django.db import transaction
from django.template import Context, loader


def get_indivo_client(request, with_session_token=True):
    client = IndivoClient(settings.INDIVO_SERVER_OAUTH['consumer_key'], settings.INDIVO_SERVER_OAUTH['consumer_secret'], settings.INDIVO_SERVER_LOCATION)
    if with_session_token:
        client.update_token(request.session['access_token'])
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
  return ElementTree.fromstring(xml_string)

NS = "{http://indivo.org/vocab/xml/documents#}"

def parse_meta(etree):
    if hasattr(etree, 'attrib'):
        return {'document_id': etree.attrib['id'], 'created_at' : etree.findtext('createdAt')}
    else:
        # this is an error condition
        # raise Exception("no meta information about this report")
        # FIXME: temporary hack
        return {'document_id': 'foobar', 'created_at' : '2010-03-01'}

def parse_problem(etree):
    new_problem = {'date_onset' : etree.findtext('%sdateOnset' % NS),
                   'date_resolution' : etree.findtext('%sdateResolution' % NS),
                   'name': etree.findtext('%sname' % NS),
                   'comments': etree.findtext('%scomments' % NS),
                   'diagnosed_by': etree.findtext('%sdiagnosedBy' % NS)}
    return new_problem
