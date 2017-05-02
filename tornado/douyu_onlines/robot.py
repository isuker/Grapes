# coding=utf-8

import time
import Queue
import urllib
import threading
import sys
sys.path.append('..')
from douyu_utils.chat.auth import *
from douyu_utils.douyu_utils import *
from servers import servers

class Robot(threading.Thread):
    def __init__(self, rid):
        super(Robot, self).__init__()
        self.rid = rid
        self.stop_flag = False
        self.auth = None
        self.pause = False
        self.freq = 30 # 最大发言间隔，最小值为20
        self.msg = []
        self.cookie = None
        self.nickname = None
        self.send_count = 0
        self.max_send = random.randint(20,40)
        self.isTest = False

    def get_cookie_from_server(self):

        search_url = 'http://b16n023084.51mypc.cn:5005/get_cookie/%s' % self.rid
        search_url = 'http://192.168.3.56:5002/cookie/%s' % self.rid
        search_url = 'http://192.168.3.56:5002/cookie?rid=%d&type=0' % self.rid
        #search_url = 'http://192.168.3.160:5000/cookie'

        cookie = None
        while not cookie and not self.stop_flag:
            try:
                r = requests.get(search_url)
            except Exception, e:
                print e, search_url
                time.sleep(30+random.random())
                continue

            response = r.text
            try:
                cookie = json.loads(response)
            except Exception, e:
                print e, search_url
                print 'response:', response
                time.sleep(120+random.random())
                continue
        print 'cookie:', urllib.unquote(response.encode('utf-8'))
        self.nickname = urllib.unquote(cookie['acf_nickname'].encode('utf-8'))
        return cookie

    def get_barrage_from_server(self):
        search_url = 'http://b16n023084.51mypc.cn:5005/get_barrage?rid=%d' % self.rid
        search_url = 'http://192.168.3.56:5002/barrage/%d/%s' % (self.rid, self.cookie['acf_uid'])
        #search_url = 'http://192.168.3.160:5000/barrage/%d/%s' % (self.rid, self.cookie['acf_uid'])
        #print search_url
        try:
            r = requests.get(search_url)
        except Exception, e:
            print e, search_url
            return None

        response = r.text
        # print response
        data = None
        try:
            data = json.loads(response)
        except Exception, e:
            print e, search_url
            print 'response:', response
            #raise e
        #if data.get('if_send', 1) == 0:
        #    print search_url
        #    print data.get('msg', None)
        return data

    def error_hdlr(self, rid, msg):
        pass
        # if msg.body['code'] == '59':
        #     self.cookie = self.get_cookie_from_server()

    def send_msg(self, room):
        while not self.stop_flag:
            time.sleep(random.uniform(20, self.freq))
            if not self.pause:
                if len(self.msg) > 0:
                    room.send_msg(self.msg[0])
                    self.send_count += 1
                    del self.msg[0]
                    if self.isTest:
                        self.close()
                else:
                    barrage = self.get_barrage_from_server()
                    if barrage and barrage['if_send'] and len(barrage['msg'])>0:
                        msg = barrage['msg']
                    else:
                        barrage = None
                    if barrage:
                        try:
                            room.send_msg(msg)
                        except Exception, e:
                            self.send_count = self.max_send+1
                            break
                        #print self.nickname, ':', msg
                        self.send_count += 1


    def run(self):
        while not self.stop_flag:
            #servers = douyu_get_danmu_auth_server(self.rid)
            if len(servers) == 0:
                print "servers length:", len(servers)
                continue
            hasExcept = True
            while hasExcept and  not self.stop_flag:
                try:
                    hasExcept = False
                    server = servers[random.randint(0, len(servers ) -1)]
                    danmu_ip = server['ip']
                    danmu_port = int(server['port'])
                    self.cookie = self.get_cookie_from_server()
                    self.auth = ChatAuth(self.rid, danmu_ip, danmu_port, self.cookie)
                    self.auth.on('error', self.error_hdlr)
                    self.auth.knock(self.send_msg)
                except Exception, e:
                    print "failed room %d server %s:%d" %(self.rid, danmu_ip, danmu_port)
                    print e.message
                    hasExcept = True
                    self.auth.close()
                    time.sleep(120+random.random())

    def close(self):
        self.stop_flag = True;
        if self.auth:
            self.auth.close()
        print 'robot stop'

    def setfreq(self, freq):
        if freq < 20:
            freq = 20
        self.freq = freq

    def setpause(self, status):
        self.pause = status

    def sendmsg(self, msg):
        if msg and len(msg):
            self.msg.append(msg)