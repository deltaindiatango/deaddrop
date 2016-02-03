#! /usr/bin/python

hostname = 'https://deaddrop6pdgft4z.onion.to/post'

def deaddrop(text):
    import urllib
    import urllib2
    r = urllib2.Request(hostname, text, headers={"User-Agent": "Mozilla/5.0"})
    return urllib2.urlopen(r).read()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print deaddrop(open(sys.argv[1]).read())
    else:
        print deaddrop(sys.stdin.read())
