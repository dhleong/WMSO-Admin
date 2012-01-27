#!/usr/bin/env python
#
#
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from django.template import Template, Context

import display
import page
import res

class MainHandler(webapp.RequestHandler):
    def get(self, link):
        if not len(link.strip()):
            link = 'index.html'

        # check for a resource
        if res.exists(link):
            #print 'huh?'
            res.handle_view(self, link)
            return

        q = page.DbPage.all()
        q.filter('link = ', link)

        dbPage = q.get()
        if not dbPage:
            # TODO proper 404 headers and such
            self.response.out.write('no such page')
            return

        pg = page.Page(dbPage)

        template_vars = {}
        pg.build_template(template_vars)

        t = Template(pg.get_template())
        self.response.out.write(t.render(Context(template_vars)))


def main():
    application = webapp.WSGIApplication([('/(.*)', MainHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
