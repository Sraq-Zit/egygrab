from ast import literal_eval
import enum
from numexpr import evaluate
from enum import Enum

import threading
import traceback
import requests
import base64
import pickle
import time
import sys
import re
import os



class TYPES(Enum): 
    episode = 'episode'
    masrahiya = 'masrahiya'
    season = 'season'
    series = 'series'
    movie = 'movie'


class EgyGrab():
    def __init__(self, url):
        self.dl_url = self.url = url
        self.type = None
        for t in TYPES:
            if '/%s/'%t.name in url:
                self.type = TYPES[t.name]
                break
        if self.type is None: raise ValueError('There is nothing to download :(')
        self.threads = []
        self.results = []
    
    def grab(self, quality='1080p'):
        if self.type == TYPES.episode or self.type == TYPES.masrahiya or self.type == TYPES.movie:
            return [self.__grab_item(self.url, quality)[1]]

        
        urls = [self.url]
        if self.type == TYPES.series:
            html = requests.get(self.url).text
            urls = reversed([match[1] for match in re.finditer(r'<a href="(https:\/\/egybest.org\/season\/.+?)"', html)])

        self.threads = []
        self.results = []
        for url in urls:
            season_results = []
            i = 0
            html = requests.get(url).text
            for match in re.finditer(r'<a href="(https:\/\/egybest.org\/episode\/.+?)"', html):
                t = threading.Thread(target=lambda: season_results.append(self.__grab_item(match[1], quality, True, i)))
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
            # call = 'https://egybest.org/api?call='+re.search(r'rel="#yt_trailer".+?data-call="(.+?)"', html)[1]
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
                print('%s not link was available'%url)
                return (id, '')
            code = code[1]
            # watch = 'https://egybest.org'+re.search(r'<iframe.+?src="(.+?)"', html)[1]
            name = re.search(r"([a-z0-9]+)={'url':[^,]+?\+([a-z0-9]{3,}),", html, re.I)
            data = re.search(r"([a-z0-9]{3,})\['forEach'].+?%s\+=([a-z0-9]+?)\[.+?]"%name[2], html, re.I)
            for val in re.finditer(r"%s\['data'\]\['([^']+?)'\]='([^']+?)'"%name[1], html): pass
            a, b = data[1], data[2]

            data = { a: {}, b: {} }
            for arrName in data.keys():
                for p in re.finditer(r"%s\[([^\]]+?)]='(.+?)'[,;]"%arrName, html):
                    data[arrName][eval(p[1])] = p[2]

            l = data[a]
            data[a] = []
            for i in range(len(l)):
                data[a].append(l[i])

            vidstream = sess.get('https://egybest.org'+code, allow_redirects=False).headers['location']
            if vidstream[0] == '/':
                verification = 'https://egybest.org/api?call='+(''.join([data[b][v] for v in data[a] if v in data[b]]))
                click = 'https://egybest.org/'+base64.b64decode(re.search(r"=\['([^']+?)'\]", html)[1] + '===').decode('utf8')
                res = sess.get(click).text
                args = re.search(r'\("(.+?)",(\d+),"(.+?)",(\d+),(\d+),(\d+)\)', res)
                cipher, _, key, offset, base, _ = args.groups()
                base = int(base)
                offset = int(offset)
                cipher = cipher.split(key[base])
                cipher = [c.translate(c.maketrans(key, ''.join([str(i) for i in range(len(key))]))) for c in cipher]
                cipher = [chr(int(c, base) - offset) for c in cipher if c]
                c_name, c_value = tuple(re.search(r'cookie="(.+?);', ''.join(cipher))[1].split('='))
                sess.cookies.set(c_name, c_value)
                time.sleep(.5)
                sess.post(verification, data={val[1]: val[2]})
                vidstream = sess.get('https://egybest.org'+code, allow_redirects=False).headers['location']
                sess.cookies.pop(c_name)
            else:
                # print('vidstream link grabbed using cookies')
                pass
            # vidstream = 'https://egybest.org/vs-mirror/vidstream.to/f/YvD0EpU8nU'
            vidstream = 'https://egybest.org/vs-mirror/'+re.search(r'vidstream.+?\/f\/.+?\/', vidstream)[0]
            html = sess.get(vidstream).text
            # print(html)
            # html = open('html.txt', encoding='utf-8').read()

            if not re.search('<a href="(h.+?)" class="bigbutton"', html):
                a0c = literal_eval(re.search(r'var a0c=(\[.+?\]);var', html)[1])
                a0d_offset = re.search(r'var a0d=function\(a,b\)\{a=a-([^;]+?);', html)[1]
                def a0d(a):
                    a=int(a, 16)-int(a0d_offset, 16)
                    return a0c[a]

                parameters = re.search(r"function\(a,b\)\{var .=a0d;while\(!!\[\]\)\{try\{var .=([^;]+?);[^,]+?\(a0c,([^)].+?)\)", html)
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
                sess.get('https://egybest.org/'+base64.b64decode(token + '===').decode('utf8'))
                verification = ''.join([values[keys[i]] for i in range(len(keys)) if keys[i] in values])
                # time.sleep(.2)
                sess.post('https://egybest.org/tvc.php?verify='+verification, data={re.search(r"'([^']+?)':'ok'", html)[1]: 'ok'})
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

URL = sys.argv[1]
QUALITY = sys.argv[2] if len(sys.argv) > 2 else '1080p'
grabber = EgyGrab(URL)

print('Your URL links to "%s"'%grabber.type.name)

filename = re.search(r'.+?\/%s\/(.+?)(\/|$)'%grabber.type.name, URL)[1] + '.txt'

open(filename, 'w').write('\n'.join(grabber.grab(QUALITY)))

print('Links were saved in "%s"'%filename)
