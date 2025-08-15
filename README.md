# kds_legato110
Python device adaptor: KDS Legato 110, single syringe, programmable, touch screen, infuse/withdraw pump.
## Quick start:
- Use the touchscreen on the pump to set things up and get familiar (i.e put a syringe on and program in the parameters etc). Try hitting the 'run'/'stop' button and seeing if it does what you want.
- Connect to the pump with a USB cable and check the 'COM' port. On a windows machine the simple (FTDI?) USB driver is auto installed and seems to work.
- Download and run:
  -  "kds_legato110.py" for Python control.
  -  "kds_legato110_gui.py" for an example of simple GUI.
  -  See "kds_legato110_external_trigger_example.py" for how to trigger a 'run' with an external 5V TLL

![social_preview](https://github.com/amsikking/kds_legato110/blob/main/social_preview.png)

## Details:
- See the included "KDS_Legato_100_Series_Quick_Start_Guide_5617-007REVB.pdf" and "KDS_Legato_110_Datasheet_2017.pdf" for basics.
- This adaptor was generated with reference to the included "KDS_Legato_100_Series_Manual_5617-006REV2.0.pdf". The documentation and available commands was 'partial' so significant testing and debugging was needed...
