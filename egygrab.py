from ast import literal_eval
import enum
from numexpr import evaluate
from enum import Enum

import threading
import traceback
import requests
import argparse
import base64
import pickle
import time
import sys
import re
import os

__version__ = "1.4.2"


def check_updates(current_filename):
    URL = 'https://raw.githubusercontent.com/Sraq-Zit/egygrab/master/egygrab.py'
    new_code = requests.get(URL).text
    version = re.search(r'__version__\s*=\s*[\'"](.+?)[\'"]', new_code)
    if not version: return
    if __version__ != version[1]:
        res = ''
        while res not in ['y', 'n']: res = input('There is a new update, update ?')
        if res == 'y':
            try:
                with open(current_filename, 'w') as f:
                    f.write(new_code)
                print('UPDATED! Run the command once again, exiting ..')
                time.sleep(2)
                sys.exit()
            except Exception as e:
                print('ERROR: could not update')


class TYPES(Enum): 
    episode = 'episode'
    masrahiya = 'masrahiya'
    season = 'season'
    series = 'series'
    movie = 'movie'
    anime = 'anime'
    show = 'show'
    wwe = 'wwe-show'


class EgyGrab():
    def __init__(self, url):
        self.dl_url = self.url = url
        self.type = None
        for t in TYPES:
            if '/%s/'%t.value in url:
                self.type = TYPES[t.name]
                break
        if self.type is None: raise ValueError('There is nothing to download :(')
        self.threads = []
        self.results = []
    
    def grab(self, quality='1080p', cookies=True):
        if self.type in [TYPES.episode, TYPES.masrahiya, TYPES.movie]:
            return [self.__grab_item(self.url, quality, cookies)[1]]

        
        urls = [self.url]
        if self.type in [TYPES.series, TYPES.anime, TYPES.wwe, TYPES.show]:
            html = requests.get(self.url).text
            urls = reversed(['https://w.egybest.org' + match[1] for match in re.finditer(r'(\/season\/.+?)"', html)])

        self.threads = []
        self.results = []
        for url in urls:
            season_results = []
            i = 0
            html = requests.get(url)
            html = html.text
            for match in re.finditer(r'(\/episode\/.+?)"', html):
                t = threading.Thread(target=lambda: season_results.append(self.__grab_item('https://w.egybest.org' + match[1], quality, cookies, i)))
                i+=1
                t.start()
                self.threads.append(t)
            for t in self.threads: t.join()

            self.results += sorted(season_results, key=lambda x: x[0], reverse=True)
            print('"%s" Grabbed!'%re.search(r'.+?\/season\/(.+?)(\/|$)', url)[1])

        return [v for _, v in self.results]

    
    def __grab_item(self, url, quality='1080p', last_session=True, id=0):
        try:
            sess = requests.Session()
            sess.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36',
            }
            cookiesPath = 'cookies/cookies_%s.pickle'%str(id)
            if os.path.exists(cookiesPath) and last_session:
                sess.cookies = pickle.load(open(cookiesPath, 'rb'))
            html = sess.get(url).text
            # open('test.html', 'w', encoding='utf-8').write(html)
            # html = open('html.txt', encoding='utf-8').read()
            # print('item page loaded!')

            # print(html)
            html = html.replace("'+'", '')
            # call = 'https://w.egybest.org/api?call='+re.search(r'rel="#yt_trailer".+?data-call="(.+?)"', html)[1]
            qualities = ['240p', '480p', '720p', '1080p']
            permitted = False
            code = None
            while not code and len(qualities):
                q = qualities.pop()
                if not permitted:
                    permitted = q == quality
                if permitted:
                    code = re.search(q + r'.+?"(/api\?call=.+?)"><i class="i-dl">', html)
            if not code:
                print('%s no link was available'%url)
                return (id, '')
            code = code[1]
            # watch = 'https://w.egybest.org'+re.search(r'<iframe.+?src="(.+?)"', html)[1]
            name = re.search(r"([a-z0-9]+)={'url':[^,]+?\+([a-z0-9]{3,}),", html, re.I)
            data = re.search(r"([a-z0-9]{3,})\['forEach'].+?%s\+=([a-z0-9]+?)\[.+?]"%name[2], html, re.I)
            for val in re.finditer(r"%s\['data'\]\['([^']+?)'\]='([^']+?)'"%name[1], html): pass
            a, b = data[1], data[2]

            data = { a: {}, b: {} }
            for arrName in data.keys():
                for p in re.finditer(r"%s\[([^\]]+?)]='(.+?)'[,;]"%arrName, html, re.I):
                    k = p[1][1:-1] if p[1][0] == "'" else int(evaluate(p[1]))
                    data[arrName][k] = p[2]

            l = data[a]
            data[a] = []
            for i in range(len(l)):
                data[a].append(l[i])

            vidstream = sess.get('https://w.egybest.org'+code, allow_redirects=False).headers['location']
            if vidstream[:2] == '/?':
                verification = 'https://w.egybest.org/api?call='+(''.join([data[b][v] for v in data[a] if v in data[b]]))
                click = 'https://w.egybest.org/'+base64.b64decode(re.search(r"=\['([^']+?)'\]", html)[1] + '===').decode('utf8')
                res = sess.get(click).text
                args = re.search(r'\("(.+?)",(\d+),"(.+?)",(\d+),(\d+),(\d+)\)', res)
                cipher, _, key, offset, base, _ = args.groups()
                base = int(base)
                offset = int(offset)
                cipher = cipher.split(key[base])
                cipher = [c.translate(c.maketrans(key, ''.join([str(i) for i in range(len(key))]))) for c in cipher]
                cipher = [chr(int(c, base) - offset) for c in cipher if c]
                # print(sess.cookies)
                # c_name, c_value = tuple(re.search(r'cookie="(.+?);', ''.join(cipher))[1].split('='))
                # sess.cookies.set(c_name, c_value)
                time.sleep(1)
                sess.post(verification, data={val[1]: val[2]})
                vidstream = sess.get('https://w.egybest.org'+code, allow_redirects=False).headers['location']
                # sess.cookies.pop(c_name)
            else:
                # print('vidstream link grabbed using cookies')
                pass
            # vidstream = 'https://w.egybest.org/vs-mirror/vidstream.to/f/YvD0EpU8nU'
            vidstream = 'https://w.egybest.org/vs-mirror/'+re.search(r'vidstream.+?\/f\/.+?\/', vidstream)[0]
            # print(vidstream)
            html = sess.get(vidstream).text
            # print(html)
            # html = open('html.txt', encoding='utf-8').read()

            if not re.search('<a href="(h.+?)" class="bigbutton"', html):
                a0c = literal_eval(re.search(r'var \w=(\[.+?\]);', html)[1])
                a0d_offset = re.search(r'return a0d=function\(d,e\)\{d=d-([^;]+?);', html)[1]
                def a0d(a):
                    a=int(a, 16)-int(a0d_offset, 16)
                    return a0c[a]

                parameters = re.search(r"function\(a,b\)\{var .=a0d.+?;while\(!!\[\]\)\{try\{var .=([^;]+?);[^,]+?\(a0c,([^)].+?)\)", html)
                limit = int(parameters[2], 16)
                c = 0
                while True:
                    step = parameters[1]
                    for match in re.finditer(r'parseInt\(.\(([^)]+?)\)\)', parameters[0]):
                        step = step.replace(match[0], str(int((re.search(r'\d+', a0d(match[1])) or [0])[0])))
                    c = evaluate(step)
                    if c == limit:
                        break

                    a0c.append(a0c.pop(0))

                token = re.search(r",[^,]+?=\[a0[a-zA-Z]\((.+?)\)", html)
                if token:
                    token = a0d(token[1])
                else:
                    token = re.search(r",[^,]+?=\['([^']+?)'\]", html)[1]

                arrNames = re.search(r'\+=(_.+?)\[(.+?)\[.+?\]\]\|\|''', html)

                values = {}
                arrName = arrNames[1]
                for match in re.finditer(r"%s\['([^'()]+?)'\]='([^']+?)'"%arrName, html):
                    values[match[1]] = match[2]
                for match in re.finditer(r"%s\['([^'()]+?)'\]=a0.\(([^)]+?)\)"%arrName, html):
                    values[match[1]] = a0d(match[2])
                for match in re.finditer(r"%s\[a0.\(([^)]+?)\)\]='([^']+?)'"%arrName, html):
                    values[a0d(match[1])] = match[2]
                for match in re.finditer(r"%s\[a0.\(([^)]+?)\)\]=a0.\(([^)]+?)\)"%arrName, html):
                    values[a0d(match[1])] = a0d(match[2])

                keys = {}
                arrName = arrNames[2]
                for match in re.finditer(r"%s\[([^=()]+?)\]='([^'].+?)'"%arrName, html):
                    keys[int(match[1], 16)] = match[2]
                for match in re.finditer(r"%s\[([^=()]+?)\]=a0.\(([^)].+?)\)"%arrName, html):
                    keys[int(match[1], 16)] = a0d(match[2])

                # print(token)
                sess.get('https://w.egybest.org/'+base64.b64decode(token + '===').decode('utf8'))
                verification = ''.join([values[keys[i]] for i in range(len(keys)) if keys[i] in values])
                # time.sleep(.2)
                sess.post('https://w.egybest.org/tvc.php?verify='+verification, data={re.search(r"'([^']+?)':'ok'", html)[1]: 'ok'})
                html = sess.get(vidstream).text
            else:
                # print('download link grabbed using cookies')
                pass
            if not os.path.exists('cookies'): os.mkdir('cookies')
            pickle.dump(sess.cookies, open(cookiesPath, 'wb'))
            print('%s grabbed'%url)
            return (id, re.search('<a href="(h.+?)" class="bigbutton"', html)[1])
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            # traceback.print_exc()
            
            return self.__grab_item(url, quality, last_session, id)

# Test series

check_updates(sys.argv[0])

parser = argparse.ArgumentParser(prog='EgyGrab')
parser.add_argument('url', help='an Egybest url of a movie, episode, season, or series. should start with https://w.egybest.org/')
parser.add_argument('-q', '--quality', type=str, default='1080p', help='the desired quality')
parser.add_argument('-C', '--no-cookies', dest='cookies', action='store_false', help='creates a new session for each grabbing request')

args = parser.parse_args()

# args.url = 'https://w.egybest.org/series/new-amsterdam/?ref=home-tv'
# args.quality = '1080p'

grabber = EgyGrab(args.url)

print('Your URL links to "%s"'%grabber.type.name)

filename = re.search(r'.+?\/%s\/(.+?)(\/|$)'%grabber.type.value, args.url)[1] + '.txt'

open(filename, 'w').write('\n'.join(grabber.grab(args.quality)))

print('Links were saved in "%s"'%filename)
