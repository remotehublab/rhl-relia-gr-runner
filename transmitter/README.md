# runner

Create a virtual environment, but using system site packages to have access to gnuradio:

$ python3 -mvenv env --system-site-packages

Activate the environment:

$ . env/bin/activate
$ pip install -r requirements.txt

And then, every time you want to run it

$ . env/bin/activate
$ flask run
