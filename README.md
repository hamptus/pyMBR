# pyMBR
Read the Master Boot Record using Python

This was written for use in the DC3 challenge. It has been tested on Windows 7
and Linux. 

To parse a drive on Windows, open the disk as shown here: 
https://support.microsoft.com/en-us/kb/100027

for example:

`python mbr.py \\.\PhysicalDrive0`

Or, for Linux:

`python mbr.py /dev/sda`
