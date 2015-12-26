Author: Harini Anand

Date: 12/14/2015

Project ID: confcenter-1156

Prerequisites:
1. Download and Install Python2.7 link: https://www.python.org/download/releases/2.7/
2. Download and Install Google App Engine SDK for python: https://cloud.google.com/appengine/downloads?hl=en#Google_App_Engine_SDK_for_Python
3. Download this project from github

How to run the Conference Central App:
1. Open the Google App Engine Launcher
2. Using File -> Existing Application, navigate to the folder where this project is downloaded.
3. To run locally:
    Highlight the row showing the "confcenter-1156" project and Select 'Run'
    Check the Logs to ensure the API server, module and admin server are started successfully
    Note the port used (default is 8080)
    Then using the browser, load the URL http://localhost:8080
4. To deploy:
    Highlight the row showing the "confcenter-1156" project and Select 'Deploy'
    In the console window, ensure deployment is successful and the api version is updated
    Then using the browser, load the URL https://confcenter-1156.appspot.com

Tasks implemented in the project:

Task 1: Add Sessions to a Conference
====================================
- Defined and implemented Session class and SessionForm with the following fields:
Session name
highlights
speaker
duration
typeOfSession
date
start time (in 24 hour notation so it can be ordered).

- Defined and implemented the following Endpoint methods
  - getConferenceSessions(websafeConferenceKey) -- Given a conference, return all sessions
  path: conference/{websafeConferenceKey}/getConferenceSessions

  - getConferenceSessionsByType(websafeConferenceKey, typeOfSession) Given a conference, return all sessions of a specified type (eg lecture, keynote, workshop)
  path: conference/{websafeConferenceKey}/getConferenceSessionsByType/{typeOfSession}

  - getSessionsBySpeaker(speaker) -- Given a speaker, return all sessions given by this particular speaker, across all conferences
  path: conference/{speaker}

  - createSession(SessionForm, websafeConferenceKey) -- open only to the organizer of the conference
    path: conference/{websafeConferenceKey}/createSession

DESIGN:
======
I designed the 3 classes in models.py to implement session in conference.py
THey are Session, SessionForm and SessionForms

Session Kind:
name - stores the name of the session
Speaker - stores the name of the speaker of that session
duration - stores the duration of the session in minutes
date - stores the date in the YYYY-MM-DD format
startTime - stores the starting time fo the session in 24 hour format
typeOfsession - stores the type of Session (e.g. Talk, Pre-Conference, Workshop etc) (defaulted to talk if information is not given)
highlights - stores the highlights specific to the session (defaulted to Not Available if information is not provided)
websafeConferenceKey - stores the web safe key for the conference that it is a session of


SessionForm  class contains all the above fields in Session plus sessionUrlSafeKey which saves the web safe
key of the session created. This Form class is used for display purposes.


SessionForms class contains 1 or more SessionForm so as to be able to show information about multiple sessions.
This Form class is used for display purposes.

Endpoint implementations:
A> createSession(SessionForm, websafeConferenceKey) - This function takes a websafekey of a conference and a SessionForm and creates a session. 

To implement the method, the following steps are performed:
 - Obtained the current user information
 - Verify the required fields are filled out (required fields are name, speaker, duration, date and startTime )
 - Verify the OrganizerUserID matches the userID of the current user
 - Then a session entity is created with the conference entity of which the websafeConferencekey belongs to as a Parent.
 - The fields (name, speaker, duration, date, startTime, typeOfSession, highlights and websafeConferenceKey) are filled in and the session entity created is saved to datestore.
 - Then the number of sessions offered by given speaker is determined. 
 - If the number of sessions offered by that spearker is > 1, set a memcache notification for the spearker to show all the sessions being offered by the speaker and also send an email to the current user.
  - return created entry as sessionForm

B>  getConferenceSessions(websafeConferenceKey) - This function, given a conference, return all sessions

