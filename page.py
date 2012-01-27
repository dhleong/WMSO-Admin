#
# Page handling
#

from google.appengine.ext import db

from django.template import TemplateDoesNotExist
from django.template.loader import BaseLoader

from display import get_type, Display

class Template(db.Model):
    '''
    A Template just has a name (should be like filename) by which
    it can be referenced, and some text data
    '''

    name = db.StringProperty(required=True)
    data = db.TextProperty(required=True)

    extends = db.StringProperty()

    def __str__(self):
        '''So we have a nice pretty name in the selector instead of random crap'''
        return self.name

class TemplateLoader(BaseLoader):
    is_usable = True

    def load_template_source(self, template_name, template_dirs=None):
        q = Template.all()
        q.filter('name = ', template_name)

        t = q.get()
        if t:
            return (t.data, t.name)

        raise TemplateDoesNotExist(template_name)

class DbPage(db.Model):
    '''
    A Page references one or more Displays, and uses them to
    build its template. Note that templates are ONLY
    associated with pages-- Displays only manage their
    data, and know nothing about how it will be formatted.
    '''

    link = db.StringProperty()          # URL reference
    name = db.StringProperty()          # human-friendly name of the page
    #template = db.StringProperty()      # template file name
    template = db.ReferenceProperty(Template)
    displays = db.StringListProperty()  # list of owned displays
    #displays = db.ListProperty(item_type=unicode, choices=set([d.name for d in Display.all()]))  # list of owned displays
    #displays = db.ListProperty(db.Key)

    last_update = db.DateTimeProperty(auto_now=True)

class Page:
    def __init__(self, dbPage):
        self.instance = dbPage

    def get_template(self):
        '''Return the template as a string'''
        return self.instance.template.data

    def build_template(self, template_vals):
        q = DbPage.all()
        q.filter('link = ', self.instance.link)

        page = q.get()
        if not page:
            # nothing yet
            return

        q = Display.all()
        q.filter('__key__ IN ', [ db.Key(key) for key in self.instance.displays ])

        for disp in q:
            kind = get_type(disp)
            kind.build_template(template_vals)
