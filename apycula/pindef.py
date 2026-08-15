from os.path import expanduser
from glob import glob
import json
import os
import csv
import copy

VeryTrue = 2

# caches
# .CSV index of vendor files {(device, package) : file_name}
_pindef_index = {}
# (device, package) : pins
_pindef_files = {}

# GW1N-UV2 uses the GW1N-2 die, but not the GW1N-1P5C QFN48XF package.
# This is the QN48 column of Gowin UG171.xlsx
# (SHA256 2fc6a36204215c2104efb34a70000fee352e1dfc21fb96a04767c9ae4e0b10ad).
# Keep every physical pin here, including supplies and ground, so the package
# definition is auditable and cannot turn into another QFN48XF proxy by accident.
GW1N_2_QN48_PINOUT = {
    "1": "VCCIO0", "2": "VSS", "3": "IOT16A", "4": "IOT14B",
    "5": "IOT14A", "6": "IOT11A", "7": "IOT11B", "8": "IOT9B",
    "9": "IOT9A", "10": "IOT7B", "11": "IOT7A", "12": "VCC",
    "13": "IOT2A", "14": "IOL4B", "15": "IOL4A", "16": "IOL5A",
    "17": "IOL5B", "18": "IOL6A", "19": "IOL6B", "20": "IOL11A",
    "21": "IOL11B", "22": "IOL15B", "23": "IOL15A", "24": "IOL17B",
    "25": "VCCIO3/VCCIO4/VCCIO5", "26": "VSS", "27": "IOL17A",
    "28": "IOB5B", "29": "IOB5A", "30": "IOB7B", "31": "IOB7A",
    "32": "IOB13B", "33": "IOB13A", "34": "IOB18A", "35": "IOB18B",
    "36": "VCCIO2/VCCX", "37": "VCC/VCCIO1", "38": "IOR13A",
    "39": "IOR13B", "40": "IOR11B", "41": "IOR11A", "42": "IOR5B",
    "43": "IOR5A", "44": "IOR3B", "45": "IOR3A", "46": "IOR1B",
    "47": "IOR1A", "48": "IOT16B",
}

_GW1N_2_QN48_EXTRA_IO = {
    "IOT2A": {"BANK": 0, "CFG": "MODE0", "DIFF": "P", "PAIR": "IOT2B"},
    "IOT11A": {"BANK": 0, "CFG": "GCLKT_0", "DIFF": "P", "PAIR": "IOT11B", "TRUELVDS": True, "X16": True},
    "IOT11B": {"BANK": 0, "CFG": "GCLKC_0", "DIFF": "N", "PAIR": "IOT11A", "TRUELVDS": True},
    "IOT16A": {"BANK": 0, "CFG": "JTAGSEL_N", "DIFF": "P", "PAIR": "IOT16B"},
    "IOT16B": {"BANK": 0, "CFG": "RECONFIG_N", "DIFF": "N", "PAIR": "IOT16A"},
    "IOL5A": {"BANK": 5, "CFG": "LPLL_T_IN", "DIFF": "P", "PAIR": "IOL5B"},
    "IOL5B": {"BANK": 5, "CFG": "LPLL_C_IN", "DIFF": "N", "PAIR": "IOL5A"},
    "IOL15A": {"BANK": 3, "DIFF": "P", "PAIR": "IOL15B", "TRUELVDS": True, "X16": True},
    "IOL15B": {"BANK": 3, "DIFF": "N", "PAIR": "IOL15A", "TRUELVDS": True},
    "IOB13A": {"BANK": 2, "DIFF": "P", "PAIR": "IOB13B", "TRUELVDS": True, "X16": True},
    "IOB13B": {"BANK": 2, "DIFF": "N", "PAIR": "IOB13A", "TRUELVDS": True},
    "IOR3A": {"BANK": 1, "CFG": "D2", "DIFF": "P", "PAIR": "IOR3B", "TRUELVDS": True},
    "IOR3B": {"BANK": 1, "CFG": "D3", "DIFF": "N", "PAIR": "IOR3A", "TRUELVDS": True},
    "IOR5A": {"BANK": 1, "CFG": "MI/D7", "DIFF": "P", "PAIR": "IOR5B", "TRUELVDS": True},
    "IOR5B": {"BANK": 1, "CFG": "MO/D6", "DIFF": "N", "PAIR": "IOR5A", "TRUELVDS": True},
}

