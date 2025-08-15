# Imports from the python standard library:
import time

# Third party imports, installable via pip:
import serial

class Controller:
    '''
    Basic device adaptor for KDS Legato 110, Single Syringe, Programmable
    Touch Screen, Infusion/Withdrawal Pump. Many more commands are available
    and have not been implemented.
    '''
    def __init__(self,
                 which_port,
                 name='Legato110',
                 verbose=True,
                 very_verbose=False):
        self.name = name
        self.verbose = verbose
        self.very_verbose = very_verbose
        # open serial port:
        if self.verbose: print("%s: opening..."%name, end='')
        try:
            self.port = serial.Serial(
                port=which_port, baudrate=115200, timeout=1)
        except serial.serialutil.SerialException:
            raise IOError('No connection to %s on port %s'%(name, which_port))
        if self.verbose: print(" done.")
        # how to convert the 'prompt' returned by the device to a message:
        self.prompt2msg = {':' : 'The pump is idle',
                           '>' : 'The pump is infusing',
                           '<' : 'The pump is withdrawing',
                           '*' : 'The pump stalled',
                           'T*': 'The target was reached'}
        # how to convert the 'unit' returned by the device to a pl/s: 
        self.unit2plps = {
            'ml/hr' :1e9/3600,'ul/hr':1e6/3600,'nl/hr':1e3/3600,'pl/hr':1/3600,
            'ml/min':1e9/60, 'ul/min':1e6/60, 'nl/min':1e3/60, 'pl/min':1/60,
            'ml/sec':1e9,    'ul/sec':1e6,    'nl/sec':1e3,    'pl/sec':1,
            }
        # check communications protocol for '_send' method to work:
        self._running = False
        assert self._get_echo() == 'OFF'
        assert self._get_poll() == 'OFF'
        assert self._get_address() == '0'
        # check device type:
        self._get_ver()
        assert self._version[:10] == 'Legato 110', (
            "%s: unexpected device (%s)"%(self.name, self._version[:10]))
        self._get_version()
        # configure:
        self._set_footswitch_mode('fall') # -> 5V TTL fall will 'run' program!
        self._set_force(50) # safe for glass syringes
        # get status:
        self._get_status()
        self._estimate_run_time()
        self.get_syringe_type()
        self.get_flow_rate_limits()
        self.get_flow_rates()
        self.get_target_volume()
        self.get_run_direction()

    def _read_prompt(self): # special function to read and parse the 'prompt'
        prompt = self.port.read().decode('ascii').rstrip()
        if prompt == 'T': # then read trailing '*' (special case)
            assert self.port.read().decode('ascii') == '*'
            prompt = 'T*' # correct prompt
        if prompt in self.prompt2msg.keys():
            self.prompt_msg = self.prompt2msg[prompt]
            if self.very_verbose:
                print("%s: prompt = %s (%s)"%(
                    self.name, prompt, self.prompt_msg))
        else:
            r = self.port.readline().decode('ascii').strip()
            raise Exception(
                "%s: unexpected prompt = %s (%s)"%(self.name, prompt, r))
        return prompt

    def _send(self, cmd, response_lines):
        cmd = bytes(cmd + '\r', encoding='ascii')
        if self.very_verbose:
            print("%s: sending cmd = %s"%(self.name, cmd))
        self.port.write(cmd)
        self.port.readline() # ignore empty linefeed
        # get responses:
        responses = []
        for i in range(response_lines):
            response = self.port.readline().decode('ascii').strip()
            responses.append(response)
            if self.very_verbose:
                print("%s: response (%i) = %s"%(self.name, i, response))
        # get prompt:
        prompt = self._read_prompt()
        if self.port.in_waiting != 0:
            if self._running: # race condition where 'T*' is returned from 'run'
                self.port.readline() # ignore empty linefeed
                assert self._read_prompt() == 'T*'
                self._running = False
            else:
                r = self.port.readline().decode('ascii').strip()
                raise Exception("%s: unexpected response = %s"%(self.name, r))
        return responses

    def _get_echo(self):
        if self.very_verbose:
            print("%s: getting echo"%self.name)
        self._echo = self._send('echo', response_lines=1)[0]
        if self.very_verbose:
            print("%s:  = %s"%(self.name, self._echo))
        return self._echo

    def _get_poll(self):
        if self.very_verbose:
            print("%s: getting poll"%self.name)
        self._poll = self._send('poll', response_lines=1)[0]
        if self.very_verbose:
            print("%s:  = %s"%(self.name, self._poll))
        return self._poll

    def _get_address(self):
        if self.very_verbose:
            print("%s: getting address"%self.name)
        self._address = self._send('addr', response_lines=1)[0].split()[3]
        if self.very_verbose:
            print("%s:  = %s"%(self.name, self._address))
        return self._address

    def _get_ver(self):
        if self.very_verbose:
            print("%s: getting ver"%self.name)
        self._version = self._send('ver', response_lines=1)[0]
        if self.very_verbose:
            print("%s:  = %s"%(self.name, self._version))
        return self._version

    def _get_version(self):
        if self.very_verbose:
            print("%s: getting version"%self.name)
        self._version_long = self._send('version', response_lines=3)
        if self.very_verbose:
            for i in range(len(self._version_long)):
                print("%s:  -> %s"%(self.name, self._version_long[i]))
        return self._version_long

    def _get_footswitch_mode(self):
        if self.very_verbose:
            print("%s: getting footswitch mode (%%)"%self.name)
        r = self._send('ftswitch', response_lines=1)[0]
        # it seems like 'Active low' is needed to run with 0V on the trigger
        r2mode = {'Momentary':'mom', 'Active high':'rise', 'Active low':'fall'}
        self._footswitch_mode = r2mode[r]
        if self.very_verbose:
            print("%s:  = %s"%(self.name, self._footswitch_mode))
        return self._footswitch_mode

    def _set_footswitch_mode(self, mode):
        if self.very_verbose:
            print("%s: setting footswitch_mode (%%) = %s"%(self.name, mode))
        assert mode in ('mom', 'rise', 'fall'), (
            "%s: unexpected mode (%s)"%(self.name, mode))
        self._send('ftswitch ' + str(mode), response_lines=0)
        assert self._get_footswitch_mode() == mode, (
                "%s: unexpected footswitch_mode"%self.name)
        if self.very_verbose:
            print("%s: -> done setting footswitch_mode."%self.name)
        return None

    def _get_force(self):
        if self.very_verbose:
            print("%s: getting force (%%)"%self.name)
        force = self._send('force', response_lines=1)[0]
        self.force_pct = int(force.split('%')[0])
        if self.very_verbose:
            print("%s:  = %s"%(self.name, self.force_pct))
        return self.force_pct

    def _set_force(self, force_pct):
        if self.very_verbose:
            print("%s: setting force (%%) = %i"%(self.name, force_pct))
        assert type(force_pct) is int, (
            "%s: unexpected type for force"%self.name)
        assert 1 <= force_pct <= 100, (
            "%s: force_pct out of range"%self.name)
        self._send('force ' + str(force_pct), response_lines=0)
        assert self._get_force() == force_pct, (
                "%s: unexpected force_pct"%self.name)
        if self.very_verbose:
            print("%s: -> done setting force."%self.name)
        return None

    def _get_status(self):
        if self.very_verbose:
            print("%s: getting status"%self.name)
        status = self._send('status', response_lines=1)[0].split()
        if self.very_verbose:
            print("%s: current rate (fL/s)   = %s"%(self.name, status[0]))
            print("%s: infuse time    (ms)   = %s"%(self.name, status[1]))
            print("%s: infused volume (fL)   = %s"%(self.name, status[2]))
            print("%s: motor direction       = %s"%(self.name, status[3][0]))
            print("%s: limit switch status   = %s"%(self.name, status[3][1]))
            print("%s: stall status          = %s"%(self.name, status[3][2]))
            print("%s: trigger input state   = %s"%(self.name, status[3][3]))
            print("%s: direction port state  = %s"%(self.name, status[3][4]))
            print("%s: target reached status = %s"%(self.name, status[3][5]))
        return status

    def _estimate_run_time(self):
        if self.very_verbose:
            print("%s: estimating run time"%self.name)
        verbose = self.verbose
        self.verbose = False
        assert self.get_target_volume() != 'Target volume not set', (
            "%s: please set a target volume"%self.name)
        self.get_flow_rates()
        assert self.wrate_plps != 0, (
            "%s: please set a non zero withdraw rate"%self.name)
        assert self.irate_plps != 0, (
            "%s: please set a non zero infuse rate"%self.name)
        self.wrun_time_s = round(self.tvolume_pl / self.wrate_plps, 6)
        self.irun_time_s = round(self.tvolume_pl / self.irate_plps, 6)
        self.verbose = verbose
        if self.very_verbose:
            print("%s: withdraw run time = %s (s)"%(
                self.name, self.wrun_time_s))
            print("%s: infuse   run time = %s (s)"%(
                self.name, self.irun_time_s))
        return self.wrun_time_s, self.irun_time_s

    def _finish_running(self):
        assert self._running
        timeout = self.port.timeout
        self.port.timeout = None # block until 'run' is finished!
        self.port.readline() # ignore empty linefeed
        assert self._read_prompt() == 'T*' # target reached
        assert self.port.in_waiting == 0
        self._running = False
        self.port.timeout = timeout # reset timeout
        if self.verbose:
            print('%s:  -> finished running'%self.name)
        return None

    def get_syringe_type(self):
        if self.verbose:
            print("%s: getting syringe type"%self.name)
        self.sy_type = self._send('syrm', response_lines=1)[0]
        if self.verbose:
            print("%s: = %s"%(self.name, self.sy_type))
        return self.sy_type

    def get_flow_rate_limits(self):
        if self.verbose:
            print("%s: getting flow rate limits"%self.name)
        self.wrate_limits = self._send('wrate lim', response_lines=1)[0]
        self.irate_limits = self._send('irate lim', response_lines=1)[0]
        if self.verbose:
            print("%s: withdraw rate limits = %s "%(
                self.name, self.wrate_limits))
            print("%s: infuse rate   limits = %s "%(
                self.name, self.irate_limits))
        # parse limits to min and max numbers with unit:
        self.wrate_min = float(self.wrate_limits.split(' to ')[0].split()[0])
        self.wrate_min_unit =  self.wrate_limits.split(' to ')[0].split()[1]
        self.wrate_max = float(self.wrate_limits.split(' to ')[1].split()[0])
        self.wrate_max_unit =  self.wrate_limits.split(' to ')[1].split()[1]
        self.irate_min = float(self.irate_limits.split(' to ')[0].split()[0])
        self.irate_min_unit =  self.irate_limits.split(' to ')[0].split()[1]
        self.irate_max = float(self.irate_limits.split(' to ')[1].split()[0])
        self.irate_max_unit =  self.irate_limits.split(' to ')[1].split()[1]
        # convert to min and max rates in pl/s:
        self.wrate_min_plps = round(
            self.wrate_min * self.unit2plps[self.wrate_min_unit])
        self.wrate_max_plps = round(
            self.wrate_max * self.unit2plps[self.wrate_max_unit])
        self.irate_min_plps = round(
            self.irate_min * self.unit2plps[self.irate_min_unit])
        self.irate_max_plps = round(
            self.irate_max * self.unit2plps[self.irate_max_unit])
        return self.wrate_limits, self.irate_limits

    def get_flow_rates(self):
        if self.verbose:
            print("%s: getting flow rates"%self.name)
        self.wrate = self._send('wrate', response_lines=1)[0]
        self.irate = self._send('irate', response_lines=1)[0]
        if self.verbose:
            print("%s: withdraw rate = %s "%(self.name, self.wrate))
            print("%s: infuse rate   = %s "%(self.name, self.irate))
        # parse rates into number and unit:
        wrate = float(self.wrate.split()[0])
        wrate_unit =  self.wrate.split()[1]
        irate = float(self.irate.split()[0])
        irate_unit =  self.irate.split()[1]
        # convert rates into pl/s:
        self.wrate_plps = round(wrate * self.unit2plps[wrate_unit])
        self.irate_plps = round(irate * self.unit2plps[irate_unit])
        return self.wrate, self.irate

    def set_flow_rate(self, direction, rate, unit):
        if self.verbose:
            print("%s: setting flow rate = %s %s %s"%(
                self.name, direction, rate, unit))
        # check input:
        assert direction in ('withdraw', 'infuse'), (
            "%s: unknown run direction (%s)"%(self.name, direction))
        if rate in ('min', 'max'):
            assert unit is None, (
                "%s: for 'min' or 'max' flow rate, set 'unit=None'"%self.name)
        if rate == 'min' and direction == 'withdraw':
            rate, unit = int(round(self.wrate_min)), self.wrate_min_unit
        if rate == 'max' and direction == 'withdraw':
            rate, unit = int(self.wrate_max), self.wrate_max_unit
        if rate == 'min' and direction == 'infuse':
            rate, unit = int(round(self.irate_min)), self.irate_min_unit
        if rate == 'max' and direction == 'infuse':
            rate, unit = int(self.irate_max), self.irate_max_unit
        assert type(rate) is int, ( # int only to solve floating point problem
            "%s: unexpected type for flow rate (%s)"%(self.name, type(rate)))
        assert rate != 0, ("%s: zero flow rate not allowed"%self.name)
        assert unit in self.unit2plps.keys(), (
            "%s: unexpected unit for flow rate (%s)"%(self.name, unit))
        rate_plps = round(rate * self.unit2plps[unit])
        # check direction and limits:
        if direction == 'withdraw':
            assert rate_plps >= self.wrate_min_plps, (
                "%s: withdraw flow rate (%s %s) too low (min %s %s)"%(
                    self.name, rate, unit, self.wrate_min, self.wrate_min_unit))
            assert rate_plps <= self.wrate_max_plps, (
                "%s: withdraw flow rate (%s %s) too high (max %s %s)"%(
                    self.name, rate, unit, self.wrate_max, self.wrate_max_unit))
            wrate = str(rate) + ' ' + unit
            self._send('wrate ' + wrate, response_lines=0)
            self.get_flow_rates()
            assert self.wrate_plps == rate_plps, (
                "%s: requested flow rate (%s) not set (%s)"%(
                    self.name, rate_plps, self.wrate_plps))
        else:
            assert rate_plps >= self.irate_min_plps, (
                "%s: infuse flow rate (%s %s) too low (min %s %s)"%(
                    self.name, rate, unit, self.irate_min, self.irate_min_unit))
            assert rate_plps <= self.irate_max_plps, (
                "%s: infuse flow rate (%s %s) too high (max %s %s)"%(
                    self.name, rate, unit, self.irate_max, self.irate_min_unit))            
            irate = str(rate) + ' ' + unit
            self._send('irate ' + irate, response_lines=0)
            self.get_flow_rates()
            assert self.irate_plps == rate_plps, (
                "%s: requested flow rate (%s) not set (%s)"%(
                    self.name, rate_plps, self.irate_plps))
        if self.verbose:
            print("%s: -> done setting flow rate."%self.name)
        return None

    def get_target_volume(self):
        if self.verbose:
            print("%s: getting target volume"%self.name)
        self.tvolume = self._send('tvolume', response_lines=1)[0]
        if self.verbose:
            print("%s:  = %s "%(self.name, self.tvolume))
        if self.tvolume == 'Target volume not set':
            self.tvolume_pl = None
        else:
            vol = float(self.tvolume.split()[0])
            unit = self.tvolume.split()[1]
            unit2pl = {'ml':1e9, 'ul':1e6, 'nl':1e3, 'pl':1}
            self.tvolume_pl = vol * unit2pl[unit]
        return self.tvolume

    def set_target_volume(self, volume, unit):
        if self.verbose:
            print("%s: setting target volume = %s %s"%(
                self.name, volume, unit))
        assert type(volume) is int or type(volume) is float, (
            "%s: unexpected type for volume (%s)"%(self.name, type(volume)))
        assert volume != 0, ("%s: zero target volume not allowed"%self.name)
        assert unit in ('ml', 'ul', 'nl', 'pl'), (
            "%s: unexpected unit for volume (%s)"%(self.name, unit))
        tvolume = str(volume) + ' ' + unit
        self._send('tvolume ' + tvolume, response_lines=0)
        assert self.get_target_volume() == tvolume, (
                "%s: unexpected target volume"%self.name)
        if self.verbose:
            print("%s: -> done setting target volume."%self.name)
        return None

    def get_run_direction(self):
        if self.verbose:
            print("%s: getting run direction"%self.name)
        direction = self._send('load', response_lines=1)[0].split()[3]
        assert direction in ('Withdraw', 'Infuse'), (
            "%s: run direction (%s) not supported"%(self.name, direction))
        if direction == 'Withdraw':
            self.run_direction = 'withdraw'
        else:
            self.run_direction = 'infuse'
        if self.verbose:
            print("%s: = %s"%(self.name, self.run_direction))
        return self.run_direction

    def set_run_direction(self, direction):
        if self.verbose:
            print("%s: setting run direction = %s"%(self.name, direction))
        assert direction in ('withdraw', 'infuse'), (
            "%s: unknown run direction (%s)"%(self.name, direction))
        if direction == 'withdraw':
            self._send('load qs w', response_lines=0)
        else:
            self._send('load qs i', response_lines=0)
        assert self.get_run_direction() == direction
        # unfortunately this command seems to need more time to really be done!
        time.sleep(0.2) 
        if self.verbose:
            print("%s: -> done setting run direction"%self.name)
        return None

    def run(self, block=True):
        if self._running:
            self._finish_running()
        if self.verbose:
            print("%s: running"%self.name)
        self._send('run', response_lines=0)
        self._running = True
        if block:
            self._finish_running()
        return None

    def stop(self):
        if self.verbose:
            print("%s: stopping"%self.name)
        self._send('stop', response_lines=0)
        self._running = False
        return None

    def close(self):
        if self.verbose: print("%s: closing..."%self.name, end=' ')
        self.port.close()
        if self.verbose: print("done.")

