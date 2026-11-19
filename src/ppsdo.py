#!/usr/bin/env python3
#
# This file is part of LimePSB_RPCM_GW.
#
# Copyright (c) 2024-2025 Lime Microsystems.
#
# SPDX-License-Identifier: Apache-2.0

import os

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *
from litex.gen.genlib.cdc import BusSynchronizer

from litex.soc.interconnect.csr import *

# PPSDO Layouts ------------------------------------------------------------------------------------

ppsdo_uart_layout = [
    ("rx",  1),
    ("tx",  1),
]

ppsdo_config_layout = [
    ("one_s_target",    32, DIR_M_TO_S),  # Target value for 1-second interval.
    ("one_s_tol",       32, DIR_M_TO_S),  # Tolerance for 1-second interval.
    ("ten_s_target",    32, DIR_M_TO_S),  # Target value for 10-second interval.
    ("ten_s_tol",       32, DIR_M_TO_S),  # Tolerance for 10-second interval.
    ("hundred_s_target",32, DIR_M_TO_S),  # Target value for 100-second interval.
    ("hundred_s_tol",   32, DIR_M_TO_S),  # Tolerance for 100-second interval.
]

ppsdo_status_layout = [
    ("one_s_error",      32, DIR_M_TO_S),  # Error value for 1-second interval.
    ("ten_s_error",      32, DIR_M_TO_S),  # Error value for 10-second interval.
    ("hundred_s_error",  32, DIR_M_TO_S),  # Error value for 100-second interval.
    ("dac_tuned_val",    16, DIR_M_TO_S),  # DAC tuned value.
    ("accuracy",          4, DIR_M_TO_S),  # Accuracy status.
    ("pps_active",        1, DIR_M_TO_S),  # PPS active status.
    ("state",             4, DIR_M_TO_S),  # Current state.
]

# PPSDO --------------------------------------------------------------------------------------------

