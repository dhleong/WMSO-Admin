#
# The "base" page type, provides single variables
# By: Daniel Leong
#

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from google.appengine.dist import use_library
#use_library('django', '1.2')

from google.appengine.ext.webapp import template
from google.appengine.ext.db import djangoforms
from google.appengine.ext import db

from __init__ import Display, AbstractDisplay

class BaseVar(db.Model):
    
    display = db.ReferenceProperty(Display) # the display we belong to

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

class BaseVarForm(djangoforms.ModelForm):
    class Meta:
        model = BaseVar
        exclude = ['display', 'val_short', 'val_long', 'val_date']

def FilledBaseVarForm(*args, **kwargs):
    '''Dynamically create a filled form entry with only the chosen val_type visible'''

    thisType = '' # fill me
    if kwargs.has_key('data'):
        # called using 'data'
        thisType = kwargs['data']['%s-val_type' % kwargs['prefix']]
    else:
        # called using 'instance'
        thisType = kwargs['instance'].val_type

    class FilledBaseVarForm_(djangoforms.ModelForm):
        class Meta:
            model = BaseVar
            exclude = [ e for e in BaseVarForm.Meta.exclude 
                if e != 'val_%s' % thisType ]

        def __init__(self):
            super(FilledBaseVarForm_, self).__init__(*args, **kwargs)

        def get_value(self):
            return self['val_%s' % thisType]

    return FilledBaseVarForm_()

class BaseDisplay(AbstractDisplay):
    
    def __init__(self, disp):
        '''
        disp: a Display instance (from the db)
        '''
        super(BaseDisplay, self).__init__(disp)

    def build_template(self, template_vars):
        '''Add whatever variables we provide to the template_vars dict'''

        q = BaseVar.all()
        q.filter('display = ', self.display)

        for var in q:
            kind = var.val_type
            template_vars[var.name] = var.get_value()#['val_' + kind]

    def get(self, handler, template_values):
        q = BaseVar.all()
        q.filter('display = ', self.display)

        my_vars = []

        for v in q:
            f = FilledBaseVarForm(instance=v, prefix=v.key().id())
            my_vars.append(f)
       
        # making a new one
        my_vars.append(BaseVarForm(prefix='new'))

        template_values['my_vars'] = my_vars
        
        handler.response.out.write(template.render('static/display-base.html', template_values))

    def build_and_save(self, handler):
        '''Build the lise of base vars for a POST operation, updating entities 
        as needed. This method is intended to be run in a transaction
        '''
        q = BaseVar.all()
        q.filter('display = ', self.display)

        my_vars = []
        # update any existing vars as needed
        for disp in q:
            deleteName = 'delete-%d' % disp.key().id()
            if handler.request.POST.has_key(deleteName) and handler.request.POST[deleteName].lower() == 'on':
                # kill it
                disp.delete()
                continue

            currVar = FilledBaseVarForm(prefix=disp.key().id(), data=handler.request.POST, instance=disp)
            if currVar.is_valid():# and currVar.get_value() != disp.get_value():
                currVar.save()

            #my_vars.append(FilledBaseVarForm(instance=entity, prefix=entity.key().id()))
            my_vars.append(currVar)

        # create new var if needed
        newVar = BaseVarForm(prefix='new', data=handler.request.POST)
        if newVar.is_valid():
            entity = newVar.save(commit=False)
            entity.display = self.display.key()
            entity.put()

            my_vars.append(FilledBaseVarForm(instance=entity, prefix=entity.key().id()))

        return my_vars

    def post(self, handler, template_values):
        super(BaseDisplay, self).post(handler, template_values)
        
        #my_vars = db.run_in_transaction(self.build_and_save, handler)
        my_vars = self.build_and_save(handler)

        # add option for a new var
        my_vars.append(BaseVarForm(prefix='new'))

        # add to template
        template_values['my_vars'] = my_vars
        
        # render
        handler.response.out.write(template.render('static/display-base.html', template_values))

