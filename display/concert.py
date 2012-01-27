#
# The "concert" page type, provides season-sorted concerts
#   that can be assigned to establishable locations
# By: Daniel Leong
#

# idea:
#  use listing module for seasons!

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import re
from datetime import datetime

from google.appengine.dist import use_library
#use_library('django', '1.2')

from google.appengine.ext.webapp import template
from google.appengine.ext.db import djangoforms
from google.appengine.ext import db

from __init__ import Display, AbstractDisplay
from model import ModelForm
import listing

try:
    from django import newforms as forms
except:
    from django import forms


#PIECES_REGEX = r"(?P<name>.*) by (?P<composer>[^;]*)(?P<soloists>;[ ]*(?:[^,]*),[ ]*(?:[^(]*)[ ]*(?:\((?:.*)\))?)*"
PIECES_REGEX  = r"(?P<name>.*?)(?:[ ]*from (?P<work>.*))? by (?P<composer>[^;]*)(?P<soloists>;[ ]*(?:[^,]*),[ ]*(?:[^(]*)[ ]*(?:\((?:.*)\))?)*"
SOLOIST_REGEX = r"(?:;[ ]*(?P<soloist>[^,]*),[ ]*(?P<instrument>[^(;]*)[ ]*(?:\((?P<link>[^)]*)\))?)"


class Season(db.Model):
    display = db.ReferenceProperty(Display)

    name = db.StringProperty(required=True)
    start = db.DateProperty(required=True)

    def __str__(self):
        return self.name

class SeasonForm(ModelForm):
    class Meta:
        model = Season
        exclude = ['display']

class Location(db.Model):
    display = db.ReferenceProperty(Display)

    name = db.StringProperty(required=True)
    details = db.TextProperty(required=True)

    def __str__(self):
        return self.name

class LocationForm(ModelForm):
    class Meta:
        model = Location
        exclude = ['display']

class Soloist:
    name = ''
    instrument = None
    link = None

    def __init__(self, name, instrument=None, link=None):
        self.name = name
        if instrument:
            self.instrument = instrument.strip()

        self.link = link

    def __str__(self):
        
        if self.link:
            # the whole shebang
            return '; %s, %s (%s)' % (self.name, self.instrument, self.link)

        # no link
        return '; %s, %s' % (self.name, self.instrument)


class Piece:
    tba = False

    name = ''
    composer = ''
    work = None # IE a movement FROM a work
    #soloist = ''
    #soloist_instrument = ''
    #soloist_link = ''
    soloists = None

    pregex = re.compile(PIECES_REGEX)
    sregex = re.compile(SOLOIST_REGEX)

    def __init__(self, data):
        #print repr(data.strip().lower())
        if data is None or data.strip().lower() == 'tba':
            self.tba = True
            return

        # let's be smart and use regular expressions
        m = self.pregex.search(data)
        #for key in ['name','composer','soloist','soloist_instrument','soloist_link']:
        for key in ['name','composer','work']:
            self.__dict__[key] = m.group(key)

        if m.group('soloists'):
            self.soloists = []
            for ms in self.sregex.finditer(m.group('soloists')):
                self.soloists.append(Soloist(ms.group('soloist'), ms.group('instrument'), ms.group('link')))

        '''
        by = data.find('by')
        semi = data.find(';')
        self.name = data[:by].trim()
        if semi < 0:
            self.composer = data[by+2:].trim()
            self.soloist = None
            self.soloist_link = None
        else:
            self.composer = data[by+2:semi].trim()

            self.soloist = data
            self.soloist_link = soloist_link
        '''

    def __str__(self):
        ''' The "form value" string'''
        if self.tba:
            return 'TBA'

        # build soloists
        soloists_buf = ''
        if self.soloists:
            for s in self.soloists:
                soloists_buf += unicode(s)

        # add "from"
        work_buf = ''
        if self.work:
            work_buf = " from %s" % self.work

        # put it all together
        return '%s%s by %s%s' % (self.name, work_buf, self.composer, soloists_buf)

