# Imports from the python standard library:
import tkinter as tk

# Our code, one .py file per module, copy files to your local directory:
import kds_legato110 # github.com/amsikking/kds_legato110

class GuiSyringePump:
    def __init__(self, init_hardware=True): # set False for GUI design... 
        self.root = tk.Tk()
        self.root.title('Syringe Pump GUI')
        # load GUI:
        self.init_sy_pump()
        # optionally initialize hardware:
        if init_hardware:
            self.sy_pump = kds_legato110.Controller(
                which_port='COM3', verbose=True, very_verbose=False)
            self._update_settings()
        # add close function + any commands for when the user hits the 'X'
        def _close():
            if init_hardware:
                self.sy_pump.close()
            self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", _close)
        # start event loop:
        self.root.mainloop() # blocks here until 'X'

    def init_sy_pump(self):
        frame = tk.LabelFrame(self.root, text='SYRINGE PUMP', bd=6)
        frame.grid(padx=10, pady=10)
        # attributes to display:
        self._version = tk.StringVar()
        self.sy_type = tk.StringVar()
        self.tvolume = tk.DoubleVar()
        self.run_direction = tk.StringVar()
        self.flow_rate = tk.StringVar()
        self.run_time_s = tk.DoubleVar()
        # make dictionary with labels:
        labels = {
            'Syringe pump:':        self._version,
            'Syringe type:':        self.sy_type,
            'Target volume:':       self.tvolume,
            'Run direction:':       self.run_direction,
            'Flow rate:':           self.flow_rate,
            'Estimated time (s):':  self.run_time_s
                }
        # populate gui:
        for i, (k, v) in enumerate(labels.items()):
            key_label = tk.Label(frame, text=k)
            val_label = tk.Label(frame, textvariable=v)
            key_label.grid(row=i, column=0, padx=5, pady=5, sticky='w')
            val_label.grid(row=i, column=1, padx=5, pady=5, sticky='w')
        # run button:
        def _run():
            self.sy_pump.run(block=False)
            run_button.config(state='disabled', text='Running...')
            def _finish_run():
                if self.sy_pump._running: # only call if _stop wasn't called...
                    self.sy_pump._finish_running()
                    run_button.config(state='normal', text='Run')
            self.root.after(int(1e3*self.run_time_s.get()), _finish_run)
        run_button = tk.Button(
            frame, text='Run', command=_run, width=20, height=2)
        run_button.grid(
            row=len(labels), column=0, columnspan=2, padx=5, pady=5)
        # stop button:
        def _stop():
            self.sy_pump.stop()
            run_button.config(state='normal', text='Run')
        stop_button = tk.Button(
            frame, text='Stop', command=_stop, width=20, height=2)
        stop_button.grid(
            row=len(labels) + 1, column=0, columnspan=2, padx=5, pady=5)

    def _update_settings(self):
        self._version.set(self.sy_pump._version)
        self.sy_type.set(self.sy_pump.sy_type)
        self.tvolume.set(self.sy_pump.tvolume)
        self.run_direction.set(self.sy_pump.run_direction)
        if self.sy_pump.run_direction == 'withdraw':
            self.flow_rate.set(self.sy_pump.wrate)
            self.run_time_s.set(self.sy_pump.wrun_time_s)
        else:
            self.flow_rate.set(self.sy_pump.irate)
            self.run_time_s.set(self.sy_pump.irun_time_s)

if __name__ == '__main__':
    gui_sy_pump = GuiSyringePump(init_hardware=True)
