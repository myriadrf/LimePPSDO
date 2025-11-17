.. comment figure:: images/LMS8001_Companion-top.png
   :alt: LMS8001 Companion Board
   :align: center

   LMS8001 Companion Board (note older v2 board pictured).

Introduction
============

.. toctree::
   :maxdepth: 2
   :hidden:

   Introduction <self>

This project provides a **generic, reusable core** for **PPS Disciplined Oscillator (PPSDO)** functionality,
designed to regulate a **Voltage-Controlled Temperature-Compensated Crystal Oscillator (VCTCXO)** using a
**Pulse-Per-Second (PPS)** input signal.

The core is vendor-agnostic and compact, with implementations tested on Lattice iCE40, ECP5, and Xilinx
Artix-7 FPGAs. It supports PPS sources from GPS modules or any other compatible PPS sources, enabling GPSDO
setups as well as more general PPSDO applications.

The core maximizes reuse across Lime Microsystems projects (e.g., integration with LimePSB-RPCM) and non-Lime
projects. It is designed to be generated and integrated with LiteX through a standalone core generator for
easy integration in designs. Key features include:

- **PPS Input**: Captures and processes incoming PPS pulses for timing measurement.
- **VCTCXO Tamer**: Core module for phase/frequency measurement, error accumulation to maintain oscillator
  discipline.
- **Integrated RISC-V CPU**: A lightweight RISC-V processor with dedicated firmware for real-time regulation
  logic.
- **DAC Control Output**: 16-bit parallel digital value for VCTCXO tuning. This parallel output can be
  directly connected to parallel-input DACs or converted to serial protocols (e.g., SPI) in
  hardware-specific wrappers to maintain core genericity.

This core was originally developed and used in Lime Microsystems products (e.g., as part of LimePSB-RPCM GPSDO
gateware) and has been refactored for **broader applicability**.