To implement the method, the following steps are performed:
  - Obtain the parent_key, a conference entity based on the web safe key conference key
  - Query Session for all the entities with the parent_key 
  - return results as SessionForms

C>  getConferenceSessionsByType(websafeConferenceKey, typeOfSession) - This function, given a conference, return all sessions of a specified type 
 
To implement the method, the following steps are performed:
  - Obtain the parent_key, a conference entity based on the web safe key conference key
  - Query Session for all the entities with the parent_key 
  - Filter the query results by typeOfSession (typeOfSession is converted to lower case as that is how it is saved when the Session object is created)
  - return results as SessionForms

D> getSessionsBySpeaker(speaker) -- This function, given a speaker, return all sessions given by this particular speaker, across all conferences


To implement the method, the following steps are performed:
  - Query Session for all entities 
  - Filter the query results by speaker name 
  - return results as SessionForms


Task 2: Add Sessions to User Wishlist
=====================================
- Defined and implemented the following Endpoints methods

- addSessionToWishlist(SessionKey) -- adds the session to the user's list of sessions they are interested in attending
path: profile/addSessionToWishList
Note: In my design, user would be able to add the same session multiple times to the wish list.
Each time will be saved with a new dateAddedToWishList.

- getSessionsInWishlist() -- query for all the sessions in a conference that the user is interested in
path: profile/getWishList

- deleteSessionInWishlist(SessionKey) -- removes the session from the user’s list of sessions they are interested in attending  
path: profile/deleteSessionFromWishList

DESIGN
======
I designed the 3 classes in models.py to implement userwishlist in conference.py
THey are UserWishList, UserWishListForm, UserWishListForms

UserWishList Kind:
userID - ID of the user
conferenceWsk - stores the web safe key for the conference that the session is created for
sessionKey - stores the web safe key of the session that is added to the UserWishList
dateAddedToWishList - date the session is added to the UserWishList
Note: There is no condition to prevent a user from adding a session multiple times to the UserWishList.
Only the dateAddedToWishList will be different in that case. 

UserWishListForm  class contains all the above fields of UserWishList as StringFields.This Form class is used for display purposes.

UserWishListForms class contains 1 or more UserWishListForm so as to be able to show information about multiple sessions in the UserWishList. This Form class is used for display purposes.

Endpoint implementations:
A> addSessionToWishlist(SessionKey) -- adds the session to the user's list of sessions they are interested in attending
To implement the method, the following steps are performed:
 - Obtained the current user information
 - Verify the required fields are filled out (session Key )
 - The validity of the sessionKey is ensured
 - Then a userWishList entity is created with the Profile entity that matches the user as a parent.
 - The sessionKey, websafeConferenceKey of that session, UserID and dateAddedToWishlist are filled in the entity.
 - The entity is saved to datestore
 - return created entry as UserWishListForm

Note: In my design, user would be able to add the same session multiple times to the wish list.
Each time will be saved with a new dateAddedToWishList.

B> getSessionsInWishlist() -- query for all the sessions in a conference that the user is interested in

To implement the method, the following steps are performed:
 - Obtained the current user information
 - Query UserWishList find all UserWishlists that have the current user's userID as UserID
 - return the results as UserWishListForms

C> deleteSessionInWishlist(SessionKey) -- removes the session from the user’s list of sessions they are interested in attending  

To implement the method, the following steps are performed:
 - Ensure the sessionKey is filled out
 - Query UserWishList find all UserWishlists that have the sessionKey provided
 - Delete all the userWishList entities returned in the query results
 - return True

Task 3: Work on indexes and queries
=====================================
Implemented 2 endpoint methods for the following queries:
1. Query sessions of a particular Speaker that are less than a given duration
path: sessions/getSessionsBySpeakerlessthanequaltoduration

