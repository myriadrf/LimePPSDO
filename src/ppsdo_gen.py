#!/usr/bin/env python3

#
# This file is part of LimePSB_RPCM_GW.
#
# Copyright (c) 2024-2025 Lime Microsystems.
# SPDX-License-Identifier: Apache-2.0
#
# Standalone PPSDO core generator.
#

import os
import sys
import argparse

sys.path.append("../../")

from migen import *

from litex.gen import *

from litex.build.generic_platform  import *
from litex.build.generic_toolchain import *

from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from LimeDFB.pps_detector.src.pps_detector import PPSDetector
from LimeDFB.vctcxo_tamer.src.vctcxo_tamer import VCTCXOTamer

# IOs/Interfaces -----------------------------------------------------------------------------------

def get_common_ios():
    return [
        # Sys Clk/Rst.
        ("sys_clk", 0, Pins(1)),
        ("sys_rst", 0, Pins(1)),

        # RF Clk/Rst.
        ("rf_clk", 0, Pins(1)),
        ("rf_rst", 0, Pins(1)),

        # UART.
        ("uart", 0,
            Subsignal("tx", Pins(1)),
            Subsignal("rx", Pins(1)),
        ),

        # Enable.
        ("enable", 0, Pins(1)),

        # PPS.
        ("pps", 0, Pins(1)),

        # Config Inputs.
        ("config_1s_target",   0, Pins(32)),
        ("config_1s_tol",      0, Pins(32)),
        ("config_10s_target",  0, Pins(32)),
        ("config_10s_tol",     0, Pins(32)),
        ("config_100s_target", 0, Pins(32)),
        ("config_100s_tol",    0, Pins(32)),

        # Status Outputs.
        ("status_1s_error",      0, Pins(32)),
        ("status_10s_error",     0, Pins(32)),
        ("status_100s_error",    0, Pins(32)),
        ("status_dac_tuned_val", 0, Pins(16)),
        ("status_accuracy",      0, Pins(8)),
        ("status_state",         0, Pins(8)),
        ("status_pps_active",    0, Pins(1)),
    ]

# Platform -----------------------------------------------------------------------------------------

class Platform(GenericPlatform):
    def __init__(self):
        super().__init__(device="", io=get_common_ios())
        self.toolchain._support_mixed_language = False

    def build(self, fragment, build_dir, build_name, **kwargs):
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)
        conv_output = self.get_verilog(fragment, name=build_name)
        conv_output.write(f"{build_name}.v")
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform):
        self.cd_sys = ClockDomain()
        self.cd_rf  = ClockDomain()

        # # #

        sys_clk = platform.request("sys_clk")
        sys_rst = platform.request("sys_rst")
        rf_clk  = platform.request("rf_clk")
        rf_rst  = platform.request("rf_rst")

        self.comb += [
            self.cd_sys.clk.eq(sys_clk),
            self.cd_sys.rst.eq(sys_rst),
            self.cd_rf.clk.eq(rf_clk),
            self.cd_rf.rst.eq(rf_rst),
        ]

# PPSDO --------------------------------------------------------------------------------------------

