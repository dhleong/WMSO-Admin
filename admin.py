#
# Administration handler
#

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import re

import time, datetime

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.api import users
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.ext.db import djangoforms

from django import forms

import display
import page
import fields
import settings
import res

#
# Utils
#

def check_privileged(handler):
    '''If user is logged in and an admin, return them. Else, return None'''
    user = users.get_current_user()

    # only admins
    if not (user and users.is_current_user_admin()):
        template_values = {
            'login_url': users.create_login_url(handler.request.uri)
        }
        handler.response.out.write(template.render('static/error_admin.html', template_values))
        return None

    return user

#
# HANDLERS
#

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = check_privileged(self)
        if not user:
            return

        template_values = {}

        self.response.out.write(template.render('static/admin.html', template_values))

class DisplayHandler(webapp.RequestHandler):
    def get(self):
        user = check_privileged(self)
        if not user:
            return

        # template values
        template_values = {
            'displays': display.Display.all(), # load displays
            'action': self.request.uri
        }

        # if we've selected one, allow to edit it
        id_ = self.request.get('id')
        if id_:
            disp = display.Display.get_by_id(int(id_))
            if disp:
                template_values['display'] = disp
                template_values['form'] = DisplayForm(instance=disp)
                # TODO deleting form, or something

        if 'form' not in template_values:
            template_values['form'] = DisplayForm() # prepare a form to make a new display

        # render
        self.response.out.write(template.render('static/admin_displays.html', template_values))

    def post(self):
        user = check_privileged(self)
        if not user:
            return

        data = None
        id_ = self.request.get('id')
        if id_:
            disp = display.Display.get_by_id(int(id_))
            if disp:
                template_values['display'] = disp
                data = DisplayForm(data=self.request.POST, instance=disp)

        if not data:
            data = DisplayForm(data=self.request.POST)

        if data.is_valid():
            entity = data.save() # push into db
            self.redirect('/admin/update?id=%d' % entity.key().id())
            return

        template_values = {
            'displays': display.Display.all(), # load displays
            'form': data,
            'action': self.request.uri
        }

        # render
        self.response.out.write(template.render('static/admin_displays.html', template_values))

class DisplayForm(djangoforms.ModelForm):
    class Meta:
        model = display.Display

class PageHandler(webapp.RequestHandler):
    '''The Page Handler handles creating/managing Pages and their templates'''

    def _get_page(self):
        id_ = self.request.get('id')
        if not id_:
            return None

        return page.DbPage.get_by_id(long(id_))


    def get(self):
        user = check_privileged(self)
        if not user:
            return

        # basic template values
        template_values = {
            'action': self.request.uri,
            'pages': page.DbPage.all(),
            'displays': display.Display.all()
        }

        p = self._get_page()
        if p:
            template_values['page'] = p
            template_values['form'] = PageForm(instance=p)

        if 'form' not in template_values:
            template_values['form'] = PageForm()

        self.response.out.write(template.render('static/admin_pages.html', template_values))

    def post(self):
        user = check_privileged(self)
        if not user:
            return

        # basic template values
        template_values = {
            'action': self.request.uri,
            'pages': page.DbPage.all(),
            'displays': display.Display.all()
        }

        p = self._get_page()
        if p:
            template_values['page'] = p
            form = PageForm(instance=p, data=self.request.POST.mixed())
        else:
            form = PageForm(data=self.request.POST.mixed())

        if form.is_valid():
            form.save()

            # force udpate of serials
            # TODO only do this if the page has/had a serial display
            memcache.delete('serials')

        template_values['form'] = form

        self.response.out.write(template.render('static/admin_pages.html', template_values))

