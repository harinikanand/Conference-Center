#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize

from models import Session
from models import SessionForm
from models import SessionForms

from models import UserWishList
from models import UserWishListForm
from models import UserWishListForms

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.net.proto.ProtocolBuffer import ProtocolBufferDecodeError


from models import StringMessage

from utils import getUserId

from settings import WEB_CLIENT_ID

import logging
import string

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED_SPEAKER"

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

DEFAULTS_SESSION = {
    "highlights": "Not Available",
    "typeOfSession": "talk",
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2),
    speaker=messages.StringField(3),
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

USERWISHLIST_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    sessionKey=messages.StringField(1),
)

USERWISHLIST_POST_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    sessionKey=messages.StringField(1),
)

SESSIONS_QUERY_ONE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1),
    duration=messages.IntegerField(2),
)

SESSIONS_QUERY_TWO_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    typeOfSession=messages.StringField(1),
    date=messages.StringField(2),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', 
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        # TODO 2: add confirmation email sending task to queue
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )

        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id =  getUserId(user)
        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
                conferences]
        )


# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = '%s %s' % (
                'Last chance to attend! The following conferences '
                'are nearly sold out:',
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        # TODO 1
        # return an existing announcement from Memcache or an empty string.
        announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
        if not announcement:
            announcement = ""
        return StringMessage(data=announcement)

