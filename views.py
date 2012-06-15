"""
Views for the Indivo Problems app

Ben Adida
ben.adida@childrens.harvard.edu
"""

from utils import *
import uuid

from django.utils import simplejson

def start_auth(request):
    """
    begin the oAuth protocol with the server
    
    expects either a record_id or carenet_id parameter,
    now that we are carenet-aware
    """

    # create the client to Indivo
    client = get_indivo_client(request, with_session_token=False)
    
    # do we have a record_id?
    record_id = request.GET.get('record_id', None)
    carenet_id = request.GET.get('carenet_id', None)
    
    # prepare request token parameters
    params = {'oauth_callback':'oob'}
    if record_id:
        params['indivo_record_id'] = record_id
    if carenet_id:
        params['indivo_carenet_id'] = carenet_id

    # request a request token
    req_token = client.fetch_request_token(params)

    # store the request token in the session for when we return from auth
    request.session['request_token'] = req_token
    
    # redirect to the UI server
    return HttpResponseRedirect(client.auth_redirect_url)

def after_auth(request):
    """
    after Indivo authorization, exchange the request token for an access token and store it in the web session.
    """
    # get the token and verifier from the URL parameters
    oauth_token, oauth_verifier = request.GET['oauth_token'], request.GET['oauth_verifier']
    
    # retrieve request token stored in the session
    token_in_session = request.session['request_token']
    
    # is this the right token?
    if token_in_session['oauth_token'] != oauth_token:
        return HttpResponse("oh oh bad token")
    
    # get the indivo client and use the request token as the token for the exchange
    client = get_indivo_client(request, with_session_token=False)
    client.update_token(token_in_session)
    access_token = client.exchange_token(oauth_verifier)
    
    # store stuff in the session
    request.session['access_token'] = access_token
    
    if access_token.has_key('xoauth_indivo_record_id'):
        request.session['record_id'] = access_token['xoauth_indivo_record_id']
        if request.session.has_key('carenet_id'):
            del request.session['carenet_id']
    else:
        if request.session.has_key('record_id'):
            del request.session['record_id']
        request.session['carenet_id'] = access_token['xoauth_indivo_carenet_id']
    
    # go to list of problems
    return HttpResponseRedirect(reverse(problem_list))

def test_message_send(request):
    """
    testing message send with attachments assumes record-level share
    """
    client = get_indivo_client(request)

    record_id = request.session['record_id']

    message_id = str(uuid.uuid4())
    client.message_record(record_id=record_id, message_id=message_id, data={'subject':'testing!', 'body':'testing markdown with a [link to something fun]({APP_BASE}/message?id={MESSAGE_ID})', 'num_attachments':'1', 'body_type': 'markdown'})

    # an XML doc to send
    problem_xml = render_raw('problem', {'date_onset': '2010-04-26T19:37:05.000Z', 'date_resolution': '2010-04-26T19:37:05.000Z', 'coding_system': 'snomed', 'code': '37796009', 'code_fullname':'Migraine (disorder)', 'comments': 'I\'ve had a headache waiting for alpha3.', 'diagnosed_by': 'Dr. Ken'}, type='xml')

    client.message_record_attachment(record_id=record_id, message_id=message_id, attachment_num="1", data=problem_xml)

    return HttpResponseRedirect(reverse(problem_list))

