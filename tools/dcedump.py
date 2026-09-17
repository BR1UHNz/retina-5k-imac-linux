#!/usr/bin/python3
"""Dump the DCE 10 display-pipeline registers that matter for the tiled 5K panel (root)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux import Regs

PER_PIPE = [
    ('GRPH_CONTROL', 0x1a01), ('GRPH_SWAP_CNTL', 0x1a03), ('GRPH_PRIMARY_SURFACE_ADDRESS', 0x1a04),
    ('GRPH_PITCH', 0x1a06), ('GRPH_SURFACE_OFFSET_X', 0x1a09), ('GRPH_SURFACE_OFFSET_Y', 0x1a0a),
    ('GRPH_X_START', 0x1a0b), ('GRPH_Y_START', 0x1a0c), ('GRPH_X_END', 0x1a0d), ('GRPH_Y_END', 0x1a0e),
    ('GRPH_UPDATE', 0x1a11), ('GRPH_FLIP_CONTROL', 0x1a12), ('GRPH_SURFACE_ADDRESS_INUSE', 0x1a13),
    ('SCL_MODE', 0x1b42), ('VIEWPORT_START', 0x1b5c), ('VIEWPORT_SIZE', 0x1b5d),
    ('DPG_WATERMARK_MASK_CONTROL', 0x1b32), ('DPG_PIPE_DPM_CONTROL', 0x1b34),
    ('DPG_PIPE_URGENCY_CONTROL', 0x1b33), ('DPG_PIPE_STUTTER_CONTROL', 0x1b35),
    ('DPG_PIPE_NB_PSTATE_CHANGE_CONTROL', 0x1b36), ('DPG_PIPE_STUTTER_CONTROL_NONLPTCH', 0x1b37),
    ('CRTC_H_TOTAL', 0x1b80), ('CRTC_H_BLANK_START_END', 0x1b81), ('CRTC_H_SYNC_A', 0x1b82),
    ('CRTC_V_TOTAL', 0x1b87), ('CRTC_V_BLANK_START_END', 0x1b8e), ('CRTC_V_SYNC_A', 0x1b89),
    ('CRTC_CONTROL', 0x1b9c), ('CRTC_BLANK_CONTROL', 0x1b9e), ('CRTC_TRIGA_CNTL', 0x1b94),
    ('CRTC_TRIGB_CNTL', 0x1b96), ('CRTC_FORCE_COUNT_NOW_CNTL', 0x1b98),
    ('CRTC_MASTER_UPDATE_MODE', 0x1bbe), ('CRTC_MASTER_UPDATE_LOCK', 0x1bbd),
    ('BLND_CONTROL', 0x1bc0), ('BLND_V_UPDATE_LOCK', 0x1bc7),
    ('FMT_BIT_DEPTH_CONTROL', 0x1bd2), ('FMT_CONTROL', 0x1bd3), ('FMT_DYNAMIC_EXP_CNTL', 0x1bd8),
]
GLOBAL = [
    ('DMIF_CONTROL', 0x2f6), ('DMIF_STATUS', 0x2f7), ('DMIF_STATUS2', 0x304),
    ('PIPE0_DMIF_BUFFER_CONTROL', 0x321), ('PIPE1_DMIF_BUFFER_CONTROL', 0x322),
    ('DCIO_GSL0_CNTL', 0x4826), ('DC_LB_MEMORY_SPLIT?', 0x1b41),
]
r = Regs()
for name, off in GLOBAL:
    print(f'{name:36s} 0x{r.rd(off):08x}')
for p in range(2):
    print(f'--- pipe {p}')
    for name, off in PER_PIPE:
        print(f'  {name:34s} 0x{r.rd(off + 0x200 * p):08x}')
r.close()
