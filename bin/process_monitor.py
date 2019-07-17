#!/usr/bin/env python
#
#  Copyright (c) 2018, TierIV, Inc.
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of Autoware nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import roslib
roslib.load_manifest('diagnostic_updater')
import rospy
import time
import subprocess
import diagnostic_updater
from diagnostic_msgs.msg import DiagnosticStatus
from enum import IntEnum
import socket
import functools

class MonitorType(IntEnum):
    CPU = 0
    MEM = 1
    TASK = 2

class Task():
    def set_val(self, keyval):
        if len(keyval) != 2:
            return
        val = keyval[0].strip()
        key = keyval[1].strip()
        if key.find('total') > -1:      self._total = val
        elif key.find('running') > -1:  self._run = val
        elif key.find('sleeping') > -1: self._sleep = val
        elif key.find('stopped') > -1:  self._stop = val
        elif key.find('zombie') > -1:   self._zombie = val

class Process():    
    def __init__(self):
        val = ''
        self._id = val
        self._usr = val
        self._pr = val 
        self._ni = val
        self._vi = val
        self._res = val
        self._shr = val
        self._stat = val
        self._cpu = val
        self._mem = val
        self._time = val
        self._name = val
    
    def set_val(self, idx, val):
        if idx == 0:    self._id = val
        elif idx == 1:  self._usr = val
        elif idx == 2:  self._pr = val 
        elif idx == 3:  self._ni = val
        elif idx == 4:  self._vi = val
        elif idx == 5:  self._res = val
        elif idx == 6:  self._shr = val
        elif idx == 7:  self._stat = val
        elif idx == 8:  self._cpu = val
        elif idx == 9:  self._mem = val
        elif idx == 10: self._time = val
        elif idx == 11: self._name = val

class ProcessMonitor():
    def __init__(self, hostname):
        self._proc_num = rospy.get_param('~monitored_process_num', 5)
        self._proc = [[Process() for i in range(self._proc_num * 2)] for j in range(2)]
        self._check_proc_func = []
        self._task = Task()
        self._retcode = [0 for i in range(3)]
        self._updater = diagnostic_updater.Updater()
        self._updater.setHardwareID(hostname)
        self._updater.add('Task Status', self.check_task)
        for index in range(self._proc_num):
            m = MonitorType.CPU
            f = functools.partial(self.check_proc, m, index)
            self._check_proc_func.append(f)
            self._updater.add('High-load Proc[%d]' % (index + 1), self._check_proc_func[index])
        for index in range(self._proc_num):
            m = MonitorType.MEM
            f = functools.partial(self.check_proc, m, index)
            self._check_proc_func.append(f)
            self._updater.add('High-mem Proc[%d]' % (index + 1), self._check_proc_func[index + self._proc_num])

    def update(self):
        self.update_task()
        for index in range(2):
            self.update_proc(index)
        self._updater.update()


    def check_task(self, stat):
        if self._retcode[MonitorType.TASK] != 0:
            stat.summary(DiagnosticStatus.ERROR, 'top-command Error')
        else:
            stat.summary(DiagnosticStatus.OK, 'OK')
        task = self._task
        stat.add('Total Tasks', task._total)
        stat.add('Running Tasks', task._run)
        stat.add('Sleeping Tasks', task._sleep)
        stat.add('Stopped Tasks', task._stop)
        stat.add('Zombie Tasks', task._zombie)
        return stat

    def check_proc(self, monitor_type, index, stat):
        if self._retcode[monitor_type] != 0:
            stat.summary(DiagnosticStatus.ERROR, 'top-command Error')
        else:
            stat.summary(DiagnosticStatus.OK, 'OK')
        proc = self._proc[monitor_type][index]
        stat.add('Process Name', proc._name)
        stat.add('Process ID', proc._id)
        stat.add('Process User', proc._usr)
        stat.add('Process Priority', proc._pr)
        stat.add('Process Nice Value', proc._ni)
        stat.add('Process Virtual Image', proc._vi)
        stat.add('Process Resident Size', proc._res)
        stat.add('Process Shared Mem Size', proc._shr)
        stat.add('Process Status', proc._stat)
        stat.add('Process %CPU', proc._cpu)
        stat.add('Process %MEM', proc._mem)
        stat.add('Process Time', proc._time)
        return stat

    def update_task(self):
        p = subprocess.Popen('top -b -c -n 1 -d 0.01|sed -n "2 p"',
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE, shell = True)
        stdout, stderr = p.communicate()
        self._retcode[MonitorType.TASK] = p.returncode
        task_context = stdout.strip().split(':')
        if len(task_context) < 2: return
        for task_index, task_ln in enumerate(task_context[1].split(',')):
            self._task.set_val(task_ln.strip().split())

    def update_proc(self, monitor_type):
        option = ''
        if monitor_type == MonitorType.CPU:   option = '-o %CPU '
        elif monitor_type == MonitorType.MEM: option = '-o %MEM '
        cmd = 'top -b -c %s-n 1 -d 0.01' % option
        cmd += '|sed "/^\%Cpu/d"|sed "1,6d"'
        cmd += '|sed -n "1,%s p"' % self._proc_num
        p = subprocess.Popen(cmd, stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE, shell = True)
        stdout, stderr = p.communicate()
        self._retcode[monitor_type] = p.returncode
        for index, ln in enumerate(stdout.split('\n')):
            vals = ln.strip().split()
            if len(vals) < 12: continue
            for i in range(12):
                self._proc[monitor_type][index].set_val(i, vals[i])
        

if __name__=='__main__':
    hostname = socket.gethostname()
    hostname = hostname.replace('-', '_')
    try:
        rospy.init_node("process_monitor_%s" % hostname)
    except rospy.exceptions.ROSInitException:
        print >> sys.stderr, 'Process monitor is unable to initialize node. Master may not be running.'
        sys.exit(0)
    pm = ProcessMonitor(hostname)

    r = rospy.Rate(0.5)
    while not rospy.is_shutdown():

        pm.update()
        r.sleep()

