#
# Display module
#

# import the modules for our displays here
#from base import BaseDisplay
#from listing import ListingDisplay

#from . import *

#
# Don't modify below here!
#
from google.appengine.ext import db

ALL_CLASSES = ['BaseDisplay', 'ConcertDisplay', 'ExtendedDisplay', 'ListingDisplay','SerialDisplay']
# build list of Display classes
#for k in globals().keys():
    #try:
        #inst = globals()[k](None)
        ##l.append(type(inst))
        #if k != 'Display' and k[-7:] == 'Display':
            #ALL_CLASSES.append(k)
    #except Exception, e: pass

def get_all():
    '''Get a list of the names of all Display classes'''
    return ALL_CLASSES

def get_type(disp):
    '''
    Initialize and return an instance of the display_type 
    used for the given display

    disp - a Display (see below) returned from a query
    '''

    #assert isinstance(disp, Display)
    #constructor = globals()[disp.display_type]
    moduleName = disp.display_type[:-7].lower() 
    display = __import__('display.%s' % moduleName)
    dispModule = display.__dict__[moduleName]
    constructor = dispModule.__dict__[disp.display_type]

    #print 'Constructor', constructor
    #print 'Disp', disp
    ret = constructor(disp)
    #print 'Ret', ret
    return ret


class Display(db.Model):
    '''
    A Display is some specialized holder of data. It doesn't
    care how that data is formatted or who uses it, but knows 
    how to retrieve it from the database and add it to a template.

    The Display Entity is used to map Displays to their specific Kind,
    which is one of the classes in this module.
    '''

    name = db.StringProperty(required=True)  # name of the display
    display_type = db.StringProperty(required=True,choices=set(get_all()))  # type of display (class name)

    def template_name(self):
        return self.name.lower().replace(' ','_')


class AbstractDisplay(object):
    '''
    All types of displays should extend this and call through to
    the super()'s methods. We add some functionality like setting the
    'last_update' field for pages that own the display.
    '''

    def __init__(self, disp):
        '''
        disp: a Display instance (from the db)
        '''
        if disp is None:
            return

        self.display = disp
        self.id = disp.key().id()

    def post(self, handler, template_values):
        
        # update "last update" for all pages owning this display
        q = db.GqlQuery('SELECT * FROM DbPage WHERE displays = :1', str(self.display.key()))
        for p in q:
            # just re-put and it'll auto-update the last_update field
            p.put() 
