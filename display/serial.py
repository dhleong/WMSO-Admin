#
# The "serial" page type, for news posts, etc. that
#   you don't want to manually create a separate page for each
#

import os
import logging
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from google.appengine.dist import use_library
#use_library('django', '1.2')

from google.appengine.api import memcache
from google.appengine.ext.webapp import template
from google.appengine.ext.db import djangoforms
from google.appengine.ext import db

from __init__ import Display, AbstractDisplay

def match(link):
    '''
    Check to see if there's a SerialPage that handles
    the given link, and return it if so
    '''
    serial_list = memcache.get('serials')
    if not serial_list:
        serial_displays = []
        q = db.GqlQuery("SELECT * FROM Display WHERE display_type = :1",
            'SerialDisplay')
        for d in q:
            serial_displays.append(d.name)
                
        serial_list = []
        q = db.GqlQuery("SELECT * FROM DbPage")
        for r in q:
            for display in r.displays:
                if display in serial_displays:
                    serial_list.append(r.link)
                    break

        memcache.set('resources', serial_list)

    for prefix in serial_list:
        if link.find(prefix) == 0:
            q = db.GqlQuery("SELECT * FROM DbPage WHERE link = :1", prefix)
            return SerialPage(q.get())

    return None

def _name2prefix(name):
    return name.lower().replace(' ','_')

class SerialPost(db.Model):

    display = db.ReferenceProperty(Display) # the display we belong to

    uid = db.StringProperty(required=True) # Display.link+uid = url

    last_update = db.DateTimeProperty(auto_now=True)

class SerialVarSpec(db.Model):
    '''We don't need the BaseVar values for just a spec'''
    
    display = db.ReferenceProperty(Display) # the display we belong to
    name = db.StringProperty(required=True)     # the var name
    val_type = db.StringProperty(required=True, choices=set(['short','long','date']))

class SerialVarSpecForm(djangoforms.ModelForm):
    class Meta:
        model = SerialVarSpec
        exclude = ['display']

class SerialVar(db.Model):
    post = db.ReferenceProperty(SerialPost) # the post we belong to

    name = db.StringProperty(required=True)     # the var name
    val_short = db.StringProperty(multiline=False)    # the var value, coerced to a string
    val_long  = db.TextProperty()
    val_date  = db.DateTimeProperty()

    val_type = db.StringProperty(required=True, choices=set(['short','long','date']))

    def get_value(self):
        #return self['val_%s' % self.val_type]
        if self.val_type == 'short':
            return self.val_short
        elif self.val_type == 'long':
            return self.val_long
        else:
            return self.val_date

    def set_value(self, new_value):
        #self['val_%s' % self.val_type] = new_value
        self.__setattr__('val_%s' % self.val_type, new_value)

class SerialVarForm(djangoforms.ModelForm):
    class Meta:
        model = SerialVar
        exclude = ['post', 'val_short', 'val_long', 'val_date']

def FilledSerialVarForm(*args, **kwargs):
    '''Dynamically create a filled form entry with only the chosen val_type visible'''

    thisType = '' # fill me
    if kwargs.has_key('data'):
        # called using 'data'
        thisType = kwargs['data']['%s-val_type' % kwargs['prefix']]
    else:
        # called using 'instance'
        thisType = kwargs['instance'].val_type

    class FilledSerialVarForm_(djangoforms.ModelForm):
        class Meta:
            model = SerialVar
            exclude = [ e for e in SerialVarForm.Meta.exclude 
                if e != 'val_%s' % thisType ]

        def __init__(self):
            super(FilledSerialVarForm_, self).__init__(*args, **kwargs)

        def get_value(self):
            return self['val_%s' % thisType]

    return FilledSerialVarForm_()

class SerialPage:
    '''
    Special version of Page for serials
    '''
    def __init__(self, dbPage):
        self.instance = dbPage

    def get_template(self):
        '''Return the template as a string'''
        # I guess this is okay
        return self.instance.template.data

    def build_template(self, link, template_vals):
        # TODO
        pass