def problem_list(request):
    client = get_indivo_client(request)
    
    in_carenet = request.session.has_key('carenet_id')
    if not in_carenet:
        # get record info
        record_id = request.session['record_id']
        resp, content = client.record(record_id=record_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error reading Record info: %s"%content)
        record = parse_xml(content)
        
        # read problems
        resp, content = client.generic_list(record_id=record_id, data_model="Problem")
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error reading problems: %s"%content)
        probs = simplejson.loads(content)

    else:
        # get record info
        carenet_id = request.session['carenet_id']
        resp, content = client.carenet_record(carenet_id=carenet_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error reading Record info: %s"%content)
        record = parse_xml(content)

        # read problems from the carenet
        resp, content = client.carenet_generic_list(carenet_id=carenet_id, data_model="Problem")
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error reading problems from carenet: %s"%content)
        probs = simplejson.loads(content)
        
    probs = map(process_problem, probs)
    record_label = record.attrib['label']
    num_problems = len(probs)
    
    return render_template('list', {'record_label': record_label, 'num_problems' : num_problems, 
                                    'problems': probs, 'in_carenet':in_carenet, })

def new_problem(request):
    if request.method == "GET":
        return render_template('newproblem')
    else:

        # Fix dates formatted by JQuery into xs:dateTime                                        
        date_onset = request.POST['date_onset'] + 'T00:00:00Z' if request.POST['date_onset'] != '' else ''
        date_resolution = request.POST['date_resolution'] + 'T00:00:00Z' if request.POST['date_resolution'] != '' else ''

        # get the variables and create a problem XML
        params = {'code_abbrev':'', 
                  'coding_system': 'http://purl.bioontology.org/ontology/SNOMEDCT/', 
                  'date_onset': date_onset, 
                  'date_resolution': date_resolution, 
                  'code_fullname': request.POST['code_fullname'], 
                  'code': request.POST['code'], 
                  'comments' : request.POST['comments']}
        problem_xml = render_raw('problem', params, type='xml')
        
        # add the problem
        client = get_indivo_client(request)
        resp, content = client.document_create(record_id=request.session['record_id'], body=problem_xml, 
                                               content_type='application/xml')
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error creating new problem: %s"%content)
        
        # add a notification
        # let's not do this anymore because it's polluting the healthfeed
        # client.record_notify(record_id=request.session['record_id'], 
        #                      body={'content':'a new problem has been added to your problem list'})
        
        return HttpResponseRedirect(reverse(problem_list))

def code_lookup(request):
    client = get_indivo_client(request)
    
    query = request.GET['query']
    
    # reformat this for the jQuery autocompleter
    resp, content = client.coding_system_query(system_short_name='snomed', body={'q':query})
    if resp['status'] != '200':
        # TODO: handle errors
        # But this Indivo instance might not support codingsystem lookup, so let's pass
        pass
    codes = simplejson.loads(content)
    formatted_codes = {'query': query, 'suggestions': [c['consumer_value'] for c in codes], 'data': codes}
    
    return HttpResponse(simplejson.dumps(formatted_codes), mimetype="text/plain")

def one_problem(request, problem_id):
    client = get_indivo_client(request)
    record_id = request.session.get('record_id', None)
    
    if record_id:
        # get record info
        resp, content = client.record(record_id=record_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error reading Record info: %s"%content)
        record = parse_xml(content)
        
        # read the document
        resp, content = client.record_specific_document(record_id=record_id, document_id=problem_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error fetching document: %s"%content)
        doc_xml = content

        # read the document's metadata
        resp, content = client.record_document_meta(record_id=record_id, document_id=problem_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error fetching document metadata: %s"%content)
        doc_meta_xml = content

    else:
        # get record info
        carenet_id = request.session['carenet_id']
        resp, content = client.carenet_record(carenet_id=carenet_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error reading Record info: %s"%content)
        record = parse_xml(content)
        
        # read the document
        resp, content = client.carenet_document(carenet_id=carenet_id, document_id=problem_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error fetching document from carenet: %s"%content)
        doc_xml = content

        # read the document's metadata
        resp, content = client.carenet_document_meta(carenet_id=carenet_id, document_id=problem_id)
        if resp['status'] != '200':
            # TODO: handle errors
            raise Exception("Error fetching document metadata from carenet: %s"%content)
        doc_meta_xml = content
    
    doc = parse_xml(doc_xml)    
    problem = parse_sdmx_problem(doc, ns=True)
    
    if doc_meta_xml:
        doc_meta = parse_xml(doc_meta_xml)
        meta = parse_meta(doc_meta)
    else:
        meta = None
    
    record_label = record.attrib['label']
    surl_credentials = client.get_surl_credentials()
    
    return render_template('one', {'problem':problem, 'record_label': record_label, 'meta': meta, 'record_id': record_id, 'problem_id': problem_id, 'surl_credentials': surl_credentials})