class PPSDO(LiteXModule):
    def __init__(self, cd_sys="sys", cd_rf="rf", with_csr=False, sys_clk_freq=None, cpu_rftype=None):
        self.cd_sys       = cd_sys
        self.sys_clk_freq = sys_clk_freq
        self.cpu_rftype   = cpu_rftype

        # Control.
        self.enable = Signal()

        # PPS.
        self.pps    = Signal()

        # UART.
        self.uart   = Record(ppsdo_uart_layout)

        # Config.
        self.config = Record(ppsdo_config_layout)

        # Status.
        self.status = Record(ppsdo_status_layout)

        # CSRs.
        if with_csr:
            self.add_csr()

        # # #

        # CDC.
        # ----
        _enable = self.enable
        _pps    = self.pps
        _uart   = self.uart
        _config = self.config
        _status = self.status

        if cd_sys != "sys":
            # Control/PPS (sys -> cd_sys).
            _enable = Signal()
            _pps    = Signal()
            self.specials += MultiReg(self.enable, _enable, odomain=cd_sys)
            self.specials += MultiReg(self.pps,    _pps,    odomain=cd_sys)

            # UART (RX: sys -> cd_sys, TX: cd_sys -> sys).
            _uart = Record(ppsdo_uart_layout)
            self.specials += MultiReg(self.uart.rx, _uart.rx, odomain=cd_sys)
            self.specials += MultiReg(_uart.tx, self.uart.tx, odomain="sys")

            # Config (sys -> cd_sys).
            _config = Record(ppsdo_config_layout)
            config_cdc = BusSynchronizer(len(self.config), "sys", cd_sys)
            self.submodules += config_cdc
            self.comb += [
                config_cdc.i.eq(self.config.raw_bits()),
                _config.raw_bits().eq(config_cdc.o),
            ]

            # Status (cd_sys -> sys).
            _status = Record(ppsdo_status_layout)
            status_cdc = BusSynchronizer(len(self.status), cd_sys, "sys")
            self.submodules += status_cdc
            self.comb += [
                status_cdc.i.eq(_status.raw_bits()),
                self.status.raw_bits().eq(status_cdc.o),
            ]

        # Instance.
        # ---------
        self.specials += Instance("ppsdo",
            # Sys Clk/Rst.
            i_sys_clk              = ClockSignal(cd_sys),
            i_sys_rst              = ResetSignal(cd_sys),

            # RF Clk/Rst.
            i_rf_clk               = ClockSignal(cd_rf),
            i_rf_rst               = ResetSignal(cd_rf),

            # Control.
            i_enable               = _enable,

            # PPS.
            i_pps                  = _pps,

            # UART.
            i_uart_rx              = _uart.rx,
            o_uart_tx              = _uart.tx,

            # Core Config.
            i_config_1s_target     = _config.one_s_target,
            i_config_1s_tol        = _config.one_s_tol,
            i_config_10s_target    = _config.ten_s_target,
            i_config_10s_tol       = _config.ten_s_tol,
            i_config_100s_target   = _config.hundred_s_target,
            i_config_100s_tol      = _config.hundred_s_tol,

            # Core Status.
            o_status_1s_error      = _status.one_s_error,
            o_status_10s_error     = _status.ten_s_error,
            o_status_100s_error    = _status.hundred_s_error,
            o_status_dac_tuned_val = _status.dac_tuned_val,
            o_status_accuracy      = _status.accuracy,
            o_status_pps_active    = _status.pps_active,
            o_status_state         = _status.state,
        )

    def add_csr(self):
        # Enable.
        self._enable = CSRStorage(description="Enable control for PPSDO core")
        self.comb += [
            self.enable.eq(self._enable.storage),
        ]

        # Config.
        self._config_one_s_target     = CSRStorage(32, description="Target value for 1-second interval.")
        self._config_one_s_tol        = CSRStorage(32, description="Tolerance for 1-second interval.")
        self._config_ten_s_target     = CSRStorage(32, description="Target value for 10-second interval.")
        self._config_ten_s_tol        = CSRStorage(32, description="Tolerance for 10-second interval.")
        self._config_hundred_s_target = CSRStorage(32, description="Target value for 100-second interval.")
        self._config_hundred_s_tol    = CSRStorage(32, description="Tolerance for 100-second interval.")
        self.comb += [
            self.config.one_s_target    .eq(self._config_one_s_target.storage),
            self.config.one_s_tol       .eq(self._config_one_s_tol.storage),
            self.config.ten_s_target    .eq(self._config_ten_s_target.storage),
            self.config.ten_s_tol       .eq(self._config_ten_s_tol.storage),
            self.config.hundred_s_target.eq(self._config_hundred_s_target.storage),
            self.config.hundred_s_tol   .eq(self._config_hundred_s_tol.storage),
        ]

        # Status.
        self._status_one_s_error     = CSRStatus(32, description="Error value for 1-second interval.")
        self._status_ten_s_error     = CSRStatus(32, description="Error value for 10-second interval.")
        self._status_hundred_s_error = CSRStatus(32, description="Error value for 100-second interval.")
        self._status_dac_tuned_val   = CSRStatus(16, description="DAC tuned value.")
        self._status_accuracy        = CSRStatus(4,  description="Accuracy status.")
        self._status_pps_active      = CSRStatus(1,  description="PPS active status.")
        self._status_state           = CSRStatus(4,  description="Current state.")
        self.comb += [
            self._status_one_s_error.status    .eq(self.status.one_s_error),
            self._status_ten_s_error.status    .eq(self.status.ten_s_error),
            self._status_hundred_s_error.status.eq(self.status.hundred_s_error),
            self._status_dac_tuned_val.status  .eq(self.status.dac_tuned_val),
            self._status_accuracy.status       .eq(self.status.accuracy),
            self._status_pps_active.status     .eq(self.status.pps_active),
            self._status_state.status          .eq(self.status.state),
        ]

    def add_sources(self, dac_bits=16, cpu_rftype=None):
        from litex.gen import LiteXContext
        cdir = os.path.abspath(os.path.dirname(__file__))

        # Frequency Discovery.
        # --------------------
        sys_clk_freq = self.sys_clk_freq
        if sys_clk_freq is None:
            if self.cd_sys == "sys":
                sys_clk_freq = LiteXContext.top.sys_clk_freq
            else:
                # Try to discover from SoC.
                soc = LiteXContext.top
                # 1. Check for {cd}_clk_freq attribute.
                sys_clk_freq = getattr(soc, f"{self.cd_sys}_clk_freq", None)
                # 2. Check for constants.
                if sys_clk_freq is None:
                    constants = getattr(soc, "constants", {})
                    sys_clk_freq = constants.get(f"{self.cd_sys.upper()}_CLK_FREQ")

        if sys_clk_freq is None:
             raise RuntimeError(f"Could not determine frequency for clock domain {self.cd_sys}. "
                               f"Please provide sys_clk_freq explicitly.")

        # Generate Core.
        # --------------
        rftype = cpu_rftype if cpu_rftype is not None else self.cpu_rftype
        cmd = f"cd {cdir} && python3 ppsdo_gen.py --sys-clk-freq={sys_clk_freq} --dac-bits={dac_bits}"
        if rftype is not None:
            cmd += f" --cpu-rftype={rftype}"
        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError(f"PPSDO generation failed.")

        # Import Core Sources.
        # --------------------
        self.import_sources(LiteXContext.platform, f"{cdir}/build/ppsdo/gateware/ppsdo_sources.py")

    def import_sources(self, platform, filename):
        cdir = os.path.abspath(os.path.dirname(__file__))
        namespace = {}
        with open(filename, "r") as f:
            exec(f.read(), namespace)
        files = namespace
        for path in files['include_paths']:
            platform.add_verilog_include_path(path)
        for src in files['sources']:
            path, lang, lib = src
            if not os.path.isabs(path):
                path = os.path.join(cdir, path)
            platform.add_source(path, lang, lib)

    def add_altera_platform_constraints(self,platform):
        platform.add_platform_command('set_instance_assignment -name RAMSTYLE_ATTRIBUTE M9K -to "*fazyrv_ram*ram_r*"')
        platform.add_platform_command('set_instance_assignment -name ADD_PASS_THROUGH_LOGIC_TO_INFERRED_RAMS OFF -to "*fazyrv_ram*ram_r*"')
        self.altera_pack_memories(platform)

    def altera_pack_memories(self, platform):
        """Patch the generated ppsdo.v (call after add_sources) so Quartus uses fewer M9K blocks.

        - SRAM (64 x 32, byte write enables): Quartus cannot infer byte enables from LiteX's
          Verilog-2001 write loop and splits it into four 64 x 8 RAMs (4 M9K for 256 B). It is
          replaced by a SystemVerilog packed-array module that infers one byte-enabled M9K.
        - UART RX FIFO (16 x 10): forced into logic instead of a whole M9K.
        Saves 4 M9K. Behaviour is unchanged (same registered-address, write-first read).
        """
        import re
        cdir = os.path.abspath(os.path.dirname(__file__))
        gdir = os.path.join(cdir, "build", "ppsdo", "gateware")
        vfile = os.path.join(gdir, "ppsdo.v")
        with open(vfile, "r") as f:
            v = f.read()

        sram_re = re.compile(
            r"reg \[31:0\] sram\[0:(?P<depth_m1>\d+)\];\n"
            r"initial begin\n\t\$readmemh\(\"ppsdo_sram\.init\", sram\);\nend\n"
            r"reg \[(?P<aw_m1>\d+):0\] sram_adr0;\n"
            r"always @\(posedge (?P<clk>\w+)\) begin : mem_write_block\n"
            r"\tinteger we_index;\n"
            r"\tfor\(we_index = 0; we_index < 4; we_index=we_index\+1\)\n"
            r"\t\tif \((?P<we>\w+)\[we_index\]\)\n"
            r"\t\t\tsram\[(?P<adr>\w+)\]\[we_index\*8 \+: 8\] <= (?P<dat_w>\w+)\[we_index\*8 \+: 8\];\n"
            r"\tsram_adr0 <= (?P=adr);\n"
            r"end\n"
            r"assign (?P<dat_r>\w+) = sram\[sram_adr0\];\n")
        m = sram_re.search(v)
        if m is None:
            if "ppsdo_sram_be" not in v:
                print("WARNING: PPSDO SRAM pattern not found in ppsdo.v; byte-enable packing skipped.")
        else:
            aw = int(m.group("aw_m1")) + 1
            assert int(m.group("depth_m1")) + 1 == 2**aw
            v = v[:m.start()] + (
                f"ppsdo_sram_be #(.AW({aw})) sram_be (\n"
                f"\t.clk({m.group('clk')}), .we({m.group('we')}), .adr({m.group('adr')}),\n"
                f"\t.dat_w({m.group('dat_w')}), .dat_r({m.group('dat_r')})\n"
                f");\n") + v[m.end():]
        v = v.replace("reg [9:0] storage_1[0:15];", '(* ramstyle = "logic" *) reg [9:0] storage_1[0:15];')
        with open(vfile, "w") as f:
            f.write(v)

        svfile = os.path.join(gdir, "ppsdo_sram_be.sv")
        with open(svfile, "w") as f:
            f.write("""// Generated by ppsdo.py altera_pack_memories(): byte-enabled SRAM that Quartus maps to one M9K.
module ppsdo_sram_be #(parameter AW = 6) (
    input  logic          clk,
    input  logic [3:0]    we,
    input  logic [AW-1:0] adr,
    input  logic [31:0]   dat_w,
    output logic [31:0]   dat_r
);
    (* ramstyle = "M9K" *) logic [3:0][7:0] mem [0:(1<<AW)-1];
    logic [AW-1:0]   adr_r;
    always_ff @(posedge clk) begin
        if (we[0]) mem[adr][0] <= dat_w[7:0];
        if (we[1]) mem[adr][1] <= dat_w[15:8];
        if (we[2]) mem[adr][2] <= dat_w[23:16];
        if (we[3]) mem[adr][3] <= dat_w[31:24];
        adr_r <= adr;
    end
    assign dat_r = mem[adr_r];
endmodule
""")
        platform.add_source(svfile, "systemverilog", "work")
        # Without an explicit style Quartus implements this small RAM in ~1.6k LEs in the full design.
        platform.add_platform_command('set_instance_assignment -name RAMSTYLE_ATTRIBUTE M9K -to "*ppsdo_sram_be*mem*"')