def PageForm(instance=None, data=None):
    '''Generate a PageForm '''

    if data is None and instance is not None:
        data = {
            'link': instance.link,
            'name': instance.name,
            'template': instance.template.key(),
            'displays': instance.displays
        }

    class PageForm_(forms.Form):
        link = forms.CharField(required=True, max_length=20)          # URL reference
        name = forms.CharField(required=True, max_length=20)          # human-friendly name of the page
        #template = forms.CharField(required=True, max_length=20)      # template file name
        #template = forms.ChoiceField(required=True, \
            #choices=[ (t.key(), t.name) for t in page.Template.all() ])
        template = djangoforms.ModelChoiceField(page.Template, required=True)
        #displays = forms.MultipleChoiceField(required=False, \
            #choices=[ (d.key(), d.name) for d in display.Display.all() ])  # list of owned displays
        displays = fields.MultipleChoiceField(required=False, \
            choices=[ (d.key(), d.name) for d in display.Display.all() ])  # list of owned displays

        def save(self, commit=True):
            instance = self.instance
            if instance is None:
                instance = page.DbPage(link=self.cleaned_data['link'], 
                    name=self.cleaned_data['name'], 
                    template=self.cleaned_data['template'], 
                    displays=self.cleaned_data['displays'])
            else:
                instance.link = self.cleaned_data['link']
                instance.name = self.cleaned_data['name']
                instance.template = self.cleaned_data['template']
                instance.displays = self.cleaned_data['displays']

            if commit:
                instance.put()

    form = PageForm_(data)
    form.instance = instance
    return form

class UpdateHandler(webapp.RequestHandler):
    def _get_display(self):
        id_ = self.request.get('id')
        if not id_:
            return None
            
        disp = display.Display.get_by_id(long(id_))
        if not disp:
            return None

        return display.get_type(disp)
 
    def get(self):
        user = check_privileged(self)
        if not user:
            return

        disp = self._get_display()
        template_values = {
            'displays': display.Display.all(),
            'action': self.request.uri,
            'display': disp
        }

        if not disp:
            self.response.out.write(template.render('static/admin_update.html', template_values))
            return

        disp.get(self, template_values)

    def post(self):
        user = check_privileged(self)
        if not user:
            return

        disp = self._get_display()
        template_values = {
            'displays': display.Display.all(),
            'action': self.request.uri,
            'display': disp
        }

        if not disp:
            self.response.out.write(template.render('static/admin_update.html', template_values))
            return

        disp.post(self, template_values)

class Setting(db.Model):
    name = db.StringProperty()
    value = db.StringProperty()

class SyncHandler(webapp.RequestHandler):

    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def get(self):
        q = Setting.all()
        q.filter('name = ', 'last_sync')
        sync = q.get()

        # query updated pages
        pages = page.DbPage.all()

        # query resources
        resources = res.Resource.all()

        # filter by last_sync, if we have it
        if sync:
            last_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(sync.value, self.TIME_FORMAT)))

            pages.filter('last_update > ', last_time)
            resources.filter('last_update > ', last_time)

        # sum counts
        total_count = pages.count() + resources.count()

        # print 
        self.response.out.write("%d\n" % total_count)
        for p in pages:
            self.response.out.write("%s\n" % p.link)
        for r in resources:
            self.response.out.write("%s\n" % r.name)
        
        # update
        if self.request.get('commit'):
            now = datetime.datetime.now().strftime(self.TIME_FORMAT)
            if sync:
                sync.value = now
            else:
                sync = Setting(name='last_sync', value=now)

            sync.put()
        