class SerialDisplay(AbstractDisplay):

    def get(self, handler, template_values):
        mode = handler.request.get('m')
        if not mode:
            # home page; links to edit old items, create a new one,
            #   and configurations

            # fetch possible vars
            q = SerialVarSpec.all()
            q.filter('display = ', self.display)

            my_vars = []

            for v in q:
                f = SerialVarSpecForm(instance=v, prefix=v.key().id())
                my_vars.append(f)
           
            # making a new one
            my_vars.append(SerialVarSpecForm(prefix='new'))

            template_values['my_vars'] = my_vars

            # fetch posts
            q = SerialPost.all()
            q.filter('display = ', self.display)
            template_values['posts'] = q

            handler.response.out.write(template
                .render('static/display-serial.html', template_values))
        elif mode == 'edit':
            # edit an old post/create a new one
            my_vars = []
            uid = handler.request.get('uid')
            if uid:
                q = SerialPost.all()
                q.filter('display = ', self.display)
                q.filter('uid = ', uid)

                post = q.get()

                if post:
                    template_values['post'] = post

                    q = SerialVar.all()
                    q.filter('post = ', post)

                    for v in q:
                        f = FilledSerialVarForm(instance=v,\
                            prefix=_name2prefix(v.name))
                        my_vars.append(f)
            else:
                # new one. create forms from spec
                q = SerialVarSpec.all()
                q.filter('display = ', self.display)

                for v in q:
                    var = SerialVar(display=self.display,\
                        name=v.name,val_type=v.val_type)
                    f = FilledSerialVarForm(instance=var,prefix=_name2prefix(v.name))
                    my_vars.append(f)

            template_values['my_vars'] = my_vars
            handler.response.out.write(template
                .render('static/display-serial-edit.html',\
                    template_values))

    def build_spec_and_save(self, handler):
        '''Build the list of base vars for a POST operation, updating entities 
        as needed. This method is intended to be run in a transaction
        '''
        q = SerialVarSpec.all()
        q.filter('display = ', self.display)

        my_vars = []
        # update any existing vars as needed
        for disp in q:
            deleteName = 'delete-%d' % disp.key().id()
            if handler.request.POST.has_key(deleteName) and handler.request.POST[deleteName].lower() == 'on':
                # kill it
                disp.delete()
                continue

            currVar = SerialVarSpecForm(prefix=disp.key().id(), data=handler.request.POST, instance=disp)
            if currVar.is_valid():# and currVar.get_value() != disp.get_value():
                currVar.save()

            my_vars.append(currVar)

        # create new var if needed
        newVar = SerialVarSpecForm(prefix='new', data=handler.request.POST)
        if newVar.is_valid():
            entity = newVar.save(commit=False)
            entity.display = self.display.key()
            entity.put()

            my_vars.append(SerialVarSpecForm(instance=entity, prefix=entity.key().id()))

        return my_vars

    def build_and_save(self, handler):
        '''Build the list of vars for a POST operation, updating entities 
        as needed. This method is intended to be run in a transaction
        '''
        # create the post if necessary
        post_key = handler.request.get('post_key')
        existing = {}
        if post_key:
            post = SerialPost.get_by_id(int(post_key))

            q = SerialVar.all()
            q.filter('post = ', post)
            for var in q:
                existing[_name2prefix(var.name)] = var

        else:
            # new post
            post = SerialPost(display=self.display.key(),\
                uid=handler.request.get('uid'))
            post.put()


        q = SerialVarSpec.all()
        q.filter('display = ', self.display)

        my_vars = []
        # update/create vars as needed
        for disp in q:
            prefix = _name2prefix(disp.name)
            if prefix in existing:
                currVar = FilledSerialVarForm(prefix=prefix, \
                    data=handler.request.POST, instance=existing[prefix])
            else:
                currVar = FilledSerialVarForm(prefix=prefix, \
                    data=handler.request.POST)

            if currVar.is_valid():
                ent = currVar.save(commit=False)
                ent.post = post.key()

            my_vars.append(currVar)

        return post, my_vars

    def post(self, handler, template_values):
        super(SerialDisplay, self).post(handler, template_values)

        mode = handler.request.get('m')
        if not mode:
            
            #my_vars = db.run_in_transaction(self.build_and_save, handler)
            my_vars = self.build_spec_and_save(handler)

            # add option for a new var
            my_vars.append(SerialVarSpecForm(prefix='new'))

            # add to template
            template_values['my_vars'] = my_vars
            
            # render
            handler.response.out.write(template
                .render('static/display-serial.html', template_values))

        elif mode == 'edit':
            # create/update a post
            post, my_vars = self.build_and_save(handler)
            template_values['post'] = post
            template_values['my_vars'] = my_vars
            handler.response.out.write(template
                .render('static/display-serial-edit.html',\
                    template_values))
