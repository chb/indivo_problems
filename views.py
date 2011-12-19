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
    
    params['offline'] = 1
    
    # request a request token
    request_token = parse_token_from_response(client.post_request_token(data=params))
    
    # store the request token in the session for when we return from auth
    request.session['request_token'] = request_token
    
    # redirect to the UI server
    return HttpResponseRedirect(settings.INDIVO_UI_SERVER_BASE + '/oauth/authorize?oauth_token=%s' % request_token['oauth_token'])

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
    
    # create the client
    params = {'oauth_verifier' : oauth_verifier}
    access_token = parse_token_from_response(client.post_access_token(data=params))
    
    # store stuff in the session
    request.session['access_token'] = access_token
    
    if access_token.has_key('xoauth_indivo_record_id'):
        request.session['record_id'] = access_token['xoauth_indivo_record_id']
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
    problem_xml = render_raw('problem', {'date_onset': '2010-04-26', 'date_resolution': '2010-08-03', 'coding_system': 'snomed', 'code': '37796009', 'code_fullname':'Migraine (disorder)', 'comments': 'I\'ve had a headache waiting for alpha3.', 'diagnosed_by': 'Dr. Ken'}, type='xml')

    client.message_record_attachment(record_id=record_id, message_id=message_id, attachment_num="1", data=problem_xml)

    return HttpResponseRedirect(reverse(problem_list))

def problem_list(request):
    client = get_indivo_client(request)
    
    if request.session.has_key('record_id'):
        record_id = request.session['record_id']
        
        # get record information
        record = parse_xml(client.read_record(record_id = record_id).response['response_data'])
        
        problems_xml = client.read_problems(record_id = record_id, parameters={'order_by': '-date_onset'}).response['response_data']
    else:
        carenet_id = request.session['carenet_id']
        
        # get basic record information
        record = parse_xml(client.get_carenet_record(carenet_id = carenet_id).response['response_data'])
        
        problems_xml = client.read_carenet_problems(carenet_id = carenet_id, parameters={'order_by': '-date_onset'}).response['response_data']
    
    record_label = record.attrib['label']
    
    problems_et = parse_xml(problems_xml)
    
    # go through the problems and extract the document_id and the name, date onset, and date resolved
    problems = []
    
    for p in problems_et.findall('Report'):
        new_p = parse_problem(p.find('Item/%sProblem' % NS))
        new_p.update(parse_meta(p.find('Meta/Document')))
        problems.append(new_p)
    
    num_problems = int(problems_et.find('Summary').attrib['total_document_count'])
    
    return render_template('list', {'record_label': record_label, 'num_problems' : num_problems, 'problems': problems})

def new_problem(request):
    if request.method == "GET":
        return render_template('newproblem')
    else:

        # Fix dates formatted by JQuery into xs:dateTime                                        
        date_onset = request.POST['date_onset'] + 'T00:00:00Z' if request.POST['date_onset'] != '' else ''
        date_resolution = request.POST['date_resolution'] + 'T00:00:00Z' if request.POST['date_resolution'] != '' else ''

        # get the variables and create a problem XML
        params = {'code_abbrev':'', 'coding_system': 'snomed', 'date_onset': date_onset, 'date_resolution': date_resolution, 'code_fullname': request.POST['code_fullname'], 'code': request.POST['code'], 'diagnosed_by' : request.POST['diagnosed_by'], 'comments' : request.POST['comments']}
        problem_xml = render_raw('problem', params, type='xml')
        
        # add the problem
        client = get_indivo_client(request)
        client.post_document(record_id = request.session['record_id'], data=problem_xml)
        
        # add a notification
        # let's not do this anymore because it's polluting the healthfeed
        # client.record_notify(record_id = request.session['record_id'], data={'content':'a new problem has been added to your problem list'})
        
        return HttpResponseRedirect(reverse(problem_list))

def code_lookup(request):
    client = get_indivo_client(request)
    
    query = request.GET['query']
    
    # reformat this for the jQuery autocompleter
    codes = simplejson.loads(client.lookup_code(coding_system='snomed', parameters= {'q' : query}).response['response_data'])
    formatted_codes = {'query': query, 'suggestions': [c['consumer_value'] for c in codes], 'data': codes}
    
    return HttpResponse(simplejson.dumps(formatted_codes), mimetype="text/plain")

def one_problem(request, problem_id):
    client = get_indivo_client(request)
    
    record_id = request.session.get('record_id', None)
    
    if record_id:
        
        # get record information
        record = parse_xml(client.read_record(record_id = record_id).response['response_data'])
        
        doc_xml = client.read_document(record_id= record_id, document_id = problem_id).response['response_data']
        doc_meta_xml = client.read_document_meta(record_id=record_id, document_id= problem_id).response['response_data']
    else:
        carenet_id = request.session['carenet_id']
        
        record = parse_xml(client.get_carenet_record(carenet_id = carenet_id).response['response_data'])
        
        doc_xml = client.get_carenet_document(carenet_id= carenet_id, document_id = problem_id).response['response_data']
        #doc_meta_xml = client.get_carenet_document_meta(carenet_id=carenet_id, document_id= problem_id).response['response_data']
        doc_meta_xml = None
    
    doc = parse_xml(doc_xml)
    
    problem = parse_problem(doc)
    
    if doc_meta_xml:
        doc_meta = parse_xml(doc_meta_xml)
        meta = parse_meta(doc_meta)
    else:
        meta = None
    
    record_label = record.attrib['label']
    
    surl_credentials = client.get_surl_credentials()
    
    return render_template('one', {'problem':problem, 'record_label': record_label, 'meta': meta, 'record_id': record_id, 'problem_id': problem_id, 'surl_credentials': surl_credentials})