class TemplateHandler(webapp.RequestHandler):
    reExtends = re.compile(r"^\{\% extends ['\"](?P<extended>[^'\"]+)['\"] \%\}")

    def get(self):
        user = check_privileged(self)
        if not user:
            return

        # template values
        template_values = {
            'templates': page.Template.all(), # load displays
            'action': self.request.uri
        }

        # if we've selected one, allow to edit it
        id_ = self.request.get('id')
        if id_:
            tmp = page.Template.get_by_id(int(id_))
            if tmp:
                template_values['template'] = tmp
                template_values['form'] = TemplateForm(instance=tmp)

        if 'form' not in template_values:
            template_values['form'] = TemplateForm() # prepare a form to make a new display

        # render
        self.response.out.write(template.render('static/admin_templates.html', template_values))

    def post(self):
        user = check_privileged(self)
        if not user:
            return

        data = None
        wasNew = True
        id_ = self.request.get('id')
        if id_:
            tmp = page.Template.get_by_id(int(id_))
            if tmp:
                # editing an existing one
                data = TemplateForm(data=self.request.POST, instance=tmp)
                wasNew = False
        
        if not data:
            # okay, new template
            data = TemplateForm(data=self.request.POST)    

        template_values = {
            'templates': page.Template.all(), # load displays
            'action': self.request.uri,
        }

        if data.is_valid():
            entity = data.save(commit=False) # push into db

            # find if we extend anything
            m = self.reExtends.search(self.request.POST['data'])
            if m:
                entity.extends = m.group('extended')
            else:
                entity.extends = None

            # okay, now definitely save
            key = entity.put()

            if wasNew:
                template_values['form'] = TemplateForm()
                template_values['redir'] = "?id=%d" % key.id()
            else:
                # editing an old one 
                template_values['template'] = entity
                template_values['form'] = data

            # TODO check if we should mark pages for syncing

            # first, build a list of relevant templates
            changed_templates = [ entity ]

            # add everything that extends it. we assume
            #   nobody tries to extend themself...
            q = page.Template.all()
            q.filter('extends = ', entity.name)

            for t in q:
                changed_templates.append( t )

            q = page.DbPage.all()
            q.filter('template IN ', changed_templates)
            for p in q:
                p.put() # should update the auto_now date


        # render
        self.response.out.write(template.render('static/admin_templates.html', template_values))


class TemplateForm(djangoforms.ModelForm):
    class Meta:
        model = page.Template
        exclude = ['extends']

class SettingForm(djangoforms.ModelForm):
    class Meta:
        model = Setting

class PublishHandler(webapp.RequestHandler):

    FORMS = ['ftp_host','ftp_user','ftp_pass','ftp_path']

    def _get_forms(self):
        '''Get the forms in a dict by name'''
        forms = {}
        q = Setting.all()
        for s in q:
            if s.name in self.FORMS:
                forms[s.name] = s

        # now fill with new entities if any are missing
        for name in self.FORMS:
            if not forms.has_key(name):
                forms[name] = Setting(name=name)

        return forms

    def get(self):
        user = check_privileged(self)
        if not user:
            return

        go = self.request.get('go')
        if go:
            # render applet page
            template_values = {'DOC_ROOT':settings.DOC_ROOT}
            configs = self._get_forms()
            params = []
            for key in self.FORMS:
                if configs[key].value:
                    params.append(configs[key])
            template_values['params'] = params

            self.response.out.write(template.render('static/admin_publish_applet.html', template_values))
        else:
            # render settings
            entities = self._get_forms()
            forms = []
            # this way, we get them in order
            for key in self.FORMS:
                forms.append(SettingForm(instance=entities[key], prefix=key))
                
            template_values = {
                'action':self.request.uri,
                'forms':forms
            }
            self.response.out.write(template.render('static/admin_publish.html', template_values))
        

    def post(self):
        user = check_privileged(self)
        if not user:
            return

        entities = self._get_forms()
        forms = []
        # this way, we get them in order
        for key in self.FORMS:
            entities[key].name = key
            f = SettingForm(instance=entities[key], prefix=key, data=self.request.POST)
            value = f.data['%s-value'%key]
            if f.is_valid() and value and len(value):
                entity = f.save(commit=False)
                entity.name = key
                entity.put()

            forms.append(f)

        template_values = {
            'action':self.request.uri,
            'forms':forms
        }
        self.response.out.write(template.render('static/admin_publish.html', template_values))
    

def main():
    application = webapp.WSGIApplication([('/admin/?', MainHandler),
                                          ('/admin/displays.*', DisplayHandler),
                                          ('/admin/pages.*', PageHandler),
                                          ('/admin/publish', PublishHandler),
                                          ('/admin/sync', SyncHandler),
                                          ('/admin/templates.*', TemplateHandler),
                                          ('/admin/update.*', UpdateHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