def get_package(device, package, special_pins):
    global _pindef_files
    if device == "GW1N-1P5C" and package == "QN48":
        if (device, "QFN48XF") not in _pindef_index:
            all_packages(device)
        source = get_package(device, "QFN48XF", VeryTrue)
        by_name = {pin["NAME"]: pin for pin in source}
        pins = []
        for index, name in GW1N_2_QN48_PINOUT.items():
            if name not in by_name and name not in _GW1N_2_QN48_EXTRA_IO:
                continue
            pin = copy.deepcopy(by_name.get(name, {"NAME": name, "TYPE": "I/O"}))
            pin.update(_GW1N_2_QN48_EXTRA_IO.get(name, {}))
            pin["INDEX"] = index
            pins.append(pin)
        if special_pins != VeryTrue:
            pins = [pin for pin in pins if 'CFG' not in pin or (
                pin['CFG'] != 'RECONFIG_N' and not pin['CFG'].startswith('JTAGSEL_N'))]
        if not special_pins:
            return [pin for pin in pins if 'CFG' not in pin]
        return pins
    if (device, package) not in _pindef_files:
        gowinhome = os.getenv("GOWINHOME")
        if not gowinhome:
            raise Exception("GOWINHOME not set")
        with open(_pindef_index[(device, package)]) as f:
            pins = json.load(f)
        _pindef_files[(device, package)] = [d for d in pins['PIN_DATA'] if d['TYPE'] == 'I/O']

    if special_pins != VeryTrue:
        pins = [pin for pin in _pindef_files[(device, package)]
                if 'CFG' not in pin.keys() or (
                    pin['CFG'] != 'RECONFIG_N' and not pin['CFG'].startswith('JTAGSEL_N'))]
    else:
        pins = _pindef_files[(device, package)]
    if not special_pins:
        return [pin for pin in pins if 'CFG' not in pin.keys()]
    return pins

# {partnumber : (pkg, device, speed)}
def all_packages(device):
    gowinhome = os.getenv("GOWINHOME")
    if not gowinhome:
        raise Exception("GOWINHOME not set")
    # {package: speed} vendor file
    speeds = {}
    with open(f"{gowinhome}/IDE/data/device/device_info.csv", mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, fieldnames =
            ["unused_id", "partnumber", "series", "device", "unused_0", "unused_1", "package", "voltage", "speed"])
        for row in csv_reader:
            if row['device'] != device:
               continue
            speeds.update({row['partnumber']: row['speed']})
    global _pindef_index
    # _pindef_index = {}
    res = {}
    with open(f"{gowinhome}/IDE/data/device/device_package.csv", mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, fieldnames =
            ["unused_id", "partnumber", "series", "device", "package", "filename"])
        for row in csv_reader:
            if row['device'] != device:
               continue
            res[row['partnumber']] = (row['package'], device, speeds[row['partnumber']])
            _pindef_index[(row['device'], row['package'])] = \
                    f"{gowinhome}/IDE/data/device/{row['filename']}"
    return res

def get_pins(device, package, special_pins=False):
    df = get_package(device, package, special_pins)
    res = {}
    for pin in df:
        res.setdefault(str(pin['BANK']), []).append(str(pin['INDEX']))
    return res

def get_bank_pins(device, package):
    df = get_package(device, package, VeryTrue)
    res = {}
    for pin in df:
        res[pin['NAME']] = str(pin['BANK'])
    return res

def get_locs(device, package, special_pins=False):
    df = get_package(device, package, special_pins)
    res = set()
    for pin in df:
        res.update({pin['NAME']})
    return res

def get_pin_locs(device, package, special_pins=False):
    df = get_package(device, package, special_pins)
    res = {}
    for pin in df:
        cfgs = []
        if 'CFG' in pin.keys():
            cfgs = pin['CFG'].split('/')
        res[str(pin['INDEX'])] = (pin['NAME'], cfgs)
    return res

def get_clock_locs(device, package):
    df = get_package(device, package, True)
    return [(pin['NAME'], *pin['CFG'].split('/')) for pin in df
            if 'CFG' in pin.keys() and pin['CFG'].startswith("GCLK")]

def get_pll_pads_locs(device, package):
    df = get_package(device, package, True)
    return [(pin['NAME'], *pin['CFG'].split('/')) for pin in df
            if 'CFG' in pin.keys() and 'PLL' in pin['CFG']]

# { name : (is_diff, is_true_lvds, is_positive, adc_bus)}
def get_diff_adc_cap_info(device, package, special_pins=False):
    df = get_package(device, package, special_pins)
    res = {}
    # If one pin of the pair is forbidden for the diff IO,
    # we can determine this only after we read the data of all pairs
    positive = {}
    negative = {}
    for pin in df:
        is_positive = False
        is_diff = 'DIFF' in pin.keys()
        adc_bus = None
        if 'ADC_INPUT' in pin.keys() and pin['ADC_INPUT']:
            adc_bus = pin['ADC_INPUT']

        if not is_diff:
            res[str(pin['NAME'])] = (is_diff, is_true_lvds, is_positive, adc_bus)
            continue
        is_true_lvds = 'TRUELVDS' in pin.keys()

        if pin['DIFF'] == 'P':
            is_positive = True
            positive[str(pin['NAME'])] = (is_diff, is_true_lvds, is_positive, adc_bus, str(pin['PAIR']))
        else:
            is_positive = False
            negative[str(pin['NAME'])] = (is_diff, is_true_lvds, is_positive, adc_bus)
    # check the pairs
    for pos_name, pos_flags in positive.items():
        neg_name = pos_flags[-1]
        if neg_name in negative.keys():
            res.update({pos_name : pos_flags[0:-1]})
            res.update({neg_name : negative[neg_name]})
    return res
