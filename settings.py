
import os
ROOT_PATH = os.path.dirname(__file__)

#if os.environ['HTTP_HOST'] == 'localhost:8083':
    #DOC_ROOT = 'http://localhost:8083/'
#else:
    #DOC_ROOT = 'http://wmso-admin.appspot.com/'
DOC_ROOT = "http://%s" % os.environ['HTTP_HOST']

TEMPLATE_DIRS = (ROOT_PATH + '/static')

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'page.TemplateLoader'
)
