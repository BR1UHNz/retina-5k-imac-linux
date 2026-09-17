# Live measurements, stock 7.2.5 + keeper, dual-tile 5K (2026-09-16 16:36)
Link A (eDP-1): 0x200-0x207 = 01 00 77 77 01 01 00 00 ; (0x41C,0x425,0x4F1) = 15 00 01 ; 0x10A=00 ; 0x101=84 ; 0x310=00 00 00 ; 0x600=01
Link B (DP-1):  0x200-0x207 = 01 00 77 77 81 01 00 00 ; (0x41C,0x425,0x4F1) = 00 00 01 ; 0x10A=00 ; 0x101=84 ; 0x310=00 00 00 ; 0x600=01
Compat tuple (link A, earlier): 05 02 00.  DPMS-off (link A D3): 0x200=01 00 00 00 80 00, 0x600=02, 0x4F1=00, DP-1 disconnected.
OTG0/OTG1 totals 2720x2962 (stock layout: eDP-1=OTG0, DP-1=OTG1). Phase deltas 0..1.5 lines.
=> 0x205 == 01 on BOTH links in native mode: the link-health readiness criterion (SINK_STATUS bit0) is valid on this TCON.
=> Both links' EDID product 0xAE02 (256 bytes) in native mode.
Registers after stock one-shot sync: TRIGB 0x10800, FORCE_COUNT_NOW 0x100 on both OTGs, MASTER_UPDATE_MODE 0, DCIO_GSL0_CNTL(0x4826)=0, 0x4a26=0, 0x4c26=0x7bbb7df1.
