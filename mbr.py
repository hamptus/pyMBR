""" MBR data structure starts on page 88 of FSFA.
Table 5.1 Data structures for the DOS partition table.
Byte range		Description                     Essential
0-445			Boot Code                       No
446-461			Partition Table Entry #1        Yes
462-477			Partition Table Enrty #2        Yes
478-493			Partition Table Enrty #3        Yes
494-509			Partition Table Enrty #4        Yes
510-511			Signature value (0xAA55)        No

Table 5.2 Data structure for DOS partition entries.
Byte Range      Description                     Essential
0-0             Bootable Flag                   No
1-3             Starting CHS Address            Yes
4-4             Partition Type (see table 5.3)  No
5-7             Ending CHS Address              Yes
8-11            Starting LBA Address            Yes
12-15           Size in Sectors                 Yes
"""
import struct
import json


# Table 5.3 Some of the type values for DOS partitions.
# More partition values can be found here:
# http://www.win.tue.nl/~aeb/partitions/partition_types-1.html
DOS_PARTITIONS = {
    0x00: "Empty",
    0x01: "FAT12, CHS",
    0x04: "FAT16, 16-32 MB, CHS",
    0x05: "Microsoft Extended, CHS",
    0x06: "FAT16, 32 MB-2GB, CHS",
    0x07: "NTFS",
    0x0b: "FAT32, CHS",
    0x0c: "FAT32, LBA",
    0x0e: "FAT16, 32 MB-2GB, LBA",
    0x0f: "Microsoft Extended, LBA",
    0x11: "Hidden Fat12, CHS",
    0x14: "Hidden FAT16, 16-32 MB, CHS",
    0x16: "Hidden FAT16, 32 MB-2GB, CHS",
    0x1b: "Hidden FAT32, CHS",
    0x1c: "Hidden FAT32, LBA",
    0x1e: "Hidden FAT16, 32 MB-2GB, LBA",
    0x42: "Microsoft MBR, Dynamic Disk",
    0x82: "Solaris x86 -or- Linux Swap",
    0x83: "Linux",
    0x84: "Hibernation",
    0x85: "Linux Extended",
    0x86: "NTFS Volume Set",
    0x87: "NTFS Volume SET",
    0xa0: "Hibernation",
    0xa1: "Hibernation",
    0xa5: "FreeBSD",
    0xa6: "OpenBSD",
    0xa8: "Mac OSX",
    0xa9: "NetBSD",
    0xab: "Mac OSX Boot",
    0xb7: "BSDI",
    0xb8: "BSDI swap",
    # FIXME: I'm pretty sure 0xdb is a recovery partition
    0xdb: "Recovery Partition",
    0xde: "Dell Diagnostic Partition",
    0xee: "EFI GPT Disk",
    0xef: "EFI System Partition",
    0xfb: "Vmware File System",
    0xfc: "Vmware swap",
    # FIXME Add flag for VirtualBox Partitions
}

# FIXME find way to determine sector size
SECTOR_SIZE = 512


class Partition(object):
    """
    Object for storing Partition Data
    """

    def __init__(self, data, parent=None):
        """
        To get the correct lba value for extended partitions, we need to add
        the lba value from the extended partition. For example, if you read the
        first 4 partitions and the fourth is an extended partition with an lba
        of 1000, we seek to the 1000th sector. Then we read the next mbr,
        adding the 1000 from the extended partition to each lba.
        """
        self.parent = parent
        self.bootable_flag = struct.unpack("<B", data[0])[0]
        self.start_chs_address = struct.unpack("<BH", data[1:4])[0]
        self.partition_type = struct.unpack("<B", data[4])[0]
        self.end_chs_address = struct.unpack("<BH", data[5:8])[0]
        # FIXME Check to see how the lba address bytes are used
        if self.get_type() == 'Empty':
            self.lba = 0
        else:
            self.lba = struct.unpack("<L", data[8:12])[0]

        self.size = struct.unpack("<L", data[12:16])[0]


    def get_type(self):
        """
        Returns the text value of the partition type
        """
        return DOS_PARTITIONS[self.partition_type]


    def __repr__(self):
        return self.get_type()

    def is_bootable(self):
        """
        Returns True if this partition is bootable
        """
        return self.bootable_flag == 0x80

    def is_extended(self):
        """
        Returns True if the partition is an extended partition
        """
        return 'Extended' in self.get_type()


class Mbr(object):
    """
    Parses the Master Boot Record
    """

    def __init__(self, data, parent=None):
        self.boot_code = struct.unpack("<446B", data[0:446])
        self.partitions = []
        self.partitions.append(Partition(data[446:462], parent))
        self.partitions.append(Partition(data[462:478], parent))
        self.partitions.append(Partition(data[478:494], parent))
        self.partitions.append(Partition(data[494:510], parent))
        self.signature = struct.unpack("<H", data[510:])[0]

    @property
    def extended_partitions(self):
        return [i for i in self.partitions if 'Extended' in i.get_type()]

    def validate_signature(self):
        """
        Returns True if signature = 0xAA55 (a valid MBR signature)
        """
        return self.signature == 0xAA55

    def add_partitions(self, disk):
        """
        Adds partitions from extended partitions to the MBR class
        """
        for partition in self.partitions:
            if 'Extended' in partition.get_type():
                with open(disk, 'rb') as hd:
                    hd.seek(partition.read_start)
                    new_mbr = Mbr(hd.read(512), lba_offset=partition.lba)
                    self.partitions.extend(new_mbr.partitions)

                new_mbr.add_partitions(disk)

    def json(self):
        mbr_dict = {'Signature': self.signature}
        mbr_dict['Partitions'] = []
        for number, partition in enumerate(self.partitions):
            part_name = "Partition%s" % (number + 1)
            mbr_dict['Partitions'].append(
                {part_name: {'Type': partition.get_type(),
                             'Bootable': partition.is_bootable(),
                             'CHS start': partition.start_chs_address,
                             'CHS end': partition.end_chs_address,
                             'Logical block address': partition.lba,
                             'Size': partition.size,}})

        return json.dumps(['Master Boot Record', mbr_dict], indent=4)

"""
ABOUT EXTENDED PARTITIONS

The starting address for a secondary File System partition is relative to the
current partition table.

The starting address for a secondary extended partition entry is relative to
the primary extended partition.
"""

def get_extended_tables(primary_lba, extended_lba, disk):
    disk.seek(0)
    disk.seek((primary_lba + extended_lba) * SECTOR_SIZE)
    mbr = Mbr(disk.read(512))
    yield mbr
    for partition in mbr.partitions:
        if partition.is_extended():
            for mbr in get_extended_tables(primary_lba, partition.lba, disk):
                yield mbr

def get_partition_tables(open_disk):
    with open(open_disk, 'rb') as disk:
        mbr = Mbr(disk.read(512))
        yield mbr
        disk.seek(0)
        for partition in mbr.partitions:
            if partition.is_extended():
                primary_lba = partition.lba
                mbrs = get_extended_tables(primary_lba, 0, disk)
                for mbr in mbrs:
                    yield mbr

if __name__=='__main__':
    import sys
    args = sys.argv
    partition_tables = get_partition_tables(args[1])
    for pt in partition_tables:
        for partition in pt.partitions:
            print partition