class PiecesProperty(db.StringListProperty):

    regex = re.compile(PIECES_REGEX)

    def get_form_field(self, **kwargs):

        defaults = {'widget': forms.Textarea}
        defaults.update(kwargs)
        return super(PiecesProperty, self).get_form_field(**defaults)

    def get_value_for_form(self, instance):
        buf = ''
        pieces = getattr(instance, self.name)
        if len(pieces):
            for item in pieces:
                buf += unicode(item) + '\n'
        else:
            buf += 'TBA\n'
            
        return buf[:-1] # we don't want the trailing linefeed

    def make_value_from_datastore(self, value):
        ret = []
        for line in value:
            p = Piece(line)
            if not p.tba:
                ret.append(p)

        return ret

    #def empty(self, value):
        #print value
        #return not value or not len(value) or value[0].tba

    def validate(self, value):

        #value = super(PiecesProperty, self).validate(value)
        for line in value:
            if isinstance(line, Piece):
                break # heh, we're fine

            if line.strip().lower() == 'tba':
                continue

            m = self.regex.search(line)
            if not m:
                raise BadValueError('Property %s must be TBA or of the format "PIECE by COMPOSER{; SOLOIST, INSTRUMENT {(LINK)}}', self.name)
     
            if not m.groups('name') and m.groups('composer'):
                raise BadValueError('Property %s must be TBA or of the format "PIECE by COMPOSER{; SOLOIST, INSTRUMENT {(LINK)}}', self.name)

        # should be fine if we get here
        return value


class Concert(db.Model):
    display = db.ReferenceProperty(Display)
    season = db.ReferenceProperty(Season)

    name = db.StringProperty(required=True)
    location = db.ReferenceProperty(Location, required=True)
    time = db.DateTimeProperty(required=True)

    pieces = PiecesProperty(indexed=False,default=None)

    soloist = db.StringProperty()
    soloist_link = db.StringProperty()

class ConcertForm(ModelForm):
    class Meta:
        model = Concert
        exclude = ['display', 'season']