PURPOSE: The users of the conference central might be interested in conference sessions of 
a particular speaker however may not have time to attend long sessions.
The users may prefer short sessions. In that case, the above query helps those users to query based on 
a particular speaker for a session duration less than or equal to the duration the user is interested in.


IMPLEMENTED DESIGN:
===================

To implement the method, the following steps are performed:
 - Ensure required fields in query form are filled out (speaker and duration)
 - Query Session to obtain entities that have given speaker name and duration is between 0 and the given duration
 - return the results as SessionForms

ALTERNATE DESIGN (PROPOSAL NOT IMPLEMENTED):
============================================
 - Ensure required fields in query form are filled out (speaker and duration)
 - Query Session to obtain entities that match the speaker (q = Session.query (Session.speaker == request.speaker))
 - Fitler the above query results for Session.duration <= request.duration (q = q.filter(Session.duration <=request.duration))
 - return the results (q) as SessionForms

2. Query sessions of a particular type on a particular date
path: sessions/getSessionsOfATypeOnAParticularDate

PURPOSE: The users of the conference central might be interested in conference sessions of 
on a particular day that are only workshops or talks or seminars etc.

IMPLEMENTED DESIGN:
===================

To implement the method, the following steps are performed:
 - Ensure required fields in query form are filled out (typeOfSession and date)
 - Query Session to obtain entities that have given typeOfSession (in lower case as when the entity is created, the typeOfsession is converted to lower case) and given date
 - return the results as SessionForms

ALTERNATE DESIGN (PROPOSAL NOT IMPLEMENTED):
============================================
 - Ensure required fields in query form are filled out (typeOfSession and date)
 - Query Session to obtain entities that match a particular date (q = Session.query (Session.date == datetime.strptime(request.date, "%Y-%m-%d").date()))
 - Fitler the above query results for typeOfsession (convert the given typeOfSession to lower case)  (q = q.filter(Session.typeOfSession == request.typeOfSession.lower()))
 - return the results q as SessionForms

3. Also implemented an endpoint method for a query for all non-workshop sessions before 7 pm.
path: sessions/getSessionsNotWorkshopsNotAfter7pm

DATASTORE QUERY LIMITATION: THis query requires 2 inequalities and that results in the below datastore query error:
BadRequestError: Only one inequality filter per query is supported. Encountered both typeOfSession and startTime

 
IMPLEMENTED DESIGN:
===================
To implement the method, the following steps are performed:
 - Query Session to obtain entities for which startime is less than "19:00" (as startTime is saved in 24 hour format)
 - Then iterate through the results to determine which have typeOfSession not set to "workshop"
 - return those results as SessionForms

ALTERNATE DESIGN (PROPOSAL NOT IMPLEMENTED):
===========================================
- Query Session to obtain entities with all types of Session (pre-conference, talk, seminar etc) except "workshop"
  for which the startTime is less than 19:00.
  But it is tedious and not efficient.
   sessions = Session.query( ndb.AND (ndb.OR ((Session.typeOfSession == "talk"),
                                              (Session.typeOfSession == "pre-conference"),
                                              (Session.typeOfSession == "seminar")),
                                               Session.startTime < datetime.strptime("19:00", "%H:%M").time()))

Task 4: Add a task
=====================================
When a new session is added to a conference, the speaker is checked. If there is more than one session by this speaker at this conference,
then wrote the functionality to add a new Memcache entry that informs of the speaker and other session names

Also defined and implemented endpoint method
- getFeaturedSpeaker()
path: session/featuredspeaker

DESIGN:
When creating a session, after creating an entity and saving to datastore, a query is run on Session Kind to determine if there are other Session entities with the speaker name provided, if so, then using a task queue, an announcement showing the name of that speaker along with all the other sessions offerend by the speaker is written to the memcache (key is FEATURED_SPEAKER)

getFeaturedSpeaker() returns the announcement saved to Memcache under the key FEATURED_SPEAKER.


Files modified:
app.yaml
index.yaml
main.py
conference.py
models.py