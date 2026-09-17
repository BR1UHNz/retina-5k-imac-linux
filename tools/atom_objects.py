#!/usr/bin/env python3
"""Dump the ATOM BIOS object tables (display paths, connectors, encoders,
routers, records, GPIO pin LUT, GPIO I2C info) of an AMD legacy ATOM VBIOS."""
import struct, sys

rom = open(sys.argv[1], 'rb').read()
u8 = lambda o: rom[o]
u16 = lambda o: struct.unpack_from('<H', rom, o)[0]
u32 = lambda o: struct.unpack_from('<I', rom, o)[0]

assert rom[0:2] == b'\x55\xaa', 'no option ROM signature'
hdr = u16(0x48)
assert rom[hdr + 4:hdr + 8] == b'ATOM', 'no ATOM signature'
master_data = u16(hdr + 0x20)
print(f"ATOM_ROM_HEADER @0x{hdr:x}  subsys {u16(hdr+0x18):04x}:{u16(hdr+0x1a):04x}  MasterDataTable @0x{master_data:x}")

DATA_TABLES = ['UtilityPipeLine', 'MultimediaCapabilityInfo', 'MultimediaConfigInfo', 'StandardVESA_Timing',
               'FirmwareInfo', 'PaletteData', 'LCD_Info', 'DIGTransmitterInfo', 'AnalogTV_Info',
               'SupportedDevicesInfo', 'GPIO_I2C_Info', 'VRAM_UsageByFirmware', 'GPIO_Pin_LUT',
               'VESA_ToInternalModeLUT', 'ComponentVideoInfo', 'PowerPlayInfo', 'CompassionateData',
               'SaveRestoreInfo', 'PPLL_SS_Info', 'OemInfo', 'XTMDS_Info', 'MclkSS_Info', 'Object_Header',
               'IndirectIOAccess', 'MC_InitParameter', 'ASIC_VDDC_Info', 'ASIC_InternalSS_Info', 'TV_VideoMode',
               'VRAM_Info', 'MemoryTrainingInfo', 'IntegratedSystemInfo', 'ASIC_ProfilingInfo',
               'VoltageObjectInfo', 'PowerSourceInfo', 'ServiceInfo']
tables = {}
for i, name in enumerate(DATA_TABLES):
    off = u16(master_data + 4 + 2 * i)
    if off:
        tables[name] = off
print("data tables:", ', '.join(f"{k}@0x{v:x}(rev {u8(v+2)}.{u8(v+3)}, {u16(v)}b)" for k, v in tables.items()))

OBJ_TYPE = {1: 'GPU', 2: 'ENCODER', 3: 'CONNECTOR', 4: 'ROUTER', 5: 'GENERIC', 6: 'DISPLAY?'}
ENC = {0x13: 'INTERNAL_KLDSCP_TMDS1', 0x14: 'INTERNAL_KLDSCP_DVO1', 0x15: 'INTERNAL_KLDSCP_DAC1',
       0x16: 'INTERNAL_KLDSCP_DAC2', 0x19: 'INTERNAL_KLDSCP_LVTMA', 0x1E: 'INTERNAL_UNIPHY',
       0x20: 'INTERNAL_UNIPHY1', 0x21: 'INTERNAL_UNIPHY2', 0x22: 'NUTMEG', 0x23: 'TRAVIS',
       0x24: 'INTERNAL_VCE', 0x25: 'INTERNAL_UNIPHY3', 0x26: 'INTERNAL_AMCLK', 0x27: 'MHL_SII8620?',
       0x0E: 'MDS/other', 0x1C: 'ALMOND', 0x1D: 'TRAVIS?'}
CONN = {0x01: 'SINGLE_LINK_DVI_I', 0x02: 'DUAL_LINK_DVI_I', 0x03: 'SINGLE_LINK_DVI_D', 0x04: 'DUAL_LINK_DVI_D',
        0x05: 'VGA', 0x06: 'COMPOSITE', 0x07: 'SVIDEO', 0x08: 'YPbPr', 0x09: 'D_CONNECTOR',
        0x0A: '9PIN_DIN', 0x0B: 'SCART', 0x0C: 'HDMI_TYPE_A', 0x0D: 'HDMI_TYPE_B', 0x0E: 'LVDS',
        0x0F: '7PIN_DIN', 0x10: 'PCIE_CONNECTOR', 0x11: 'CROSSFIRE', 0x12: 'HARDCODE_DVI',
        0x13: 'DISPLAYPORT', 0x14: 'eDP', 0x15: 'MXM', 0x16: 'LVDS_eDP', 0x17: 'USBC'}
