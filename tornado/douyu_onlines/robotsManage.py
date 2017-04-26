# coding=utf-8

import random
import time
import json
import threading
import requests
import Queue
import sys
sys.path.append('..')
from robot import Robot

class MonitorRoom(threading.Thread):
    def __init__(self, rid, roominfo, rm):
        super(MonitorRoom, self).__init__()
        self.isRunning = True
        self.rid = rid
        self.roominfo = roominfo
        self.rm = rm
        self.ss = None

    def close(self):
        self.isRunning = False

    def run(self):
        while self.isRunning:
            roomapi_url = 'http://open.douyucdn.cn/api/RoomApi/room/%d' % self.rid
            try:
                r = requests.get(roomapi_url)
            except Exception, e:
                print e, roomapi_url
            if r:
                response = r.text
            # print response
            try:
                info = json.loads(response)
            except Exception, e:
                print e, roomapi_url
                print 'response:', response
            if info['error'] == 0:
                data = info['data']
                room_status = data['room_status']
                if self.ss != room_status:
                    self.ss = room_status
                    if room_status == '2': # 关播
                        self.roominfo['ss'] = '0'
                        threads = self.roominfo['threads']
                        while len(threads) > 0:
                            thread = threads[0]
                            threads.remove(thread)
                            thread.close()
                        logout_url = 'http://192.168.3.56:5002/stop/%d' % self.rid
                        #logout_url = 'http://192.168.3.160:5000/stop/%d' % rid
                        try:
                            requests.get(logout_url)
                        except Exception, e:
                            print e
                        print logout_url
                    else: # 开播
                        self.roominfo['ss'] = '1'
                        while self.isRunning:
                            login_url = 'http://192.168.3.56:5002/login/%d' % self.rid
                            #login_url = 'http://192.168.3.160:5000/login/%d' % rid
                            try:
                                r = requests.get(login_url)
                            except Exception, e:
                                print e
                            print login_url
                            response = r.text
                            data = {}
                            try:
                                data = json.loads(response)
                            except Exception, e:
                                print e
                            status = data.get('status', 4)
                            if status != 4:
                                break
                        num = self.roominfo.get('num', 0)
                        self.rm.setnum(self.rid, num)
                    print self.rid, ':', self.roominfo['ss']
            time.sleep(10)

class RobotsManage(threading.Thread):
    def __init__(self):
        super(RobotsManage, self).__init__()
        self.roomsinfo = {}  # 1876728, 592766
        self.cmdQueue = Queue.Queue()
        self.isRunning = False
        self.mutex = threading.Lock()

    def run(self):
        self.isRunning = True
        while self.isRunning:
            if not self.cmdQueue.empty():
                cmd = self.cmdQueue.get()
                rid = cmd['rid']
                roominfo = self.roomsinfo.get(str(rid))
                if not roominfo:
                    if cmd['type'] == 'add':
                        roominfo = {'threads': []}
                        cr = MonitorRoom(rid, roominfo, self)
                        cr.start()
                        roominfo['cr'] = cr
                        self.roomsinfo[str(rid)] = roominfo
                        continue
                else:
                    threads = roominfo['threads']
                    if cmd['type'] == 'pause':
                        roominfo['pause'] = cmd['status']
                        for thread in threads:
                            thread.setpause(cmd['status'])
                    elif cmd['type'] == 'send':
                        msg = cmd['msg']
                        i = 0
                        for thread in threads:
                            if i < cmd['repeat']:
                                thread.sendmsg(msg)
                                i += 1
                            else:
                                break
                    elif cmd['type'] == 'freq':
                        freq = cmd['freq']
                        roominfo['freq'] = freq
                        for thread in threads:
                            thread.setfreq(freq)
                    elif cmd['type'] == 'num':
                        num = cmd['num']
                        roominfo['num'] = num
                        if roominfo.get('ss', '0') == '1': # 开播
                            interval = roominfo.get('interval', 10)
                            while len(threads) < num:
                                thread = Robot(rid)
                                pause = roominfo.get('pause', False)
                                thread.setpause(pause)
                                freq = roominfo.get('freq', 30)
                                thread.setfreq(freq)
                                thread.start()
                                threads.append(thread)
                                time.sleep(interval+random.random())
                        while len(threads) > num:
                            thread = threads[0]
                            threads.remove(thread)
                            thread.close()
                    elif cmd['type'] == 'del':
                        for thread in threads:
                            thread.close()
                            time.sleep(random.random())
                        threads = []
                        cr = roominfo['cr']
                        cr.close()
                        self.roomsinfo.pop(str(rid))
                        logout_url = 'http://192.168.3.56:5002/stop/%d' % rid
                        #logout_url = 'http://192.168.3.160:5000/stop/%d' % rid
                        try:
                            requests.get(logout_url)
                        except Exception, e:
                            print e
                        print logout_url
                    elif cmd['type'] == 'interval':
                        interval = cmd['interval']
                        roominfo['interval'] = interval
            else:
                time.sleep(1)
                for key in self.roomsinfo:
                    rid = int(key)
                    ri = self.roomsinfo[key]
                    ts = ri['threads']
                    for t in ts:
                        if t.send_count > t.max_send:
                            t.close()
                            ts.remove(t)
                            t = Robot(rid)
                            pause = ri.get('pause', False)
                            t.setpause(pause)
                            freq = ri.get('freq', 30)
                            t.setfreq(freq)
                            t.start()
                            ts.append(t)
                            time.sleep(random.random())

    def setpause(self, rid, status):  # True=pause; False=play
        cmd = {}
        cmd['type'] = 'pause'
        cmd['rid'] = rid
        cmd['status'] = status
        self.cmdQueue.put(cmd)

    def sendmsg(self, rid, msg, repeat):
        if repeat < 0:
            roominfo = self.roomsinfo[str(rid)]
            if roominfo:
                repeat = len(roominfo['threads'])
        cmd = {}
        cmd['type'] = 'send'
        cmd['rid'] = rid
        cmd['msg'] = msg
        cmd['repeat'] = repeat
        self.cmdQueue.put(cmd)

    def setfreq(self, rid, freq):
        if freq < 20:
            freq = 20
        cmd = {}
        cmd['type'] = 'freq'
        cmd['rid'] = rid
        cmd['freq'] = freq
        self.cmdQueue.put(cmd)

    def setnum(self, rid, num):
        if num < 0:
            num = 0
        cmd = {}
        cmd['type'] = 'num'
        cmd['rid'] = rid
        cmd['num'] = num
        self.cmdQueue.put(cmd)

    def addroom(self, rid):
        cmd = {}
        cmd['type'] = 'add'
        cmd['rid'] = rid
        self.cmdQueue.put(cmd)

    def delroom(self, rid):
        cmd = {}
        cmd['type'] = 'del'
        cmd['rid'] = rid
        self.cmdQueue.put(cmd)

    def setinterval(self, rid, interval):
        if interval < 0:
            interval = 0
        cmd = {}
        cmd['type'] = 'interval'
        cmd['rid'] = rid
        cmd['interval'] = interval
        self.cmdQueue.put(cmd)

    def exit(self):
        self.isRunning = False

    def roomsinfo(self):
        print self.roomsinfo