class ConcertDisplay(AbstractDisplay):

    def __init__(self, disp):
        super(ConcertDisplay, self).__init__(disp)

    def build_template(self, template_values):
        '''Add whatever variables we provide to the template_values dict'''

        q = Season.all()
        q.order('-start')
        seasons = []
        for s in q:
            cq = Concert.all()
            cq.filter('season = ', s)
            cq.order('time')
            seasons.append({'name':s.name, 'concerts':cq})

        # calculate next concert
        q = Concert.all()
        q.filter('time > ', datetime.now())
        q.order('time')
        next_concert = q.get()

        if not next_concert:
            # okay... just get most recent?
            q = Concert.all()
            q.order('-time')
            next_concert = q.get()

        template_values[self.display.template_name()] = {
            'seasons':seasons,
            'next':next_concert
        }

    def get(self, handler, template_values):

        mode = handler.request.get('m')
        if not mode:
            # main page
            locations = []
            ls = Location.all()
            for l in ls:
                locations.append(LocationForm(prefix=l.key().id(),instance=l))
            locations.append(LocationForm(prefix='new'))
            template_values['locations'] = locations
            template_values['action_location'] = handler.request.uri + "&m=location"

            seasons = []
            ls = Season.all()
            ls.order('start')
            for l in ls:
                seasons.append(SeasonForm(prefix=l.key().id(),instance=l))
            seasons.append(SeasonForm(prefix='new'))
            template_values['seasons'] = seasons
            template_values['action_season'] = handler.request.uri + "&m=season"

            handler.response.out.write(template.render('static/display-concert.html', template_values))
        elif mode == 'concerts':
            # "concert" page-- add concerts
            
            id_ = handler.request.get('season')
            if id_:
                season = Season.get_by_id(long(id_), self.display)
                if season:
                    template_values['season'] = season
    
            if 'season' not in template_values:
                handler.response.out.write("No such season")
                return

            concerts = []
            ls = Concert.all()
            ls.filter('season =', template_values['season'])
            ls.order('time')
            for l in ls:
                concerts.append(ConcertForm(prefix=l.key().id(),instance=l))

            concerts.append(ConcertForm(prefix='new'))

            template_values['concerts'] = concerts

            handler.response.out.write(template.render('static/display-concert-season.html', template_values))


    def post(self, handler, template_values):
        super(ConcertDisplay, self).post(handler, template_values)

        mode = handler.request.get('m')

        if mode == 'season':
            self.post_season(handler, template_values)
            return
        elif mode == 'location':
            self.post_location(handler, template_values)
            return
        elif mode == 'concerts':
            self.post_concerts(handler, template_values)

    def post_concerts(self, handler, template_values):
            
        id_ = handler.request.get('season')
        if id_:
            season = Season.get_by_id(long(id_), self.display)
            if season:
                template_values['season'] = season

        if 'season' not in template_values:
            handler.response.out.write("No such season")
            return

        concerts = []
        ls = Concert.all()
        ls.filter('season =', template_values['season'])
        ls.order('time')
        for l in ls:
            # update existing ones
            deleteName = 'delete-%d' % l.key().id()
            if handler.request.POST.has_key(deleteName) and handler.request.POST[deleteName].lower() == 'on':
                # kill it
                l.delete()
                continue

            curr = ConcertForm(prefix=l.key().id(), data=handler.request.POST, instance=l)
            if curr.is_valid():
                curr.save()

            concerts.append(curr)

        newConcert = ConcertForm(prefix='new',data=handler.request.POST)
        if newConcert.is_valid():
            entity = newConcert.create(parent=self.display, commit=False)
            entity.display = self.display.key()
            entity.season = template_values['season'].key()
            entity.put()

            # add it
            concerts.append(ConcertForm(prefix=entity.key().id(),instance=entity))
            
            # allow for a new one
            concerts.append(ConcertForm(prefix='new'))
        else:
            concerts.append(newConcert)

        template_values['concerts'] = concerts

        handler.response.out.write(template.render('static/display-concert-season.html', template_values))

    def post_location(self, handler, template_values):
        locations = []
        ls = Location.all()
        for l in ls:
            # update existing locations
            deleteName = 'delete-%d' % l.key().id()
            if handler.request.POST.has_key(deleteName) and handler.request.POST[deleteName].lower() == 'on':
                # kill it
                l.delete()
                continue

            curr = LocationForm(prefix=l.key().id(), data=handler.request.POST, instance=l)
            if curr.is_valid():
                curr.save()

            locations.append(curr)

        newLocation = LocationForm(prefix='new',data=handler.request.POST)
        if newLocation.is_valid():
            entity = newLocation.create(parent=self.display, commit=False)
            entity.display = self.display.key()
            entity.put()
            locations.append(LocationForm(instance=entity, prefix=entity.key().id()))

        locations.append(LocationForm(prefix='new'))
        template_values['locations'] = locations
        template_values['action_location'] = "/admin/update/?id=%d&m=location" % self.display.key().id()

        seasons = []
        ls = Season.all()
        ls.order('start')
        for l in ls:
            seasons.append(SeasonForm(prefix=l.key().id(),instance=l))
        seasons.append(SeasonForm(prefix='new'))
        template_values['seasons'] = seasons
        template_values['action_season'] = "/admin/update/?id=%d&m=season" % self.display.key().id()

        handler.response.out.write(template.render('static/display-concert.html', template_values))

    def post_season(self, handler, template_values):
        locations = []
        ls = Location.all()
        for l in ls:
            locations.append(LocationForm(prefix=l.key().id(),instance=l))
        locations.append(LocationForm(prefix='new'))
        template_values['locations'] = locations
        template_values['action_location'] = "/admin/update/?id=%d&m=location" % self.display.key().id()

        seasons = []
        ls = Season.all()
        ls.order('start')
        for l in ls:
            # update existing seasons
            deleteName = 'delete-%d' % l.key().id()
            if handler.request.POST.has_key(deleteName) and handler.request.POST[deleteName].lower() == 'on':
                # kill it
                l.delete()
                continue

            curr = SeasonForm(prefix=l.key().id(), data=handler.request.POST, instance=l)
            if curr.is_valid():
                curr.save()

            seasons.append(curr)

        newSeason = SeasonForm(prefix='new', data=handler.request.POST)
        if newSeason.is_valid():
            entity = newSeason.create(parent=self.display, commit=False)
            entity.display = self.display.key()
            entity.put()
            seasons.append(SeasonForm(instance=entity, prefix=entity.key().id()))

        seasons.append(SeasonForm(prefix='new'))
        template_values['seasons'] = seasons
        template_values['action_season'] = "/admin/update/?id=%d&m=season" % self.display.key().id()

        handler.response.out.write(template.render('static/display-concert.html', template_values))