REC = {1: 'I2C', 2: 'HPD_INT', 3: 'OUTPUT_PROTECTION', 4: 'CONNECTOR_DEVICE_TAG', 5: 'CONNECTOR_DVI_EXT_INPUT',
       6: 'ENCODER_FPGA_CONTROL', 7: 'CONNECTOR_CVTV_SHARE_DIN', 8: 'JTAG', 9: 'OBJECT_GPIO_CNTL',
       10: 'ENCODER_DVO_CF', 11: 'CONNECTOR_CF', 12: 'CONNECTOR_HARDCODE_DTD', 13: 'CONNECTOR_PCIE_SUBCONNECTOR',
       14: 'ROUTER_DDC_PATH_SELECT', 15: 'ROUTER_DATA_CLOCK_PATH_SELECT', 16: 'CONNECTOR_HPDPIN_LUT',
       17: 'CONNECTOR_AUXDDC_LUT', 18: 'OBJECT_LINK', 19: 'CONNECTOR_REMOTE_CAP', 20: 'ENCODER_CAP',
       21: 'BRACKET_LAYOUT', 22: 'CONNECTOR_FORCED_TMDS_CAP', 23: 'DISP_CONNECTOR_CAPS',
       24: 'CONNECTOR_LAYOUT_INFO?', 25: 'EXT_DISPLAY_CONNECTION?', 26: 'CONNECTOR_SPEED_UPTO', 255: 'LAST'}


def objname(oid):
    t = (oid >> 12) & 0xF
    e = (oid >> 8) & 0x7
    idx = oid & 0xFF
    tn = OBJ_TYPE.get(t, f'type{t}')
    if t == 2:
        n = ENC.get(idx, f'0x{idx:02x}')
    elif t == 3:
        n = CONN.get(idx, f'0x{idx:02x}')
    else:
        n = f'0x{idx:02x}'
    return f"{tn}:{n}#enum{e} (0x{oid:04x})"


def records(off):
    out = []
    while True:
        rtype, rsize = u8(off), u8(off + 1)
        if rtype == 0xFF or rsize == 0:
            break
        body = rom[off + 2:off + rsize]
        desc = REC.get(rtype, f'rec{rtype}')
        extra = ''
        if rtype == 1:
            i2c = body[0]
            extra = f" i2cId=0x{i2c:02x}(hwcap={i2c>>7} engine={(i2c>>4)&7} line_mux={i2c&0xF}) addr=0x{body[1]:02x}"
        elif rtype == 2:
            extra = f" HPD gpioId={body[0]} plugged_pin_state={body[1]}"
        elif rtype == 4:
            n = body[0]
            tags = [f"acpiId=0x{u32(off+2+4+i*4):08x}/devTag=0x{u16(off+2+4+i*4+4):04x}" for i in range(0)]
            extra = f" numDeviceTags={n} raw={body.hex(' ')}"
        elif rtype == 9:
            extra = f" gpio objectID={body[0]} flags=0x{body[1]:02x} pinId={body[2] if len(body)>2 else '?'} raw={body.hex(' ')}"
        elif rtype == 11:
            extra = f" CF usMaxPixClk? raw={body.hex(' ')}"
        elif rtype == 20:
            caps = u16(off + 2)
            extra = f" encoderCaps=0x{caps:04x}(HBR2={caps&1} HBR2_EN={(caps>>1)&1} HDMI6G={(caps>>2)&1} HBR3?={(caps>>3)&1}) raw={body.hex(' ')}"
        elif rtype == 18:
            extra = f" link raw={body.hex(' ')}"
        elif rtype == 23:
            extra = f" connectorCaps raw={body.hex(' ')}"
        else:
            extra = f" raw={body.hex(' ')}"
        out.append(f"      [{desc}]{extra}")
        off += rsize
    return out


oh = tables['Object_Header']
print(f"\nObject_Header @0x{oh:x} rev {u8(oh+2)}.{u8(oh+3)} usDeviceSupport=0x{u16(oh+4):04x}")
conn_t = oh + u16(oh + 6)
router_t = oh + u16(oh + 8)
enc_t = oh + u16(oh + 10)
prot_t = oh + u16(oh + 12)
path_t = oh + u16(oh + 14)
misc_t = oh + u16(oh + 16) if u16(oh + 2) >= 18 else None

