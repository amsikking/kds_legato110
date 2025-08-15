# Third party imports, installable via pip:
import numpy as np

# Our code, one .py file per module, copy files to your local directory:
import ni_PCIe_6738     # github.com/amsikking/ni_PCIe_6738
import kds_legato110    # github.com/amsikking/kds_legato110

'''Run the syringe pump with an external trigger'''
# -> D-sub 15, Pin3 = Footswitch Input, Pin9 = Signal Return / Ground
# -> configure to a rising or falling edge with '_set_footswitch_mode' method

ao = ni_PCIe_6738.DAQ(num_channels=1, rate=1e6, verbose=True)
sy_pump = kds_legato110.Controller(which_port='COM3', verbose=True)

triggers = 2
trigger_period_px = ao.s2p(0.1) # 0.1s minimum for device
run_period_px = ao.s2p(sy_pump.irun_time_s) # -> withdraw or infuse time!
jitter_px = ao.s2p(0.2) # extra time to ensure the run is finished -> 0.2s?
period_px = trigger_period_px + run_period_px + jitter_px

voltage_series = []
for i in range(triggers):
    volt_period = np.zeros((period_px, ao.num_channels), 'float64')
    volt_period[:trigger_period_px, 0] = 5 # 5V TLL falling edge trigger
    voltage_series.append(volt_period)
voltages = np.concatenate(voltage_series, axis=0)

# can the syringe pumpu keep up?
for i in range(2):
    ao.play_voltages(voltages) # race condition!

time_s = ao.p2s(voltages.shape[0])
events_per_s = triggers / time_s
print('events_per_s = %02f'%events_per_s) # forced by ao play

sy_pump.close()
ao.close()
