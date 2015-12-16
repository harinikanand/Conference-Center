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

Task 3: Work on indexes and queries
=====================================
Implemented 2 endpoint methods for the following queries:
1. Query sessions of a particular Speaker that are less than a given duration
path: sessions/getSessionsBySpeakerlessthan1hourduration

2. Query sessions of a particular type on a particular date
path: sessions/getSessionsOfATypeOnAParticularDate

Also implemented an endpoint method for a query for all non-workshop sessions before 7 pm.
path: sessions/getSessionsNotWorkshopsNotAfter7pm

Task 4: Add a task
=====================================
When a new session is added to a conference, the speaker is checked. If there is more than one session by this speaker at this conference,
then wrote the functionality to add a new Memcache entry that informs of the speaker and other session names

Also defined and implemented endpoint method
- getFeaturedSpeaker()
path: session/featuredspeaker

Files modified:
app.yaml
index.yaml
main.py
conference.py
models.py