DEV_SUPPORT = {0x0001: 'CRT1', 0x0002: 'LCD1', 0x0004: 'TV1', 0x0008: 'DFP1', 0x0010: 'CRT2', 0x0020: 'LCD2',
               0x0040: 'DFP6', 0x0080: 'DFP2', 0x0100: 'CV', 0x0200: 'DFP3', 0x0400: 'DFP4', 0x0800: 'DFP5'}
ds = u16(oh + 4)
print("  device support:", [n for b, n in DEV_SUPPORT.items() if ds & b])

n = u8(path_t)
print(f"\nDisplay paths ({n}):")
p = path_t + 4
for i in range(n):
    dtag, size, conn, gpu = u16(p), u16(p + 2), u16(p + 4), u16(p + 6)
    gfx = [u16(p + 8 + 2 * k) for k in range((size - 8) // 2)]
    tag = [nm for b, nm in DEV_SUPPORT.items() if dtag & b]
    print(f"  path{i}: devTag=0x{dtag:04x}{tag} conn={objname(conn)} gpu=0x{gpu:04x} chain={[objname(g) for g in gfx]}")
    p += size


def dump_table(name, t):
    n = u8(t)
    print(f"\n{name} objects ({n}):")
    for i in range(n):
        o = t + 4 + i * 8
        oid, srcdst, rec = u16(o), u16(o + 2), u16(o + 4)
        line = f"  {objname(oid)}"
        if srcdst:
            sd = oh + srcdst
            nsrc = u8(sd)
            srcs = [u16(sd + 1 + 2 * k) for k in range(nsrc)]
            ndst = u8(sd + 1 + 2 * nsrc)
            dsts = [u16(sd + 2 + 2 * nsrc + 2 * k) for k in range(ndst)]
            line += f" src={[objname(s) for s in srcs]} dst={[objname(d) for d in dsts]}"
        print(line)
        if rec:
            for r in records(oh + rec):
                print(r)


dump_table('Connector', conn_t)
dump_table('Encoder', enc_t)
if u16(oh + 8):
    dump_table('Router', router_t)
if misc_t and u16(oh + 16):
    dump_table('Misc', misc_t)

# GPIO pin LUT: ATOM_GPIO_PIN_LUT { header; ATOM_GPIO_PIN_ASSIGNMENT asGPIO_Pin[] { usGpioPin_AIndex(2), ucGpioPinBitShift(1), ucGPIO_ID(1) } }
if 'GPIO_Pin_LUT' in tables:
    t = tables['GPIO_Pin_LUT']
    size = u16(t)
    print(f"\nGPIO_Pin_LUT ({(size-4)//4} pins): regIndex/shift -> gpioId")
    for k in range((size - 4) // 4):
        o = t + 4 + k * 4
        print(f"  gpioId={u8(o+3):3d}  regIndex=0x{u16(o):04x} (mmio byte off 0x{u16(o)*4:x}) bit={u8(o+2)}")

# GPIO_I2C_Info: ATOM_GPIO_I2C_INFO { header; ATOM_GPIO_I2C_ASSIGMENT asGPIO_Info[] } each 27 bytes (rev 1.x)
if 'GPIO_I2C_Info' in tables:
    t = tables['GPIO_I2C_Info']
    size = u16(t)
    rec = 27
    print(f"\nGPIO_I2C_Info ({(size-4)//rec} entries):")
    for k in range((size - 4) // rec):
        o = t + 4 + k * rec
        (clkMask, clkEn, clkY, clkA, dataMask, dataEn, dataY, dataA) = struct.unpack_from('<8H', rom, o)
        i2cid = u8(o + 16)
        print(f"  i2cId=0x{i2cid:02x}(line {i2cid&0xF}, hw={i2cid>>7}) clkA_reg=0x{clkA:04x} dataA_reg=0x{dataA:04x} clkMask=0x{clkMask:04x} "
              f"shifts clkMask={u8(o+17)} clkEn={u8(o+18)} clkY={u8(o+19)} clkA={u8(o+20)} raw17..26={rom[o+17:o+27].hex(' ')}")