class PPSDO(SoCCore):
    def __init__(self, sys_clk_freq=6e6, dac_bits=16, firmware_path=None, **kwargs):
        platform = Platform()

        # SoCCore ----------------------------------------------------------------------------------

        # Minimal config to reduce resource usage on small FPGAs:
        # - SERV CPU      : Compact RISC-V to minimize logic.
        # - No timer/ctrl : Not needed; saves resources.
        # - SRAM          : Minimal stack/scratchpad.
        # - ROM           : Automatically reduced to used space by LiteX.

        kwargs["cpu_type"]             = "fazyrv" # Looks like serv has issues with floating point math, changed to fazyrv
        kwargs["with_timer"]           = False
        kwargs["with_ctrl"]            = False
        kwargs["uart_name"]            = "uart"
        kwargs["integrated_sram_size"] = 0x100
        kwargs["integrated_rom_size"]  = 0x2000
        kwargs["integrated_rom_init"]  = firmware_path

        SoCCore.__init__(self, platform, sys_clk_freq, **kwargs)

        # DAC config
        # Calculate max digital value: (2 ^ dac_bits) - 1
        dac_max = (1 << dac_bits) - 1
        self.add_constant("CONFIG_DAC_MIN", 0)
        self.add_constant("CONFIG_DAC_MAX", dac_max)

        # CRG --------------------------------------------------------------------------------------

        self.crg = _CRG(platform)

        # Pads -------------------------------------------------------------------------------------

        pps                  = platform.request("pps")
        enable               = platform.request("enable")

        # Config pads.
        config_1s_target     = platform.request("config_1s_target")
        config_1s_tol        = platform.request("config_1s_tol")
        config_10s_target    = platform.request("config_10s_target")
        config_10s_tol       = platform.request("config_10s_tol")
        config_100s_target   = platform.request("config_100s_target")
        config_100s_tol      = platform.request("config_100s_tol")

        # Status pads.
        status_1s_error      = platform.request("status_1s_error")
        status_10s_error     = platform.request("status_10s_error")
        status_100s_error    = platform.request("status_100s_error")
        status_dac_tuned_val = platform.request("status_dac_tuned_val")
        status_accuracy      = platform.request("status_accuracy")
        status_state         = platform.request("status_state")
        status_pps_active    = platform.request("status_pps_active")

        # PPS Detector -----------------------------------------------------------------------------

        self.pps_detector = PPSDetector(pps=pps)
        self.pps_detector.add_sources()
        self.comb += status_pps_active.eq(self.pps_detector.pps_active)

        # VCTCXO Tamer -----------------------------------------------------------------------------

        self.vctcxo_tamer = VCTCXOTamer(enable=enable, pps=pps)
        self.vctcxo_tamer.add_sources()
        self.bus.add_slave("vctcxo_tamer", self.vctcxo_tamer.bus, region=SoCRegion(size=0x1000))
        self.comb += [
            # Config.
            self.vctcxo_tamer.config_1s_target  .eq(config_1s_target),
            self.vctcxo_tamer.config_1s_tol     .eq(config_1s_tol),
            self.vctcxo_tamer.config_10s_target .eq(config_10s_target),
            self.vctcxo_tamer.config_10s_tol    .eq(config_10s_tol),
            self.vctcxo_tamer.config_100s_target.eq(config_100s_target),
            self.vctcxo_tamer.config_100s_tol   .eq(config_100s_tol),

            # Status.
            status_1s_error      .eq(self.vctcxo_tamer.status_1s_error),
            status_10s_error     .eq(self.vctcxo_tamer.status_10s_error),
            status_100s_error    .eq(self.vctcxo_tamer.status_100s_error),
            status_dac_tuned_val .eq(self.vctcxo_tamer.status_dac_tuned_val),
            status_accuracy      .eq(self.vctcxo_tamer.status_accuracy),
            status_state         .eq(self.vctcxo_tamer.status_state),
        ]

    def export_sources(self, filename):
        gateware_dir = os.path.join("build", self.platform.name, "gateware")
        output_path  = os.path.join(gateware_dir, filename)
        os.makedirs(gateware_dir, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("include_paths = [\n")
            for path in self.platform.verilog_include_paths:
                f.write(f" {repr(path)},\n")
            f.write("]\n\n")
            sources = list(self.platform.sources)
            verilog_file = os.path.join(gateware_dir, f"{self.platform.name}.v")
            if os.path.exists(verilog_file):
                sources.append((verilog_file, "verilog", "work"))
            rom_init = os.path.join(gateware_dir, f"{self.platform.name}_rom.init")
            if os.path.exists(rom_init):
                sources.append((rom_init, None, None))
            sram_init = os.path.join(gateware_dir, f"{self.platform.name}_sram.init")
            if os.path.exists(sram_init):
                sources.append((sram_init, None, None))
            f.write("sources = [\n")
            for source in sources:
                f.write(f" {repr(source)},\n")
            f.write("]\n")

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(description="Standalone PPSDO core generator.")
    parser.add_argument("--build",       action="store_true",  help="Generate Verilog.")
    parser.add_argument("--sys-clk-freq",default=6e6,          help="System clock frequency (default: 6MHz)")
    parser.add_argument("--dac-bits",    default=16,           help="DAC resolution in bits (default: 16")
    args = parser.parse_args()

    # SoC.
    for run in range(2):
        prepare = (run == 0)
        build   = ((run == 1) and args.build)
        soc = PPSDO(
            sys_clk_freq  = int(float(args.sys_clk_freq)),
            dac_bits      = int(args.dac_bits),
            firmware_path = None if prepare else "firmware/firmware.bin",
        )
        soc.platform.name = "ppsdo"
        builder = Builder(soc)
        builder.build(run=build)
        if prepare:
            ret = os.system(f"cd firmware && make clean all")
            if ret != 0:
                raise RuntimeError("Firmware build failed.")

    # Export sources
    soc.export_sources(f"ppsdo_sources.py")

if __name__ == "__main__":
    main()
