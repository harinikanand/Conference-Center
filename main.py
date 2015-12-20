#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from conference import ConferenceApi
from conference import MEMCACHE_FEATURED_SPEAKER_KEY
from google.appengine.ext import ndb
from google.appengine.api import memcache

from models import Session
import logging


class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        return ConferenceApi._cacheAnnouncement() 


class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Conference!',            # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )

class SetFeaturedSpeakerHandler(webapp2.RequestHandler):
    def post(self):
        """Set Memcache for featured speaker and email about others sessions of that speaker"""

        # If there is more than one session by this speaker at this conference,
        # add a new Memcache entry that features the speaker and session names.
        sessions = Session.query(Session.speaker == self.request.get('featured_speaker'))
        announcement = '%s %s %s %s' % (
                'Featured Speaker ', self.request.get('featured_speaker'),
                ' has more than one session Please check out sessions:',
                ', '.join(session.name for session in sessions))

        # Save to memcache under the featured speaker key
        memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, announcement)
        
        email_body = 'Additional Info:\r\n\r\n%s %s' % (self.request.get(
                'featured_speaker'), announcement)
        
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'New featured speaker!',            # subj
            email_body
        )

app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/set_memcache_notif_and_send_featured_speaker_email', SetFeaturedSpeakerHandler),
], debug=True)