# - - - C O N F E R E N C E       C E N T R A L    - - - - - - - -
# - - - Task 1:  Session objects - - - - - - - - - - - - - - - - -

    def _copySessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(session, field.name):
                # convert Date to date string; just copy others
                if field.name == 'date' or field.name == 'startTime':
                    setattr(sf, field.name, str(getattr(session, field.name)))
                else:
                    setattr(sf, field.name, getattr(session, field.name))
            elif field.name == "sessionUrlSafeKey":
                setattr(sf, field.name, session.key.urlsafe())
        
        sf.check_initialized()
        return sf

    def _createSessionObject(self, request):
        """Create or update Session object, returning SessionForm/request."""
        # Obtain user details to send an email at the end of creation
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # check all required fields are filled in
        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        if not request.speaker:
            raise endpoints.BadRequestException("Session 'speaker' field required")

        if not request.duration:
            raise endpoints.BadRequestException("Session 'duration' field required")

        if not request.date:
            raise endpoints.BadRequestException("Session 'date' field required")

        if not request.startTime:
            raise endpoints.BadRequestException("Session 'startTime' field required")

        # Obtain the creator of the conference provided and check against the user
        # If the creator of the conference is not the user
        # Return an error
        try:
           conference_key = ndb.Key(urlsafe=request.websafeConferenceKey)
           conf = conference_key.get()
        except  ProtocolBufferDecodeError:
            raise endpoints.BadRequestException("Invalid websafeConferenceKey provided")

        if conf is not None:
           if conf.organizerUserId != getUserId(user): 
              raise endpoints.BadRequestException("UserId does not match Conference Organizer ID")

        # copy SessionForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

  
        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS_SESSION:
            if data[df] in (None, []):
                data[df] = DEFAULTS_SESSION[df]


        # convert date and time from strings to Date objects; 
        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'][:5], "%H:%M").time()

        # Save the typeOfSession in lower case to make comparison easier when querying
        sessionTypeStr = data['typeOfSession']
        data['typeOfSession'] = str(sessionTypeStr).lower()

        # generate Parent Key based on Conference WSK
        parent_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        s_id = Session.allocate_ids(size=1, parent=parent_key)[0]
        s_key = ndb.Key(Session, s_id, parent=parent_key)
        data['key'] = s_key
        del data['sessionUrlSafeKey']

        # create Session, send email to user confirming
        # creation of Session & return (modified) SessionForm

        session = Session(**data)
        session.put()

        # Find if more than one session exists for a speaker
        sessions_count_by_speaker = Session.query(Session.speaker == request.speaker).count() + 1

        if sessions_count_by_speaker > 1:
            taskqueue.add(params={'email': user.email(),
            'featured_speaker': request.speaker},
            url='/tasks/set_memcache_notif_and_send_featured_speaker_email')


        return self._copySessionToForm(session)


    @endpoints.method(SESSION_POST_REQUEST, SessionForm, 
            path='conference/{websafeConferenceKey}/createSession',
            http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session."""
        return self._createSessionObject(request)

    @endpoints.method(SESSION_GET_REQUEST, SessionForms, 
            path='conference/{websafeConferenceKey}/getConferenceSessions',
            http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Get All Conference Sessions"""
        # create ancestor query for all key matches for this conference
        parent_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        sessions = Session.query(ancestor=parent_key)


        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    @endpoints.method(SESSION_GET_REQUEST, SessionForms, 
            path='conference/{websafeConferenceKey}/getConferenceSessionsByType/{typeOfSession}',
            http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Get Conference Sessions by Type of Session"""
        # create a query to first get list of sessions of ancestor represented by conf web safe key
        # Then filter by type of Session
        parent_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        sessions = Session.query(ancestor=parent_key)
        sessions = sessions.filter(Session.typeOfSession == request.typeOfSession.lower())
        
        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    @endpoints.method(SESSION_GET_REQUEST, SessionForms, 
            path='conference/{speaker}',
            http_method='GET', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Get All Conference Sessions of a particular speaker"""

        # Query for all sessions then filter by speaker
        sessions = Session.query()
        sessions = sessions.filter(Session.speaker == request.speaker)

        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

# - - - Task 2:  User Wish List objects - - - - - - - - - - - - - - - - -

    def _copyUserWishListToForm(self, userwishlist):
        """Copy relevant fields from UserWishList to UserWishListForm."""
        uwlf = UserWishListForm()
        for field in uwlf.all_fields():
            if hasattr(userwishlist, field.name):
                # convert Date to date string; just copy others
                if field.name == "dateAddedToWishList":
                    setattr(uwlf, field.name, str(getattr(userwishlist, field.name)))
                else:
                    setattr(uwlf, field.name, getattr(userwishlist, field.name))
        uwlf.check_initialized()
        return uwlf


    def _addSessionToUserWishList(self, request):
        """Add a Session to a User's WishList"""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # Check the required fields are present
        if not request.sessionKey:
            raise endpoints.BadRequestException("Session 'session Key' field required")

        # Obtain the session key
        # Then obtain the session using the session key
        # If session does not exist, return session does not exist
        try:
           s_key = ndb.Key(urlsafe=request.sessionKey)
           if s_key is not None:
              session = s_key.get()
        except ProtocolBufferDecodeError: 
            raise endpoints.BadRequestException("Session key Invalid")

        if  not session:
            raise endpoints.BadRequestException("Session does not exist")

        
        # copy from user wish list from to dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        data['userID'] = user_id
    
        # generate Profile Key based on user ID and User Wish list
        # ID based on Profile key get user wish list key from ID
        p_key = ndb.Key(Profile, user_id)
        userwishlist_id = UserWishList.allocate_ids(size=1, parent=p_key)[0]
        userwishlist_key = ndb.Key(UserWishList, userwishlist_id, parent=p_key)

        # Save the key and conference web safe key
        data['key'] = userwishlist_key
        data['conferenceWsk'] = session.websafeConferenceKey

        # create UserWishList, send email to user confirming
        # creation of User wish list & return (modified) User wish list Form
        userwishlist = UserWishList(**data)
        userwishlist.put()

        return self._copyUserWishListToForm(userwishlist)

    @endpoints.method(USERWISHLIST_POST_REQUEST, UserWishListForm, 
            path='profile/addSessionToWishList',
            http_method='POST', name='addSessionToWishList')
    def addSessionToWishList(self, request):
        """Add a session to the User's Wish list."""
        return self._addSessionToUserWishList(request)

    @endpoints.method(message_types.VoidMessage, UserWishListForms, 
            path='profile/getWishList',
            http_method='GET', name='getSessionsInWishList')
    def getSessionsInWishList(self, request):
        """Get all sessions of a user"""
        # Obtain user information and check user is logged in
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)
        # Obtain all user wish list matching the user id 
        userwishlist_sessions = UserWishList.query(UserWishList.userID == user_id)

        return UserWishListForms(items=[self._copyUserWishListToForm(session) for session in userwishlist_sessions])

    @endpoints.method(USERWISHLIST_POST_REQUEST, BooleanMessage, 
            path='profile/deleteSessionFromWishList',
            http_method='DELETE', name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        """Delete session(s) from a user wish list matching the session key"""

        # Check the required field is provided 
        if not request.sessionKey:
            raise endpoints.BadRequestException("Session 'session Key' field required")

        # Obtain all user wish list session matching the given sessionKey
        # and delete all of them
        userwishlist_session = UserWishList.query(UserWishList.sessionKey == request.sessionKey)
        for u in userwishlist_session:
            u.key.delete()
        retval = True
        # return deletion is sucessful
        return BooleanMessage(data=retval)

# - - - Task 3:  Indexes and 2 Queries - - - - - - - - - - - - - - - - -  

    @endpoints.method(SESSIONS_QUERY_ONE_GET_REQUEST, SessionForms,
    	              path='sessions/getSessionsBySpeakerlessthanequaltoduration',
                      http_method='GET',
                      name='getSessionsBySpeakerlessthanequaltoduration')
    def getSessionsBySpeakerlessthanequaltoduration(self, request):
        """Return sessions of a particular Speaker that are less than duration given"""

        # check all required fields are provided
        if not request.speaker:
            raise endpoints.BadRequestException("Session 'speaker' field required")
        if not request.duration:
            raise endpoints.BadRequestException("Session 'duration' field required")

        # Query Session Kind to obtain matches for given speaker and duration in the value provided
        sessions = Session.query(ndb.AND(Session.speaker == request.speaker,
        	                             Session.duration > 0,
        	                             Session.duration <= int(request.duration)))

        return SessionForms(items=[self._copySessionToForm(session) for session in sessions])


    @endpoints.method(SESSIONS_QUERY_TWO_GET_REQUEST, SessionForms,
    	              path='sessions/getSessionsOfATypeOnAParticularDate',
                      http_method='GET',
                      name='getSessionsOfATypeOnAParticularDate')
    def getSessionsOfATypeOnAParticularDate(self, request):
        """Return sessions of a particular type on a particular date"""

        # check all required fields are provided
        if not request.typeOfSession:
            raise endpoints.BadRequestException("Session 'typeOfSession' field required")
        if not request.date:
            raise endpoints.BadRequestException("Session 'date' field required")

        # Query Session entities to obtain matches for the given type of Session and date
        sessions = Session.query(ndb.AND(Session.typeOfSession == request.typeOfSession.lower(),
        	                             Session.date == datetime.strptime(request.date, "%Y-%m-%d").date()))

        return SessionForms(items=[self._copySessionToForm(session) for session in sessions])

    @endpoints.method(message_types.VoidMessage, SessionForms,
    	              path='sessions/getSessionsNotWorkshopsNotAfter7pm',
                      http_method='GET',
                      name='getSessionsNotWorkshopsNotAfter7pm')
    def getSessionsNotWorkshopsNotAfter7pm(self, request):
        """Returns non-workshop sessions before 7pm"""

        # Query Session entities to obtain matches that are before 7 pm starttime wise
        # then check if the type of session is not workshop.
        sessionlist = Session.query(Session.startTime < datetime.strptime("19:00", "%H:%M").time())
        sessions = []
        for s in sessionlist:
            if s.typeOfSession != "workshop":
            	sessions.append(s)

        return SessionForms(items=[self._copySessionToForm(session) for session in sessions])

# - - - Task 4:  Task Queues - - - - - - - - - - - - - - - - -  

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path='session/featuredspeaker',
                      http_method='GET',
                      name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return Featured speaker information from memcache."""
        # return memcache string for feature speaker if present or ""
        return StringMessage(data=memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY) or "")


api = endpoints.api_server([ConferenceApi]) # register API
