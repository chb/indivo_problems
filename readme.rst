Standalone Branch: Indivo Problems App
======================================

This branch of the app is intended to run standalone,
without being bundled into the UI. It can be used for
demo purposes, or as a base for modification to use 
with other apps.

Install/Setup
-------------

* Clone this repo::
  
    git clone git://github.com/chb/indivo_problems

* Check out the standalone branch::
  
    git checkout standalone

* Pull down submodules::
 
    git submodule init
    git submodule update

* Configure your settings::

    cp settings.py.default settings.py
    [vi | emacs | etc.] settings.py

  Make sure to update:

  * ``INDIVO_SERVER_OAUTH``: oauth credentials for your app.

  * ``INDIVO_SERVER_LOCATION``: location of a running Indivo 
    instance

  * ``INDIVO_UI_SERVER_BASE``: location of a running Indivo UI
    app.

  * ``APP_HOME``: the location of your app (in your filesystem)

Running the App
---------------

* Run the app! ::

    python manage.py runserver 0.0.0.0:{YOUR_PORT}

  Make sure your port corresponds to the port in the app
  manifest that you've registered with Indivo
