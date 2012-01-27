#
# The "extended" type is basically like
#   the listing type, but the value itself
#   is (strictly) a list of strings
# It even uses the same display tempalate (display-listing.html)
#

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext.webapp import template
from google.appengine.ext.db import djangoforms
from google.appengine.ext import db

from __init__ import Display, AbstractDisplay


class ExtendedVar(db.Model):
    display = db.ReferenceProperty(Display) # the display we belong to
    name = db.StringProperty(required=True)     # the var name
    val = db.StringListProperty()
    order = db.IntegerProperty(default=-1)

class ExtendedVarForm(djangoforms.ModelForm):
    class Meta:
        model = ExtendedVar

        exclude= ['display', 'order']

    def create(self, commit=True, key_name=None, parent=None):
        """Save this form's cleaned data into a new model instance.

        Args:
          commit: optional bool, default True; if true, the model instance
            is also saved to the datastore.
          key_name: the key_name of the new model instance, default None
          parent: the parent of the new model instance, default None

        Returns:
          The model instance created by this call.
        Raises:
          ValueError if the data couldn't be validated.
        """
        if not self.is_bound:
            raise ValueError('Cannot save an unbound form')
        opts = self._meta
        instance = self.instance
        if self.instance:
            raise ValueError('Cannot create a saved form')
        if self.errors:
            raise ValueError("The %s could not be created because the data didn't "
                           'validate.' % opts.model.kind())
        cleaned_data = self._cleaned_data()
        converted_data = {}
        for name, prop in opts.model.properties().iteritems():
            value = cleaned_data.get(name)
            if value is not None:
                converted_data[name] = prop.make_value_from_form(value)
        try:
            instance = opts.model(key_name=key_name, parent=parent, **converted_data)
            self.instance = instance
        except db.BadValueError, err:
            raise ValueError('The %s could not be created (%s)' %
                           (opts.model.kind(), err))
        if commit:
            instance.put()
        return instance


class ExtendedDisplay(AbstractDisplay):
    
    def __init__(self, disp):
        super(ExtendedDisplay, self).__init__(disp)

    def build_template(self, template_vars):
        '''Add whatever variables we provide to the template_vars dict'''

        q = ExtendedVar.all()
        q.filter('display = ', self.display)
        q.order('order')

        data = []

        for var in q:
            data.append( (var.name, var.val) )#['val_' + kind]

        template_vars[self.display.template_name()] = data

    def get(self, handler, template_values):
        if 'up' in handler.request.GET or 'down' in handler.request.GET:
            # update and redirect
            db.run_in_transaction(self.handle_updown, handler)
            handler.redirect('/admin/update?id=%d' % self.id)
            return

        q = ExtendedVar.all()
        q.filter('display = ', self.display)
        q.order('order')

        my_vars = []

        for v in q:
            f = ExtendedVarForm(instance=v, prefix=v.key().id())
            my_vars.append(f)
       
        # making a new one
        my_vars.append(ExtendedVarForm(prefix='new'))

        template_values['my_vars'] = my_vars
        
        handler.response.out.write(template.render('static/display-listing.html', template_values))

    def build_and_save(self, handler):
        '''Build the lise of vars for a POST operation, updating entities 
        as needed. 
        '''
        q = ExtendedVar.all()
        q.filter('display = ', self.display)
        q.order('order')

        my_vars = []
        # update any existing vars as needed
        for disp in q:
            deleteName = 'delete-%d' % disp.key().id()
            if handler.request.POST.has_key(deleteName) and handler.request.POST[deleteName].lower() == 'on':
                # kill it
                disp.delete()
                continue

            currVar = ExtendedVarForm(prefix=disp.key().id(), data=handler.request.POST, instance=disp)
            if currVar.is_valid():# and currVar.get_value() != disp.get_value():
                currVar.save()

            # save for later
            currVar.order = disp.order
            my_vars.append(currVar)

        # create new var if needed
        newVar = ExtendedVarForm(prefix='new', data=handler.request.POST)
        if newVar.is_valid():
            entity = newVar.create(commit=False, parent=self.display)
            entity.display = self.display.key()
            # give us a proper order
            if entity.order == -1: # it should be -1, but just in case
                if len(my_vars) > 0:
                    entity.order = my_vars[-1].order + 1
                else:
                    entity.order = 0
            entity.put()

            my_vars.append(ExtendedVarForm(instance=entity, prefix=entity.key().id()))

        return my_vars

    def handle_updown(self, handler):
        '''Special case of GET when we're re-ordering an item'''
        mode = None
        id_ = None
        if 'up' in handler.request.GET:
            mode = -1
            id_ = int(handler.request.GET['up'])
        elif 'down' in handler.request.GET:
            mode = 1
            id_ = int(handler.request.GET['down'])

        thisVar = ExtendedVar.get_by_id(id_, self.display)
        thisVar.order += mode
        
        q = ExtendedVar.all()
        #q.filter('display = ', self.display)
        q.ancestor(self.display)
        q.filter('order == ', thisVar.order)

        # fetch the one that used to be where we want to be
        oldVar = q.get()
        if oldVar:
            oldVar.order -= mode
            oldVar.put()

        thisVar.put()

    def post(self, handler, template_values):
        
        my_vars = self.build_and_save(handler)

        # add option for a new var
        my_vars.append(ExtendedVarForm(prefix='new'))

        # add to template
        template_values['my_vars'] = my_vars
        
        # render
        handler.response.out.write(template.render('static/display-listing.html', template_values))

