from django.conf.urls.defaults import *
from views import *
import settings
from django.conf import settings as rootsettings

urlpatterns = patterns('',
   # authentication
   (r'^start_auth', start_auth),
   (r'^after_auth', after_auth),

   # screens
   (r'^problems/codelookup$', code_lookup),

   # TESTING
   (r'^problems/test$', test_message_send),

   (r'^problems/$', problem_list),
   (r'^problems/new$', new_problem),
   (r'^problems/(?P<problem_id>[^/]+)', one_problem),

    # static
    ## WARNING NOT FOR PRODUCTION
    (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': rootsettings.SERVER_ROOT_DIR + settings.STATIC_HOME}),
)
