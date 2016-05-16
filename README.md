# Telegram Bot: Alfa-Bank Card-2-Card Transfer Assistant 

You can view the working app by quering *@AlfabankC2CBot* in Telegram.
The bot works on top of the web server Tornado 4.3, to run it, simply execute the run.py file and direct the requests to '/'.

## Technology Stack ##
* Azure VM
* Azure DocumentDB
* Alfa-Bank UAPI

## Installation ##

To install the requirements, run
`pip install -r requirements.txt`
Besides required libraries, it needs:
* `ffmpeg` installed and added to _PATH_ to work with audio.
* The directory `file/` needs to have the write access granted to the user who runs web server.
* The web server requires an SSL certificate to receive updates by webhook. The certificate should be located in `cert/alfa.key` and `cert/alfa.pem`
* The Telegram webhook must be set up to receive updates.

## App Run ##
In the simplest case, run
`python run.py`
I recommend to daemonize this call by using _supervisord_.
