#
# Uploadable resource management
#

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import urllib

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.api import memcache
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.ext.db import djangoforms

ACCEPTED_MIME_MAP = {
    'text': ['css','html','js'],
    'image': ['jpg', 'jpeg', 'png']
}

ACCEPTED_MIMES = sum([ [ "%s/%s"%(meta,t) for t in types] \
    for meta, types in [ (meta, ACCEPTED_MIME_MAP[meta]) for meta in ACCEPTED_MIME_MAP]], [])
ACCEPTED_MIME_STR = ', '.join(ACCEPTED_MIMES)
    

class Resource(db.Model):
    """A single resource instance"""
    
    name = db.StringProperty(required=True) # eg "css/style.css" (full relative url)
    binary = db.BooleanProperty() # if it's a binary value or text ("required," but not for validation)

    blob = db.BlobProperty()
    text = db.TextProperty()

    last_update = db.DateTimeProperty(auto_now=True)

class ResourceForm(djangoforms.ModelForm):
    class Meta:
        model = Resource
        exclude=['binary','blob','text']

def exists(link):
    """Check if the link is a valid resource"""
    res_list = memcache.get('resources')
    if not res_list:
        res_list = []
        q = Resource.all()
        for r in q:
            res_list.append(r.name)

        memcache.set('resources', res_list)

    return link in res_list

def get_mime(name):
    '''Get the mime type of a file'''

    ext = name[name.rfind('.')+1:]
    meta = 'text'
    if ext in ACCEPTED_MIME_MAP['image']:
        meta = 'image'

    return "%s/%s" % (meta, ext)

def handle_view(reqHandler, link):
    """Display the resource (we assume it exists)"""

    q = Resource.all()
    q.filter("name =", link)
    res = q.get()
    if not res:
        reqHandler.response.out.write('no such resource')
        return


    mime = get_mime(res.name)

    #print 'test'
    reqHandler.response.headers['Content-Type'] = mime
    if res.binary:
        reqHandler.response.out.write(res.blob)
    else:
        reqHandler.response.out.write(res.text)

class ResHandler(webapp.RequestHandler):
    """Admin interface to handle resources"""

    def get(self):

        upload_form = ResourceForm()

        template_values = {
            'upload_accepts': ACCEPTED_MIME_STR,
            'upload_action': '/admin/res/upload',
            'upload_form': upload_form,
            'resources': Resource.all()
        }

        upstats = self.request.get('upload')
        if upstats == 'success':
            template_values['upload_success'] = True
        elif upstats == 'fail':
            template_values['upload_fail'] = True

        deletestats = self.request.get('delete')
        if deletestats == 'fail':
            template_values['delete_fail'] = True
        else:
            template_values['delete_file'] = deletestats

        template_values['newtext_fail'] = self.request.get('newtext')

        self.response.out.write(template.render('static/admin_res.html', template_values))

class UploadHandler(webapp.RequestHandler):
    """Admin interface to handle resource uploads"""

    def post(self):
        data = None
        id_ = self.request.get('name')
        if id_:
            #tmp = Resource.get_by_id(int(id_))
            q = Resource.all()
            q.filter('name =', id_)
            tmp = q.get()
            if tmp:
                # editing an existing one
                data = ResourceForm(data=self.request.POST, instance=tmp)
        
        if not data:
            # okay, new resource
            data = ResourceForm(data=self.request.POST) 

        if data.is_valid():
            entity = data.save(commit=False) # push into db
            
            # fix name
            if entity.name[0] == '/':
                entity.name = entity.name[1:] # remove leading slash

            # update memcache if we have it
            res_list = memcache.get('resources')
            if res_list and entity.name not in res_list:
                res_list.append(entity.name)
                memcache.set('resources', res_list)

            upfile = self.request.get('upfile')
            newText = False
            if not upfile:
                # new text file
                upfile = ''
                newText = True

            ext = entity.name[entity.name.rfind('.')+1:]
            if ext in ACCEPTED_MIME_MAP['image']:
                if newText:
                    # shouldn't be image, wtf
                    self.redirect('/admin/res?newtext=fail')
                    return

                entity.binary = True
                entity.blob = db.Blob(self.request.get('upfile'))
                self.response.headers['Content-Type'] = 'image/png'
                self.response.out.write(self.request.get('upfile'))
            else:
                entity.binary = False
                if type(self.request.get('upfile')) == unicode:
                    entity.text = db.Text(self.request.get('upfile'))
                else:
                    entity.text = db.Text(self.request.get('upfile'), 'utf-8')

            entity.put()

            if self.request.get('edit'):
                self.redirect('/admin/res/edit/%d' % entity.key().id())
            else:
                self.redirect('/admin/res?upload=success')
        else:
            self.redirect('/admin/res?upload=fail')

class EditHandler(webapp.RequestHandler):
    """Admin interface to edit text resources"""

    def get(self, id_):

        res = None
        if id_:
            res = Resource.get_by_id(int(id_))

        template_values = {
            'upload_action': '/admin/res/upload',
            'new': (id_ == 'new'),
            'resource': res
        }

        if res:
            template_values['mode'] = 'html' # default
            if res.name.endswith('js'):
                template_values['mode'] = 'javascript'
            elif res.name.endswith('css'):
                template_values['mode'] = 'css'
        
        self.response.out.write(template.render('static/admin_res_edit.html', template_values))
    
class DeleteHandler(webapp.RequestHandler):
    """Admin interface to edit text resources"""

    def get(self, id_):
        if not id_:
            self.redirect('/admin/res?delete=unknown')
            return

        res = Resource.get_by_id(int(id_))
        if not res:
            self.redirect('/admin/res?delete=unknown')
            #self.response.headers['Location'] = '/admin/res?delete=unknown'
            return

        name = res.name
        res.delete()

        # update memcache if we have it
        res_list = memcache.get('resources')
        if res_list and entity.name in res_list:
            res_list.remove(entity.name)
            memcache.set('resources', res_list)

        self.redirect('/admin/res?%s' % urllib.urlencode({'delete':name}))


def main():
    application = webapp.WSGIApplication([\
                                        ('/admin/res/?', ResHandler),\
                                        ('/admin/res/edit/(.*)', EditHandler),\
                                        ('/admin/res/delete/(.*)', DeleteHandler),\
                                        ('/admin/res/upload', UploadHandler)\
                                            ],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
