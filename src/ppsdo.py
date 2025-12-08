#!/usr/bin/env python3
#
# This file is part of LimePSB_RPCM_GW.
#
# Copyright (c) 2024-2025 Lime Microsystems.
#
# SPDX-License-Identifier: Apache-2.0

import os

from migen import *

from litex.gen import *

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
    def __init__(self, cd_sys="sys", cd_rf="rf", with_csr=False):
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
            i_enable               = self.enable,

            # PPS.
            i_pps                  = self.pps,

            # UART.
            i_uart_rx              = self.uart.rx,
            o_uart_tx              = self.uart.tx,

            # Core Config.
            i_config_1s_target     = self.config.one_s_target,
            i_config_1s_tol        = self.config.one_s_tol,
            i_config_10s_target    = self.config.ten_s_target,
            i_config_10s_tol       = self.config.ten_s_tol,
            i_config_100s_target   = self.config.hundred_s_target,
            i_config_100s_tol      = self.config.hundred_s_tol,

            # Core Status.
            o_status_1s_error      = self.status.one_s_error,
            o_status_10s_error     = self.status.ten_s_error,
            o_status_100s_error    = self.status.hundred_s_error,
            o_status_dac_tuned_val = self.status.dac_tuned_val,
            o_status_accuracy      = self.status.accuracy,
            o_status_pps_active    = self.status.pps_active,
            o_status_state         = self.status.state,
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

    def add_sources(self, dac_bits=16):
        from litex.gen import LiteXContext
        cdir = os.path.abspath(os.path.dirname(__file__))

        # Generate Core.
        # --------------
        ret = os.system(f"cd {cdir} && python3 ppsdo_gen.py --sys-clk-freq={LiteXContext.top.sys_clk_freq} --dac-bits={dac_bits}")
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