if __name__ == '__main__':
    # -> currently this device adaptor assumes the user will setup the device
    # with the touch screen on the physical device and then simply
    # use Python to 'run' the set program OR trigger 'run' with a 5V TTL

    sy_pump = Controller(which_port='COM3', verbose=True, very_verbose=False)

    print('\nSetting min/max flow rates:')
    for direction in ('withdraw', 'infuse'):
        for rate in ('min', 'max'):
            sy_pump.set_flow_rate(direction, rate, None)

##    print('\nSetting flow rates manually: (will crash if out of limits)')
##    for direction in ('withdraw', 'infuse'):
##        for unit in ('nl/min', 'ul/min', 'ml/min'):
##            # for unit options see sy_pump.unit2plps.keys()
##            sy_pump.set_flow_rate(direction, 9, unit)

    print('\nSetting some target volumes:')
    for unit in ('ml', 'ul', 'nl', 'pl'):
        for vol in range(1, 3):
            sy_pump.set_target_volume(vol, unit)

    print('\nToggle run direction:')
    for direction in ('withdraw', 'infuse'):
        sy_pump.set_run_direction(direction)

    iterations = 2 # tested 100 iterations
    print('\nRun the current "program":')
    for i in range(iterations):
        sy_pump.run()

    print('\nNon-blocking call:')
    sy_pump.set_run_direction('withdraw')
    for i in range(iterations):
        sy_pump.run(block=False)
        print(' do something else...')
        sy_pump._finish_running()

    print('\nRun and stop:')
    sy_pump.set_run_direction('infuse')
    sy_pump.set_target_volume(1, 'ul') # set something that takes a finite time!
    for i in range(iterations):
        sy_pump.run(block=False)
        print(' do something else...')
        sy_pump.stop() # race condition! run may already be finishing!
        sy_pump.run()

    sy_pump.close()
