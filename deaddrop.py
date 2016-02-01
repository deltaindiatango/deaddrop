import re
import sys
import ctypes
from json import loads as json_decode, dumps as json_encode
from uuid import uuid4
from tornado import web, ioloop, gen, httpserver, netutil, process
from time import mktime, time
from hashlib import sha256
import copy


@web.stream_request_body
class drop(web.RequestHandler):

    def prepare(self):
        submission_args = {}
        keys = 'name text encoding'.split()
        for (k, v) in self.request.arguments.items():
            if k in keys:
                submission_args[k] = v[0]
            if k == 'expiry':
                val = float(re.findall('(\d*.?\d)', v[0])[0])
                conv = {'m': 60,
                        'min': 60,
                        'h': 60 * 60,
                        'hr': 60 * 60,
                        'd': 24 * 60 * 60,
                        'wk': 7 * 24 * 60 * 60,
                        'mo': 30 * 24 * 60 * 60}
                spec = re.findall('([a-z]+)', v[0].lower())
                if spec:
                    spec = spec[0].lower()
                    if spec in conv.keys():
                        val = val * conv[spec]
                submission_args['expiry'] = int(time()) + val
            if k == 'burn':
                burn = 1
                try:
                    burn = int(v[0])
                except:
                    pass
                submission_args['burn_after_reading'] = int(v[0])
        check_content_type = 'Content-Type' in self.request.headers
        check_content_type = check_content_type and 'application/x-www-form-urlencoded' != self.request.headers['Content-Type']
        if 'text' not in submission_args.keys() and check_content_type: 
            submission_args['text'] = self.request.arguments.keys()[0]
        else:
            submission_args['text'] = ''
        self.submission_args = submission_args

    def data_received(self, chunk):
        self.submission_args['text'] += chunk

    def post(self):
        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        user_submission = submission(**self.submission_args)
        self.settings['submissions'][user_submission.name] = user_submission
        if 'X-Tor2web' in self.request.headers.keys():
            base = self.request.protocol + '://' + \
                self.request.headers['X-Forwarded-Host']
        else:
            base = ''
        self.write(base + '/get?' + user_submission.name + '\r\n')

    def get(self):
        self.post()


class retrieve(web.RequestHandler):

    def get(self):
        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        name = ''
        raw = False
        submission = ''
        for (k, v) in self.request.arguments.items():
            if 'name' == k:
                name = self.request.arguments['name'][0]
            elif 'raw' == k:
                raw = True
            else:
                name = k
        if name in self.settings['submissions'].keys():
            submission = self.settings['submissions'][name].render(raw)
            self.write(submission)
            if self.settings['submissions'][name].burn_after_reading:
                self.flush(callback=self.settings['submissions'][name].burn)
            if self.settings['submissions'][name].text == '':
                self.settings['submissions'].pop(name)


class info(web.RequestHandler):

    def get(self):
        about_text = """

        minimalist ephemereal REST pastebin, offers three endpoints: post, get, source
        post takes either the text to be stored or a kv mapping with the following possible keys: name, text, expiry, burn
            burn is enabled by default, disable by setting it to 0.
            name is optional, if not provided it is a randomly generated 128 bit uuid.
            expiry is optional, if not provided it defaults to 1hr.
                it is a floating point or integer number of, presumably, seconds, with the following optional unit appended: m, min, h, hr, d, wk, mo
        get takes either the name to be retrieved or a kv mapping with the following possible keys: raw, name
            the presence of the raw key returns a json representation of the submission as it is stored in memory.
        source reads the currently executed source file from disk, compares it to an initial hash, and returns it.

    source hash: %s

    to verify the integrity of this service, match the above hash against `curl $server/source | sha256sum`

    basic usage: curl -H 'User-Agent: None' --data-binary "@file.txt" https://deaddrop6pdgft4z.onion.to/post 

""" % (self.settings['hash'])
        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        self.write(about_text)


class source(web.RequestHandler):

    def get(self):
        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        self_source = open(sys.argv[0]).read()
        self_hash = sha256(self_source)
        assert self_hash.hexdigest() == self.settings['hash']
        return self.write(self_source)


class submission(object):

    def __init__(self,
                 expiry=int(time()) + 60 * 60 * 24,
                 burn_after_reading=True,
                 name=None,
                 text=''):
        if name == None:
            name = uuid4().hex
        self.text = text
        self.name = name
        self.expiry = expiry
        self.burn_after_reading = burn_after_reading

    def render(self, raw=False):
        def okd_render(raw):
            if raw:
                return json_encode(self.__dict__)
            else:
                return str(self.text)

        t = ''
        if time() < self.expiry:
            t = okd_render(raw)
        else:
            self.burn()
        return t

    def burn(self):
        ctypes.memset(id(self.text) + 36, 0, len(self.text) + 1)
        self.text = ''


if __name__ == '__main__':
    source_hash = sha256(open(sys.argv[0]).read()).hexdigest()
    app = web.Application({
        '/post': drop,
        '/get': retrieve,
        '/source': source,
        '/': info
    }.items())
    app.settings['submissions'] = {}
    app.settings['hash'] = source_hash
    server = httpserver.HTTPServer(app, chunk_size=10240, max_body_size=10240)
    sockets = netutil.bind_sockets(1330, address='localhost')
    process.fork_processes(1)
    server.add_sockets(sockets)
    ioloop.IOLoop.current().start()
